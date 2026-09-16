from concurrent.futures import ThreadPoolExecutor
from threading import Event
from time import monotonic, sleep
from unittest.mock import patch
from uuid import uuid4

import pytest
from django.db import IntegrityError, close_old_connections, connection, transaction
from django.http import Http404
from django.test import Client

from crm import services
from crm.models import (
    ContactPoint,
    ContextNote,
    ContextNoteRevision,
    Household,
    Membership,
    Organization,
    Party,
)

pytestmark = pytest.mark.django_db


def csrf_post(client, path, **data):
    return client.post(path, data, HTTP_X_CSRFTOKEN=client.cookies["csrftoken"].value)


def create(user, kind="organization", name="Fictional Common Name", client=False):
    return services.create_typed_party(user, kind, name, client)


@pytest.fixture(autouse=True)
def directory_on(settings):
    settings.PARTY_DIRECTORY_ENABLED = True


def test_subtypes_share_party_identity_and_allow_duplicate_names(owners):
    organization = create(owners[0], "organization", client=True)
    duplicate = create(owners[0], "organization")
    household = create(owners[0], "household")
    assert Organization.objects.get(pk=organization.pk).pk == organization.pk
    assert Household.objects.get(pk=household.pk).pk == household.pk
    assert organization.kind == "organization" and organization.is_client is True
    assert duplicate.display_name == household.display_name == organization.display_name
    assert not duplicate.is_client and not household.is_client
    assert not Party.objects.filter(
        kind="person", id__in=[organization.id, household.id]
    ).exists()


def test_creation_is_atomic_and_validates_client_status(owners):
    with patch.object(
        Organization.objects, "create", side_effect=IntegrityError("injected")
    ):
        with pytest.raises(IntegrityError):
            create(owners[0])
    assert not Party.objects.filter(kind="organization").exists()
    with pytest.raises(Exception):
        services.create_typed_party(owners[0], "household", "Valid", "yes")
    assert not Party.objects.filter(kind="household").exists()


def test_html_create_detail_edit_archive_restore(authenticated, owners):
    response = csrf_post(
        authenticated,
        "/organizations/new/",
        display_name="  Fictional Guild  ",
        is_client="on",
    )
    assert response.status_code == 303
    organization = Party.objects.get(kind="organization")
    assert response["Location"] == f"/organizations/{organization.id}/"
    assert organization.display_name == "Fictional Guild" and organization.is_client
    edit = f"/organizations/{organization.id}/edit/"
    assert (
        csrf_post(
            authenticated, edit, display_name="Guild Two", expected_version=1
        ).status_code
        == 303
    )
    organization.refresh_from_db()
    assert (
        organization.display_name,
        organization.is_client,
        organization.version,
    ) == ("Guild Two", False, 2)
    assert (
        csrf_post(
            authenticated,
            f"/organizations/{organization.id}/archive/",
            expected_version=2,
        ).status_code
        == 303
    )
    organization.refresh_from_db()
    assert organization.archived_at and organization.version == 3
    blocked = csrf_post(authenticated, edit, display_name="Blocked", expected_version=3)
    assert (
        blocked.status_code == 200
        and "Restore this organization" in blocked.content.decode()
    )
    assert (
        csrf_post(
            authenticated,
            f"/organizations/{organization.id}/restore/",
            expected_version=3,
        ).status_code
        == 303
    )
    organization.refresh_from_db()
    assert organization.archived_at is None and organization.version == 4


def test_typed_routes_are_isolated_and_scoped(authenticated, owners):
    organization = create(owners[0], "organization")
    household = create(owners[0], "household")
    foreign = create(owners[1], "organization", "Private")
    for prefix, wrong in (("organizations", household), ("households", organization)):
        for suffix in ("", "edit/"):
            assert (
                authenticated.get(f"/{prefix}/{wrong.id}/{suffix}").status_code == 404
            )
    for suffix in ("", "edit/"):
        assert (
            authenticated.get(f"/organizations/{foreign.id}/{suffix}").status_code
            == 404
        )
    with pytest.raises(Http404):
        services.get_typed_party(owners[0], "organization", household.id)
    body = authenticated.get("/organizations/").content.decode()
    assert organization.display_name in body and foreign.display_name not in body


def test_search_archive_filter_pagination_and_invalid_queries(authenticated, owners):
    for index in range(52):
        create(owners[0], "household", f"Fictional Household {index:02}")
    duplicate = create(owners[0], "household", "Fictional Household 01")
    services.set_typed_party_archived(owners[0], "household", duplicate.id, 1, True)
    first = authenticated.get("/households/?q=household&archived=exclude&page=1")
    second = authenticated.get("/households/?q=household&archived=exclude&page=2")
    assert len(first.context["parties"]) == 50 and len(second.context["parties"]) == 2
    only = authenticated.get("/households/?q=01&archived=only&page=1")
    assert [row.id for row in only.context["parties"]] == [duplicate.id]
    for query in (
        {"q": "x" * 201},
        {"q": "\x00"},
        {"archived": "bad"},
        {"page": "0"},
        {"page": "wat"},
    ):
        assert authenticated.get("/households/", query).status_code == 400
    assert authenticated.get("/households/?q=a&q=b").status_code == 400
    assert authenticated.get("/households/?unknown=value").status_code == 400
    assert (
        len(authenticated.get("/households/?page=" + "9" * 500).context["parties"]) == 0
    )


def test_stale_and_invalid_forms_do_not_write(authenticated, owners):
    party = create(owners[0], "organization", "Before")
    path = f"/organizations/{party.id}/edit/"
    assert (
        csrf_post(
            authenticated, path, display_name="Accepted", expected_version=1
        ).status_code
        == 303
    )
    stale = csrf_post(
        authenticated,
        path,
        display_name="Submitted <draft>",
        is_client="on",
        expected_version=1,
    )
    assert (
        stale.status_code == 409 and "Submitted &lt;draft&gt;" in stale.content.decode()
    )
    for forged in ("workspace_id", "kind", "id", "version"):
        response = csrf_post(
            authenticated,
            path,
            display_name="Forged",
            expected_version=2,
            **{forged: str(uuid4())},
        )
        assert response.status_code == 400
    repeated = authenticated.post(
        path,
        "display_name=A&display_name=B&expected_version=2",
        content_type="application/x-www-form-urlencoded",
        HTTP_X_CSRFTOKEN=authenticated.cookies["csrftoken"].value,
    )
    assert repeated.status_code == 400
    party.refresh_from_db()
    assert (party.display_name, party.is_client, party.version) == (
        "Accepted",
        False,
        2,
    )


def test_flag_off_is_before_csrf_and_independent(authenticated, owners, settings):
    party = create(owners[0], "household")
    settings.PARTY_DIRECTORY_ENABLED = False
    for path in (
        "/organizations/",
        "/organizations/new/",
        f"/households/{party.id}/",
        f"/households/{party.id}/archive/",
    ):
        assert authenticated.get(path).status_code == 404
        assert authenticated.post(path, {"expected_version": 1}).status_code == 404
    assert (
        authenticated.post(
            "/organizations/new/",
            b"x" * 300_000,
            content_type="application/octet-stream",
        ).status_code
        == 404
    )
    assert Client(enforce_csrf_checks=True).post("/households/new/").status_code == 404
    assert "Organizations" not in authenticated.get("/people/").content.decode()
    assert Party.objects.filter(pk=party.pk).exists()
    settings.PEOPLE_MANAGEMENT_ENABLED = False
    settings.CONTEXT_NOTES_ENABLED = True
    person = services.create_person(owners[0], "Independent Person")
    note = services.create_context_note(owners[0], person.id, 1, "Context", "Source")
    assert (
        authenticated.get(f"/people/{person.id}/notes/{note.id}/history/").status_code
        == 200
    )
    settings.PARTY_DIRECTORY_ENABLED = True
    assert authenticated.get(f"/households/{party.id}/").status_code == 200


def test_auth_csrf_revocation_and_staff_no_bypass(authenticated, owners):
    party = create(owners[0])
    path = f"/organizations/{party.id}/edit/"
    assert authenticated.get(f"/organizations/{party.id}/archive/").status_code == 405
    assert Client().get(path).status_code == 302
    assert (
        authenticated.post(
            path, {"display_name": "No csrf", "expected_version": 1}
        ).status_code
        == 403
    )
    owners[1].is_staff = owners[1].is_superuser = True
    owners[1].save()
    staff = Client(enforce_csrf_checks=True)
    staff.force_login(owners[1])
    assert staff.get(path).status_code == 404
    Membership.objects.filter(user=owners[0]).update(active=False)
    assert authenticated.get(path).status_code == 302
    party.refresh_from_db()
    assert party.version == 1


@pytest.mark.django_db(transaction=True)
def test_concurrent_edit_and_archive_conflict_under_party_lock(owners):
    party = create(owners[0])
    client = Client(enforce_csrf_checks=True)
    client.force_login(owners[0])
    client.get("/people/new/")
    started = Event()
    backend_pid = []

    def edit():
        close_old_connections()
        try:
            with connection.cursor() as cursor:
                cursor.execute("SELECT pg_backend_pid()")
                backend_pid.append(cursor.fetchone()[0])
            started.set()
            return csrf_post(
                client,
                f"/organizations/{party.id}/edit/",
                display_name="Losing edit",
                expected_version=1,
            ).status_code
        finally:
            connection.close()

    with ThreadPoolExecutor(max_workers=1) as pool:
        with transaction.atomic():
            Party.objects.select_for_update().get(pk=party.pk)
            future = pool.submit(edit)
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
                pytest.fail("Edit did not wait for the Party lock")
            services.set_typed_party_archived(
                owners[0], "organization", party.id, 1, True
            )
        assert future.result(timeout=10) == 409
    party.refresh_from_db()
    assert (
        party.archived_at
        and party.display_name == "Fictional Common Name"
        and party.version == 2
    )


@pytest.mark.django_db(transaction=True)
def test_additive_migration_preserves_stage_two_records(owners):
    from django.db.migrations.executor import MigrationExecutor

    person = services.create_person(owners[0], "Before stage three")
    contact = services.create_contact_point(
        owners[0], person.id, 1, "email", "before@example.invalid", "Prior"
    )
    person.refresh_from_db()
    note = services.create_context_note(owners[0], person.id, 2, "Body", "Source")
    services.update_context_note(
        owners[0], person.id, note.id, 1, "Corrected", "Follow-up"
    )
    person.refresh_from_db()
    note.refresh_from_db()
    identity, version = person.id, person.version
    executor = MigrationExecutor(connection)
    executor.migrate([("crm", "0003_contextnote_contextnoterevision_and_more")])
    try:
        assert not {"crm_organization", "crm_household"}.issubset(
            connection.introspection.table_names()
        )
    finally:
        executor = MigrationExecutor(connection)
        executor.migrate(executor.loader.graph.leaf_nodes())
    person = Party.objects.get(pk=identity)
    assert person.version == version
    assert (ContactPoint.objects.get(pk=contact.pk).value, contact.version) == (
        "before@example.invalid",
        1,
    )
    assert (ContextNote.objects.get(pk=note.pk).body, note.version) == ("Corrected", 2)
    assert ContextNoteRevision.objects.get(note_id=note.pk).body == "Body"
    assert create(owners[0], "organization").organization.party_id is not None
