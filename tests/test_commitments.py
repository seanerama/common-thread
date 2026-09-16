from concurrent.futures import ThreadPoolExecutor
from datetime import UTC, date, datetime
from threading import Barrier, Event
from time import monotonic, sleep

import pytest
from django.core.exceptions import ValidationError
from django.db import IntegrityError, close_old_connections, connection, transaction
from django.test import Client
from django.utils import timezone

from crm import services
from crm.models import (
    Commitment,
    CommitmentPerson,
    ContextNote,
    Interaction,
    Membership,
    Organization,
    Party,
)

pytestmark = pytest.mark.django_db


@pytest.fixture(autouse=True)
def commitments_on(settings):
    settings.COMMITMENTS_ENABLED = True


def csrf_post(client, path, **data):
    return client.post(path, data, HTTP_X_CSRFTOKEN=client.cookies["csrftoken"].value)


def people(owners):
    return (
        services.create_person(owners[0], "Fictional Alex"),
        services.create_person(owners[0], "Fictional Blair"),
        services.create_person(owners[0], "Fictional Casey"),
    )


def make_commitment(user, owed_by, owed_to, person_ids, **overrides):
    values = {
        "description": "Fictional promise to follow through",
        "due_on": None,
        "source_interaction_id": None,
        "interactions_enabled": True,
    }
    values.update(overrides)
    return services.create_commitment(
        user,
        owed_by_party_id=owed_by.id,
        owed_to_party_id=owed_to.id,
        person_ids=person_ids,
        **values,
    )


def wait_for_database_lock(future, backend_pid, message):
    deadline = monotonic() + 5
    while monotonic() < deadline:
        with connection.cursor() as cursor:
            cursor.execute(
                "SELECT wait_event_type FROM pg_stat_activity WHERE pid = %s",
                backend_pid,
            )
            row = cursor.fetchone()
        if row and row[0] == "Lock":
            return
        assert not future.done()
        sleep(0.01)
    pytest.fail(message)


def test_create_explicit_direction_shared_people_source_and_attribution(
    authenticated, owners, settings
):
    settings.INTERACTIONS_ENABLED = True
    first, second, _ = people(owners)
    source = services.create_interaction(
        owners[0],
        "2026-09-16T10:00:00+00:00",
        "Fictional shared conversation",
        [first.id, second.id],
    )
    response = csrf_post(
        authenticated,
        "/commitments/new/",
        description="Promise <with details>",
        owed_by_party_id=first.id,
        owed_to_party_id=second.id,
        due_on="2026-09-20",
        person_ids=[first.id, second.id],
        source_interaction_id=source.id,
    )
    assert response.status_code == 303
    commitment = Commitment.objects.get()
    assert response["Location"] == f"/commitments/{commitment.id}/"
    assert commitment.owed_by == first and commitment.owed_to == second
    assert commitment.created_by == owners[0]
    assert commitment.status == "open" and commitment.completed_at is None
    assert commitment.source_interaction == source
    assert set(commitment.person_links.values_list("person_id", flat=True)) == {
        first.id,
        second.id,
    }
    for person in (first, second):
        body = authenticated.get(f"/people/{person.id}/").content.decode()
        assert "Promise &lt;with details&gt;" in body
    settings.INTERACTIONS_ENABLED = False
    detail = authenticated.get(f"/commitments/{commitment.id}/").content.decode()
    assert "View source interaction" not in detail
    assert "Fictional shared conversation" not in detail


def test_complete_reopen_stale_and_repeated_state(authenticated, owners):
    first, second, _ = people(owners)
    commitment = make_commitment(owners[0], first, second, [first.id])
    completed = csrf_post(
        authenticated,
        f"/commitments/{commitment.id}/complete/",
        expected_version=1,
    )
    assert completed.status_code == 303
    commitment.refresh_from_db()
    completed_at = commitment.completed_at
    assert commitment.status == "completed" and completed_at is not None
    repeated = csrf_post(
        authenticated,
        f"/commitments/{commitment.id}/complete/",
        expected_version=2,
    )
    assert repeated.status_code == 200
    commitment.refresh_from_db()
    assert commitment.version == 2 and commitment.completed_at == completed_at
    stale = csrf_post(
        authenticated,
        f"/commitments/{commitment.id}/reopen/",
        expected_version=1,
    )
    assert stale.status_code == 409
    reopened = csrf_post(
        authenticated,
        f"/commitments/{commitment.id}/reopen/",
        expected_version=2,
    )
    assert reopened.status_code == 303
    commitment.refresh_from_db()
    assert commitment.status == "open" and commitment.completed_at is None
    assert commitment.version == 3


def test_person_only_and_same_workspace_database_constraints(owners):
    first, second, _ = people(owners)
    commitment = make_commitment(owners[0], first, second, [first.id])
    organization = Party.objects.create(
        workspace=first.workspace, kind="organization", display_name="Fictional Org"
    )
    Organization.objects.create(party=organization)
    with pytest.raises(IntegrityError), transaction.atomic():
        CommitmentPerson.objects.create(
            workspace=first.workspace,
            commitment=commitment,
            person=organization,
        )
    foreign = services.create_person(owners[1], "Private Person")
    with pytest.raises(IntegrityError), transaction.atomic():
        CommitmentPerson.objects.create(
            workspace=first.workspace, commitment=commitment, person=foreign
        )
    with pytest.raises(IntegrityError), transaction.atomic():
        Commitment.objects.create(
            workspace=first.workspace,
            description="Wrong workspace direction",
            owed_by=first,
            owed_to=foreign,
            created_by=owners[0],
        )
    foreign_interaction = services.create_interaction(
        owners[1], "2026-01-01T00:00:00+00:00", "Private", [foreign.id]
    )
    with pytest.raises(IntegrityError), transaction.atomic():
        Commitment.objects.create(
            workspace=first.workspace,
            description="Wrong source workspace",
            owed_by=first,
            owed_to=second,
            created_by=owners[0],
            source_interaction=foreign_interaction,
        )


def test_validation_atomic_edit_archived_retention_and_cross_role_guard(owners):
    first, second, third = people(owners)
    commitment = make_commitment(owners[0], first, second, [first.id, third.id])
    services.set_person_archived(owners[0], third.id, 1, True)
    retained = services.update_commitment(
        owners[0],
        commitment.id,
        1,
        "Retain archived linked person",
        first.id,
        second.id,
        None,
        [first.id, third.id],
    )
    services.set_person_archived(owners[0], first.id, 1, True)
    with pytest.raises(ValidationError):
        services.update_commitment(
            owners[0],
            commitment.id,
            retained.version,
            "Cannot move archived person into a new role",
            second.id,
            first.id,
            None,
            [first.id, third.id],
        )
    commitment.refresh_from_db()
    assert commitment.version == 2
    assert commitment.owed_by_id == first.id and commitment.owed_to_id == second.id
    with pytest.raises(ValidationError):
        services.update_commitment(
            owners[0],
            commitment.id,
            2,
            "Invalid empty people",
            first.id,
            second.id,
            None,
            [],
        )
    assert (
        CommitmentPerson.objects.filter(
            commitment_id=commitment.id, archived_at__isnull=True
        ).count()
        == 2
    )


def test_due_status_filters_utc_order_nulls_and_combinations(owners, monkeypatch):
    first, second, _ = people(owners)
    fixed = datetime(2026, 9, 16, 23, 30, tzinfo=UTC)
    monkeypatch.setattr(timezone, "now", lambda: fixed)
    overdue = make_commitment(
        owners[0],
        first,
        second,
        [first.id],
        description="Overdue",
        due_on=date(2026, 9, 15),
    )
    today = make_commitment(
        owners[0],
        first,
        second,
        [first.id],
        description="Today",
        due_on=date(2026, 9, 16),
    )
    undated = make_commitment(
        owners[0], first, second, [first.id], description="Undated"
    )
    services.set_commitment_completed(owners[0], today.id, 1, True)
    assert [
        row.id for row in services.list_commitments(owners[0], "all", "overdue")
    ] == [overdue.id]
    assert [
        row.id for row in services.list_commitments(owners[0], "completed", "today")
    ] == [today.id]
    assert list(services.list_commitments(owners[0], "completed", "overdue")) == []
    assert [
        row.id for row in services.list_commitments(owners[0], "open", "undated")
    ] == [undated.id]
    all_rows = list(services.list_commitments(owners[0], "all", "all"))
    assert [row.id for row in all_rows[:2]] == [overdue.id, today.id]
    assert all_rows[-1].id == undated.id


def test_selectors_accumulate_over_fifty_and_retain_archived(authenticated, owners):
    first, second, _ = people(owners)
    for index in range(55):
        services.create_person(owners[0], f"AAA Commitment person {index:02}")
    page = authenticated.get("/commitments/new/?people_page=1")
    assert page.status_code == 200 and "Next people" in page.content.decode()
    selected_url = (
        f"/commitments/new/?people_q=Fictional+Blair&person_selected={first.id}"
        f"&owed_by_selected={first.id}&owed_to_selected={second.id}"
    )
    body = authenticated.get(selected_url).content.decode()
    assert f'value="{first.id}" checked' in body
    assert "Fictional Blair" in body
    services.set_person_archived(owners[0], first.id, 1, True)
    commitment = make_commitment(owners[0], second, second, [second.id])
    commitment.person_links.create(workspace=first.workspace, person=first)
    edit = authenticated.get(f"/commitments/{commitment.id}/edit/")
    assert edit.status_code == 200 and "archived" in edit.content.decode()


def test_interactions_off_create_preserve_clear_and_forged_source(
    authenticated, owners, settings
):
    first, second, _ = people(owners)
    source = services.create_interaction(
        owners[0], "2026-01-01T00:00:00+00:00", "Hidden source", [first.id]
    )
    existing = make_commitment(
        owners[0], first, second, [first.id], source_interaction_id=source.id
    )
    settings.INTERACTIONS_ENABLED = False
    created = csrf_post(
        authenticated,
        "/commitments/new/",
        description="Created while interactions are off",
        owed_by_party_id=first.id,
        owed_to_party_id=second.id,
        due_on="",
        person_ids=[first.id],
    )
    assert created.status_code == 303
    forged = csrf_post(
        authenticated,
        "/commitments/new/",
        description="Forged source",
        owed_by_party_id=first.id,
        owed_to_party_id=second.id,
        due_on="",
        person_ids=[first.id],
        source_interaction_id=source.id,
    )
    assert forged.status_code == 400
    preserved = csrf_post(
        authenticated,
        f"/commitments/{existing.id}/edit/",
        expected_version=1,
        description="Preserved hidden source",
        owed_by_party_id=first.id,
        owed_to_party_id=second.id,
        due_on="",
        person_ids=[first.id],
    )
    assert preserved.status_code == 303
    existing.refresh_from_db()
    assert existing.source_interaction_id == source.id
    cleared = csrf_post(
        authenticated,
        f"/commitments/{existing.id}/edit/",
        expected_version=2,
        description="Clear hidden source",
        owed_by_party_id=first.id,
        owed_to_party_id=second.id,
        due_on="",
        person_ids=[first.id],
        clear_source_interaction="on",
    )
    assert cleared.status_code == 303
    existing.refresh_from_db()
    assert existing.source_interaction_id is None
    assert authenticated.get("/commitments/new/?source_q=Hidden").status_code == 400


def test_auth_revocation_csrf_flag_gate_and_context_note_unchanged(
    authenticated, owners, settings
):
    first, second, _ = people(owners)
    commitment = make_commitment(owners[0], first, second, [first.id])
    note = ContextNote.objects.create(
        workspace=first.workspace,
        person=first,
        body="Existing note",
        source="operator",
        authored_by=owners[0],
    )
    assert note.source_interaction_id is None
    foreign = Client(enforce_csrf_checks=True)
    foreign.force_login(owners[1])
    assert foreign.get(f"/commitments/{commitment.id}/").status_code == 404
    assert Client().get(f"/commitments/{commitment.id}/").status_code == 302
    assert (
        authenticated.post(
            f"/commitments/{commitment.id}/complete/", {"expected_version": 1}
        ).status_code
        == 403
    )
    Membership.objects.filter(user=owners[0]).update(active=False)
    assert authenticated.get(f"/commitments/{commitment.id}/").status_code == 302
    Membership.objects.filter(user=owners[0]).update(active=True)
    settings.COMMITMENTS_ENABLED = False
    for path in (
        "/commitments/",
        "/commitments/new/",
        f"/commitments/{commitment.id}/",
    ):
        assert authenticated.get(path).status_code == 404
        assert authenticated.post(path, {}).status_code == 404
    assert Commitment.objects.filter(pk=commitment.pk).exists()


@pytest.mark.django_db(transaction=True)
def test_concurrent_state_change_allows_exactly_one_version(owners):
    first, second, _ = people(owners)
    commitment = make_commitment(owners[0], first, second, [first.id])
    barrier = Barrier(2)

    def complete():
        close_old_connections()
        try:
            barrier.wait(timeout=10)
            try:
                services.set_commitment_completed(owners[0], commitment.id, 1, True)
            except Exception:
                return "rejected"
            return "completed"
        finally:
            connection.close()

    with ThreadPoolExecutor(max_workers=2) as pool:
        results = list(pool.map(lambda _: complete(), range(2)))
    assert sorted(results) == ["completed", "rejected"]
    commitment.refresh_from_db()
    assert commitment.version == 2 and commitment.status == "completed"


@pytest.mark.django_db(transaction=True)
def test_create_waits_for_archive_and_rejects_new_archived_reference(owners):
    first, second, third = people(owners)
    started = Event()
    backend_pid = []

    def create_new():
        close_old_connections()
        try:
            with connection.cursor() as cursor:
                cursor.execute("SELECT pg_backend_pid()")
                backend_pid.append(cursor.fetchone()[0])
            started.set()
            try:
                make_commitment(owners[0], first, second, [first.id, third.id])
            except Exception:
                return "rejected"
            return "created"
        finally:
            connection.close()

    with ThreadPoolExecutor(max_workers=1) as pool:
        with transaction.atomic():
            Party.objects.select_for_update().get(pk=third.pk)
            future = pool.submit(create_new)
            assert started.wait(10)
            wait_for_database_lock(
                future, backend_pid, "Creation did not wait for Party lock"
            )
            services.set_person_archived(owners[0], third.id, 1, True)
        assert future.result(timeout=10) == "rejected"
    assert not Commitment.objects.exists()
    assert not CommitmentPerson.objects.exists()


@pytest.mark.django_db(transaction=True)
def test_archive_waits_for_creation_then_preserves_commitment(owners):
    first, second, third = people(owners)
    started = Event()
    backend_pid = []

    def archive_new_person():
        close_old_connections()
        try:
            with connection.cursor() as cursor:
                cursor.execute("SELECT pg_backend_pid()")
                backend_pid.append(cursor.fetchone()[0])
            started.set()
            services.set_person_archived(owners[0], third.id, 1, True)
            return "archived"
        finally:
            connection.close()

    with ThreadPoolExecutor(max_workers=1) as pool:
        with transaction.atomic():
            locked = services._lock_parties(
                first.workspace, [first.id, second.id, third.id], require_active=True
            )
            commitment = Commitment.objects.create(
                workspace=first.workspace,
                description="Created before archive",
                owed_by=locked[first.id],
                owed_to=locked[second.id],
                created_by=owners[0],
            )
            CommitmentPerson.objects.bulk_create(
                [
                    CommitmentPerson(
                        workspace=first.workspace,
                        commitment=commitment,
                        person=locked[person_id],
                    )
                    for person_id in (first.id, third.id)
                ]
            )
            future = pool.submit(archive_new_person)
            assert started.wait(10)
            wait_for_database_lock(
                future, backend_pid, "Archive did not wait for creation"
            )
        assert future.result(timeout=10) == "archived"
    assert CommitmentPerson.objects.filter(commitment=commitment, person=third).exists()


@pytest.mark.django_db(transaction=True)
def test_edit_waits_for_archive_and_rejects_new_archived_link(owners):
    first, second, third = people(owners)
    commitment = make_commitment(owners[0], first, second, [first.id])
    started = Event()
    backend_pid = []

    def add_person():
        close_old_connections()
        try:
            with connection.cursor() as cursor:
                cursor.execute("SELECT pg_backend_pid()")
                backend_pid.append(cursor.fetchone()[0])
            started.set()
            try:
                services.update_commitment(
                    owners[0],
                    commitment.id,
                    1,
                    "Attempt add",
                    first.id,
                    third.id,
                    None,
                    [first.id, third.id],
                )
            except Exception:
                return "rejected"
            return "updated"
        finally:
            connection.close()

    with ThreadPoolExecutor(max_workers=1) as pool:
        with transaction.atomic():
            Party.objects.select_for_update().get(pk=third.pk)
            future = pool.submit(add_person)
            assert started.wait(10)
            wait_for_database_lock(
                future, backend_pid, "Edit did not wait for Party lock"
            )
            services.set_person_archived(owners[0], third.id, 1, True)
        assert future.result(timeout=10) == "rejected"
    commitment.refresh_from_db()
    assert commitment.version == 1
    assert commitment.owed_to_id == second.id
    assert set(
        CommitmentPerson.objects.filter(
            commitment=commitment, archived_at__isnull=True
        ).values_list("person_id", flat=True)
    ) == {first.id}


@pytest.mark.django_db(transaction=True)
def test_archive_waits_for_edit_then_preserves_new_link(owners):
    first, second, third = people(owners)
    commitment = make_commitment(owners[0], first, second, [first.id])
    started = Event()
    backend_pid = []

    def archive_new_person():
        close_old_connections()
        try:
            with connection.cursor() as cursor:
                cursor.execute("SELECT pg_backend_pid()")
                backend_pid.append(cursor.fetchone()[0])
            started.set()
            services.set_person_archived(owners[0], third.id, 1, True)
            return "archived"
        finally:
            connection.close()

    with ThreadPoolExecutor(max_workers=1) as pool:
        with transaction.atomic():
            services._lock_parties(
                first.workspace, [first.id, second.id, third.id], require_active=True
            )
            services.update_commitment(
                owners[0],
                commitment.id,
                1,
                "Edited before archive",
                first.id,
                third.id,
                None,
                [first.id, third.id],
            )
            future = pool.submit(archive_new_person)
            assert started.wait(10)
            wait_for_database_lock(future, backend_pid, "Archive did not wait for edit")
        assert future.result(timeout=10) == "archived"
    commitment.refresh_from_db()
    assert commitment.version == 2
    assert commitment.owed_to_id == third.id
    assert CommitmentPerson.objects.filter(
        commitment=commitment, person=third, archived_at__isnull=True
    ).exists()


@pytest.mark.django_db(transaction=True)
def test_additive_migration_preserves_stage_five_records(owners):
    first, second, _ = people(owners)
    interaction = services.create_interaction(
        owners[0],
        "2026-01-01T00:00:00+00:00",
        "Prior-stage record",
        [first.id, second.id],
    )
    from django.db.migrations.executor import MigrationExecutor

    executor = MigrationExecutor(connection)
    executor.migrate([("crm", "0006_interaction_interactionparticipant_and_more")])
    try:
        assert "crm_commitment" not in connection.introspection.table_names()
        assert Interaction.objects.filter(id=interaction.id).exists()
    finally:
        executor = MigrationExecutor(connection)
        executor.migrate(executor.loader.graph.leaf_nodes())
    assert Interaction.objects.filter(id=interaction.id).exists()
