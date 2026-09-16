from concurrent.futures import ThreadPoolExecutor
from datetime import timedelta
from threading import Event
from time import monotonic, sleep
from uuid import uuid4

import pytest
from django.db import (
    IntegrityError,
    close_old_connections,
    connection,
    transaction,
)
from django.test import Client
from django.utils import timezone

from crm import services
from crm.models import Membership, Party, Relationship

pytestmark = pytest.mark.django_db


@pytest.fixture(autouse=True)
def relationships_on(settings):
    settings.RELATIONSHIPS_ENABLED = True


def csrf_post(client, path, **data):
    return client.post(path, data, HTTP_X_CSRFTOKEN=client.cookies["csrftoken"].value)


def parties(owners):
    person = services.create_person(owners[0], "Fictional Person")
    company = services.create_typed_party(
        owners[0], "organization", "Fictional Company", False
    )
    household = services.create_typed_party(
        owners[0], "household", "Fictional Household", False
    )
    return person, company, household


def make_relationship(user, source, target, **overrides):
    data = {
        "kind": "employment",
        "role": "Engineer",
        "starts_on": None,
        "ends_on": None,
    }
    data.update(overrides)
    return services.create_relationship(user, source.id, target.id, **data)


def test_create_edit_close_and_reopen_preserve_direction(authenticated, owners):
    person, company, household = parties(owners)
    response = csrf_post(
        authenticated,
        "/relationships/new/",
        from_party_id=person.id,
        to_party_id=company.id,
        kind="employment",
        role="Engineer",
        starts_on="2025-01-01",
        ends_on="",
    )
    assert response.status_code == 303
    relationship = Relationship.objects.get()
    assert response["Location"] == f"/relationships/{relationship.id}/"
    assert (relationship.from_party_id, relationship.to_party_id) == (
        person.id,
        company.id,
    )
    detail = authenticated.get(response["Location"])
    assert "Fictional Person" in detail.content.decode()
    assert "Fictional Company" in detail.content.decode()

    close = csrf_post(
        authenticated,
        f"/relationships/{relationship.id}/close/",
        expected_version=1,
        ends_on="2025-12-31",
    )
    assert close.status_code == 303
    relationship.refresh_from_db()
    assert str(relationship.ends_on) == "2025-12-31" and relationship.version == 2

    edit = csrf_post(
        authenticated,
        f"/relationships/{relationship.id}/edit/",
        expected_version=2,
        kind="employment",
        role="Principal Engineer",
        starts_on="2025-01-01",
        ends_on="",
    )
    assert edit.status_code == 303
    relationship.refresh_from_db()
    assert relationship.ends_on is None and relationship.version == 3
    assert relationship.role == "Principal Engineer"

    second = make_relationship(
        owners[0], person, household, kind="household_member", role=None
    )
    assert second.id != relationship.id
    assert Relationship.objects.filter(from_party=person).count() == 2


def test_validation_duplicates_and_database_constraints(owners):
    person, company, _ = parties(owners)
    today = timezone.now().date()
    first = make_relationship(
        owners[0], person, company, starts_on=today - timedelta(days=10)
    )
    second = make_relationship(
        owners[0], person, company, starts_on=today - timedelta(days=5)
    )
    assert first.id != second.id
    with pytest.raises(Exception):
        make_relationship(owners[0], person, person)
    with pytest.raises(Exception):
        make_relationship(
            owners[0],
            person,
            company,
            starts_on=today,
            ends_on=today - timedelta(days=1),
        )
    for invalid_kind in ("", "x" * 81, "bad\x00kind", "bad\ud800kind"):
        with pytest.raises(Exception):
            make_relationship(owners[0], person, company, kind=invalid_kind)
    foreign = services.create_person(owners[1], "Foreign Person")
    with pytest.raises(Exception):
        make_relationship(owners[0], person, foreign)

    with pytest.raises(IntegrityError), transaction.atomic():
        Relationship.objects.create(
            workspace=person.workspace,
            from_party=person,
            to_party=foreign,
            kind="other",
        )
    with pytest.raises(IntegrityError), transaction.atomic():
        Relationship.objects.create(
            workspace=person.workspace,
            from_party=person,
            to_party=person,
            kind="other",
        )


def test_timeline_boundaries_ordering_panels_and_pagination(
    authenticated, owners, settings
):
    settings.PARTY_DIRECTORY_ENABLED = True
    person, company, household = parties(owners)
    today = timezone.now().date()
    unbounded = make_relationship(owners[0], person, household, kind="referral")
    current = make_relationship(
        owners[0], person, company, starts_on=today, ends_on=today
    )
    future = make_relationship(
        owners[0], person, company, starts_on=today + timedelta(days=1)
    )
    ended = make_relationship(
        owners[0], person, company, ends_on=today - timedelta(days=1)
    )
    active, prior = services.relationship_panels(owners[0], person.id)
    assert [row.id for row in active] == [unbounded.id, current.id, future.id]
    assert [row.timeline_status for row in active] == ["current", "current", "future"]
    assert [row.id for row in prior] == [ended.id]

    for path in (
        f"/people/{person.id}/",
        f"/organizations/{company.id}/",
        f"/households/{household.id}/",
    ):
        body = authenticated.get(path).content.decode()
        assert "Relationships" in body
    for query in (
        "relationships_page=0",
        "relationships_ended_page=wat",
        "relationships_page=1&relationships_page=2",
        "unknown=1",
    ):
        assert authenticated.get(f"/people/{person.id}/?{query}").status_code == 400
        assert (
            authenticated.get(f"/organizations/{company.id}/?{query}").status_code
            == 400
        )


def test_independent_scoped_selectors_search_and_paginate(authenticated, owners):
    person, company, _ = parties(owners)
    for index in range(55):
        services.create_person(owners[0], f"AAA Selector filler {index:02}")
    url = (
        "/relationships/new/?from_q=Fictional+Person&from_page=1"
        "&to_q=Fictional+Company&to_page=1"
    )
    response = authenticated.get(url)
    body = response.content.decode()
    assert response.status_code == 200
    assert f'value="{person.id}"' in body and f'value="{company.id}"' in body
    created = csrf_post(
        authenticated,
        url,
        from_party_id=person.id,
        to_party_id=company.id,
        kind="employment",
        role="Selected independently",
        starts_on="",
        ends_on="",
    )
    assert created.status_code == 303
    first_page = authenticated.get("/relationships/new/?from_page=1&to_page=1")
    assert "Next from parties" in first_page.content.decode()
    assert "Next to parties" in first_page.content.decode()
    for query in (
        "from_page=0",
        "to_page=nope",
        "from_q=a&from_q=b",
        "unknown=x",
    ):
        assert authenticated.get(f"/relationships/new/?{query}").status_code == 400
    assert (
        authenticated.get("/relationships/new/?from_page=" + "9" * 500).status_code
        == 200
    )


def test_panel_pagination_links_preserve_the_other_page(authenticated, owners):
    person, company, _ = parties(owners)
    today = timezone.now().date()
    Relationship.objects.bulk_create(
        [
            Relationship(
                workspace=person.workspace,
                from_party=person,
                to_party=company,
                kind="current",
            )
            for _ in range(51)
        ]
        + [
            Relationship(
                workspace=person.workspace,
                from_party=person,
                to_party=company,
                kind="ended",
                ends_on=today - timedelta(days=1),
            )
            for _ in range(51)
        ]
    )
    body = authenticated.get(
        f"/people/{person.id}/?relationships_page=1&relationships_ended_page=1"
    ).content.decode()
    assert "relationships_page=2&amp;relationships_ended_page=1" in body
    assert "relationships_page=1&amp;relationships_ended_page=2" in body


def test_scoping_auth_csrf_flags_and_independent_directory(
    authenticated, owners, settings
):
    person, company, _ = parties(owners)
    relationship = make_relationship(owners[0], person, company)
    foreign_client = Client(enforce_csrf_checks=True)
    foreign_client.force_login(owners[1])
    assert foreign_client.get(f"/relationships/{relationship.id}/").status_code == 404
    assert Client().get(f"/relationships/{relationship.id}/").status_code == 302
    assert (
        authenticated.post(
            f"/relationships/{relationship.id}/edit/",
            {"expected_version": 1, "kind": "other"},
        ).status_code
        == 403
    )
    settings.PARTY_DIRECTORY_ENABLED = False
    assert authenticated.get(f"/relationships/{relationship.id}/").status_code == 200
    body = authenticated.get(f"/relationships/{relationship.id}/").content.decode()
    assert f"/organizations/{company.id}/" not in body
    assert f"/people/{person.id}/" in body
    selector = authenticated.get("/relationships/new/")
    assert selector.status_code == 200
    assert "Fictional Person" in selector.content.decode()
    settings.RELATIONSHIPS_ENABLED = False
    for path in (
        "/relationships/new/",
        f"/relationships/{relationship.id}/",
        f"/relationships/{relationship.id}/edit/",
        f"/relationships/{relationship.id}/close/",
    ):
        assert authenticated.get(path).status_code == 404
        assert authenticated.post(path, {"expected_version": 1}).status_code == 404
    assert Relationship.objects.filter(pk=relationship.pk).exists()


def test_stale_unknown_repeated_and_forged_references(authenticated, owners):
    person, company, _ = parties(owners)
    relationship = make_relationship(owners[0], person, company)
    edit_path = f"/relationships/{relationship.id}/edit/"
    assert (
        csrf_post(
            authenticated,
            edit_path,
            expected_version=1,
            kind="employment",
            role="Accepted",
            starts_on="",
            ends_on="",
        ).status_code
        == 303
    )
    stale = csrf_post(
        authenticated,
        edit_path,
        expected_version=1,
        kind="other",
        role="Submitted <draft>",
        starts_on="",
        ends_on="",
    )
    assert stale.status_code == 409
    assert "Submitted &lt;draft&gt;" in stale.content.decode()
    relationship.refresh_from_db()
    assert relationship.role == "Accepted" and relationship.version == 2
    stale_close = csrf_post(
        authenticated,
        f"/relationships/{relationship.id}/close/",
        expected_version=1,
        ends_on="2026-01-01",
    )
    assert stale_close.status_code == 409
    relationship.refresh_from_db()
    assert relationship.ends_on is None and relationship.version == 2

    foreign = services.create_person(owners[1], "Private")
    response = csrf_post(
        authenticated,
        "/relationships/new/",
        from_party_id=person.id,
        to_party_id=foreign.id,
        kind="other",
        role="",
        starts_on="",
        ends_on="",
    )
    assert response.status_code == 400 and "Private" not in response.content.decode()
    assert (
        csrf_post(
            authenticated,
            edit_path,
            expected_version=2,
            kind="other",
            role="No",
            starts_on="",
            ends_on="",
            workspace_id=uuid4(),
        ).status_code
        == 400
    )
    repeated = authenticated.post(
        edit_path,
        "expected_version=2&kind=other&kind=referral&role=&starts_on=&ends_on=",
        content_type="application/x-www-form-urlencoded",
        HTTP_X_CSRFTOKEN=authenticated.cookies["csrftoken"].value,
    )
    assert repeated.status_code == 400


def test_archived_endpoints_readable_editable_but_not_new_links(owners):
    person, company, household = parties(owners)
    relationship = make_relationship(owners[0], person, company)
    services.set_typed_party_archived(owners[0], "organization", company.id, 1, True)
    updated = services.update_relationship(
        owners[0], relationship.id, 1, "employment", "Historical", None, None
    )
    assert updated.version == 2
    with pytest.raises(Exception):
        make_relationship(owners[0], household, company, kind="other")


def test_revocation_applies_to_relationship_routes(authenticated, owners):
    person, company, _ = parties(owners)
    relationship = make_relationship(owners[0], person, company)
    Membership.objects.filter(user=owners[0]).update(active=False)
    assert authenticated.get(f"/relationships/{relationship.id}/").status_code == 302


@pytest.mark.django_db(transaction=True)
def test_create_waits_for_archive_and_fails_without_partial_link(owners):
    person, company, _ = parties(owners)
    started = Event()
    backend_pid = []

    def create_link():
        close_old_connections()
        try:
            with connection.cursor() as cursor:
                cursor.execute("SELECT pg_backend_pid()")
                backend_pid.append(cursor.fetchone()[0])
            started.set()
            try:
                make_relationship(owners[0], person, company)
            except Exception:
                return "rejected"
            return "created"
        finally:
            connection.close()

    with ThreadPoolExecutor(max_workers=1) as pool:
        with transaction.atomic():
            Party.objects.select_for_update().get(pk=company.pk)
            future = pool.submit(create_link)
            assert started.wait(10)
            deadline = monotonic() + 5
            while monotonic() < deadline:
                with connection.cursor() as cursor:
                    cursor.execute(
                        "SELECT wait_event_type FROM pg_stat_activity WHERE pid = %s",
                        backend_pid,
                    )
                    row = cursor.fetchone()
                if row and row[0] == "Lock":
                    break
                assert not future.done()
                sleep(0.01)
            else:
                pytest.fail("Relationship creation did not wait for the Party lock")
            services.set_typed_party_archived(
                owners[0], "organization", company.id, 1, True
            )
        assert future.result(timeout=10) == "rejected"
    assert not Relationship.objects.exists()


@pytest.mark.django_db(transaction=True)
def test_archive_waits_for_link_creation_then_preserves_history(owners):
    person, company, _ = parties(owners)
    started = Event()
    backend_pid = []

    def archive_party():
        close_old_connections()
        try:
            with connection.cursor() as cursor:
                cursor.execute("SELECT pg_backend_pid()")
                backend_pid.append(cursor.fetchone()[0])
            started.set()
            services.set_typed_party_archived(
                owners[0], "organization", company.id, 1, True
            )
            return "archived"
        finally:
            connection.close()

    with ThreadPoolExecutor(max_workers=1) as pool:
        with transaction.atomic():
            locked = services._lock_parties(  # exercise the shared sorted lock order
                person.workspace, [person.id, company.id], require_active=True
            )
            relationship = Relationship.objects.create(
                workspace=person.workspace,
                from_party=locked[person.id],
                to_party=locked[company.id],
                kind="employment",
            )
            future = pool.submit(archive_party)
            assert started.wait(10)
            deadline = monotonic() + 5
            while monotonic() < deadline:
                with connection.cursor() as cursor:
                    cursor.execute(
                        "SELECT wait_event_type FROM pg_stat_activity WHERE pid = %s",
                        backend_pid,
                    )
                    row = cursor.fetchone()
                if row and row[0] == "Lock":
                    break
                assert not future.done()
                sleep(0.01)
            else:
                pytest.fail("Party archive did not wait for relationship locks")
        assert future.result(timeout=10) == "archived"
    company.refresh_from_db()
    assert company.archived_at is not None
    assert Relationship.objects.filter(pk=relationship.pk).exists()


@pytest.mark.django_db(transaction=True)
def test_additive_migration_preserves_stage_three_parties(owners):
    person, company, household = parties(owners)
    identities = {person.id, company.id, household.id}
    from django.db.migrations.executor import MigrationExecutor

    executor = MigrationExecutor(connection)
    executor.migrate([("crm", "0004_party_subtypes")])
    try:
        assert "crm_relationship" not in connection.introspection.table_names()
    finally:
        executor = MigrationExecutor(connection)
        executor.migrate(executor.loader.graph.leaf_nodes())
    assert (
        set(Party.objects.filter(id__in=identities).values_list("id", flat=True))
        == identities
    )
