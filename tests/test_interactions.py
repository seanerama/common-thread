from concurrent.futures import ThreadPoolExecutor
from datetime import UTC, datetime
from threading import Barrier, Event
from time import monotonic, sleep

import pytest
from django.core.exceptions import ValidationError
from django.db import IntegrityError, close_old_connections, connection, transaction
from django.test import Client

from crm import services
from crm.models import (
    ContextNote,
    Interaction,
    InteractionParticipant,
    InteractionRevision,
    InteractionRevisionParticipant,
    Membership,
    Party,
    Relationship,
)

pytestmark = pytest.mark.django_db


@pytest.fixture(autouse=True)
def interactions_on(settings):
    settings.INTERACTIONS_ENABLED = True


def csrf_post(client, path, **data):
    return client.post(path, data, HTTP_X_CSRFTOKEN=client.cookies["csrftoken"].value)


def parties(owners):
    first = services.create_person(owners[0], "Fictional Alex")
    second = services.create_person(owners[0], "Fictional Blair")
    third = services.create_person(owners[0], "Fictional Casey")
    return first, second, third


def make_interaction(user, participant_ids, **overrides):
    values = {
        "occurred_at": "2026-09-16T10:30:00-05:00",
        "body": "Fictional shared conversation",
    }
    values.update(overrides)
    return services.create_interaction(user, participant_ids=participant_ids, **values)


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


def test_create_one_shared_interaction_and_correct_complete_snapshot(
    authenticated, owners
):
    first, second, third = parties(owners)
    created = csrf_post(
        authenticated,
        "/interactions/new/",
        occurred_at="2026-09-16T10:30:00-05:00",
        body="Original <conversation>",
        participant_ids=[first.id, second.id],
    )
    interaction = Interaction.objects.get()
    assert created.status_code == 303
    assert created["Location"] == f"/interactions/{interaction.id}/"
    assert interaction.occurred_at == datetime(2026, 9, 16, 15, 30, tzinfo=UTC)
    assert interaction.authored_by == owners[0]
    assert set(InteractionParticipant.objects.values_list("party_id", flat=True)) == {
        first.id,
        second.id,
    }

    corrected = csrf_post(
        authenticated,
        f"/interactions/{interaction.id}/edit/",
        expected_version=1,
        occurred_at="2026-09-17T08:00:00+02:00",
        body="Corrected conversation",
        participant_ids=[first.id, third.id],
    )
    assert corrected.status_code == 303
    interaction.refresh_from_db()
    assert interaction.version == 2
    assert interaction.authored_by == owners[0]
    assert interaction.occurred_at == datetime(2026, 9, 17, 6, 0, tzinfo=UTC)
    assert set(interaction.participant_links.values_list("party_id", flat=True)) == {
        first.id,
        third.id,
    }
    revision = InteractionRevision.objects.get(interaction=interaction)
    assert revision.version == 1
    assert revision.body == "Original <conversation>"
    assert revision.occurred_at == datetime(2026, 9, 16, 15, 30, tzinfo=UTC)
    assert revision.authored_by == owners[0] and revision.edited_by == owners[0]
    assert revision.edited_at is not None
    assert set(revision.participant_links.values_list("party_id", flat=True)) == {
        first.id,
        second.id,
    }
    detail = authenticated.get(f"/interactions/{interaction.id}/")
    assert "Corrected conversation" in detail.content.decode()
    history = authenticated.get(f"/interactions/{interaction.id}/history/")
    assert "Original &lt;conversation&gt;" in history.content.decode()
    assert "Fictional Blair" in history.content.decode()


def test_participant_panels_replacement_ordering_and_query_validation(
    authenticated, owners
):
    first, second, third = parties(owners)
    older = make_interaction(
        owners[0], [first.id, second.id], occurred_at="2026-01-01T12:00:00+00:00"
    )
    newer = make_interaction(
        owners[0], [first.id, second.id], occurred_at="2026-02-01T12:00:00+00:00"
    )
    services.update_interaction(
        owners[0], newer.id, 1, newer.occurred_at, "Replacement", [first.id, third.id]
    )
    assert InteractionParticipant.all_objects.filter(
        interaction=newer, party=second, archived_at__isnull=False
    ).exists()
    assert [row.id for row in services.interaction_panels(owners[0], first.id)] == [
        newer.id,
        older.id,
    ]
    assert [row.id for row in services.interaction_panels(owners[0], second.id)] == [
        older.id
    ]
    assert [row.id for row in services.interaction_panels(owners[0], third.id)] == [
        newer.id
    ]
    for party, visible in ((first, 2), (second, 1), (third, 1)):
        body = authenticated.get(f"/people/{party.id}/").content.decode()
        assert body.count("View interaction") == visible
    for query in (
        "interactions_page=0",
        "interactions_page=nope",
        "interactions_page=1&interactions_page=2",
        "unknown=1",
    ):
        assert authenticated.get(f"/people/{first.id}/?{query}").status_code == 400


def test_validation_max_unicode_uniqueness_and_database_scope(authenticated, owners):
    first, second, _ = parties(owners)
    body = "\U0001f642" * 20000
    interaction = make_interaction(owners[0], [first.id], body=body)
    assert interaction.body == body
    response = csrf_post(
        authenticated,
        "/interactions/new/",
        occurred_at="2026-01-01T12:00:00+00:00",
        body=body,
        participant_ids=[second.id],
    )
    assert response.status_code == 303
    created_id = response["Location"].split("/")[-2]
    assert Interaction.objects.get(pk=created_id).body == body
    for occurred_at in ("2026-01-01T12:00:00", "not-a-time"):
        with pytest.raises(ValidationError):
            make_interaction(owners[0], [first.id], occurred_at=occurred_at)
    for invalid_body in ("", "x" * 20001, "bad\x00text", "bad\ud800text"):
        with pytest.raises(ValidationError):
            make_interaction(owners[0], [first.id], body=invalid_body)
    for invalid_participants in ([], [first.id, first.id], str(first.id)):
        with pytest.raises(ValidationError):
            make_interaction(owners[0], invalid_participants)
    foreign = services.create_person(owners[1], "Private participant")
    with pytest.raises(Exception):
        make_interaction(owners[0], [first.id, foreign.id])
    foreign_response = csrf_post(
        authenticated,
        "/interactions/new/",
        occurred_at="2026-01-01T12:00:00+00:00",
        body="Forged foreign participant",
        participant_ids=[foreign.id],
    )
    assert foreign_response.status_code == 400
    assert "Private participant" not in foreign_response.content.decode()
    with pytest.raises(IntegrityError), transaction.atomic():
        InteractionParticipant.objects.create(
            workspace=first.workspace, interaction=interaction, party=foreign
        )
    InteractionParticipant.objects.create(
        workspace=first.workspace, interaction=interaction, party=second
    )
    with pytest.raises(IntegrityError), transaction.atomic():
        InteractionParticipant.objects.create(
            workspace=first.workspace, interaction=interaction, party=second
        )


def test_selector_search_pagination_and_selected_participants_survive_pages(
    authenticated, owners
):
    first, second, _ = parties(owners)
    for index in range(55):
        services.create_person(owners[0], f"AAA Interaction selector {index:02}")
    first_page = authenticated.get("/interactions/new/?page=1")
    assert first_page.status_code == 200
    assert "Next parties" in first_page.content.decode()
    selected_url = f"/interactions/new/?q=Fictional+Blair&selected={first.id}"
    selected_body = authenticated.get(selected_url).content.decode()
    assert f'value="{first.id}" checked' in selected_body
    assert f'value="{second.id}"' in selected_body
    created = csrf_post(
        authenticated,
        selected_url,
        occurred_at="2026-01-01T12:00:00+00:00",
        body="Accumulated selector participants",
        participant_ids=[first.id, second.id],
    )
    assert created.status_code == 303
    interaction = Interaction.objects.get(body="Accumulated selector participants")
    assert set(interaction.participant_links.values_list("party_id", flat=True)) == {
        first.id,
        second.id,
    }
    for query in ("page=0", "page=nope", "q=a&q=b", "unknown=x"):
        assert authenticated.get(f"/interactions/new/?{query}").status_code == 400


def test_interaction_pagination_preserves_relationship_pages(
    authenticated, owners, settings
):
    settings.RELATIONSHIPS_ENABLED = True
    first, second, _ = parties(owners)
    Relationship.objects.bulk_create(
        [
            Relationship(
                workspace=first.workspace,
                from_party=first,
                to_party=second,
                kind="other",
            )
            for _ in range(51)
        ]
    )
    interactions = Interaction.objects.bulk_create(
        [
            Interaction(
                workspace=first.workspace,
                occurred_at=datetime(2026, 1, 1, tzinfo=UTC),
                body=f"Pagination interaction {index}",
                authored_by=owners[0],
            )
            for index in range(51)
        ]
    )
    InteractionParticipant.objects.bulk_create(
        [
            InteractionParticipant(
                workspace=first.workspace, interaction=row, party=first
            )
            for row in interactions
        ]
    )
    body = authenticated.get(
        f"/people/{first.id}/?relationships_page=1&relationships_ended_page=1&interactions_page=1"
    ).content.decode()
    assert (
        "relationships_page=1&amp;relationships_ended_page=1&amp;interactions_page=2"
        in body
    )
    assert (
        "relationships_page=2&amp;relationships_ended_page=1&amp;interactions_page=1"
        in body
    )
    settings.RELATIONSHIPS_ENABLED = False
    interactions_only = authenticated.get(
        f"/people/{first.id}/?interactions_page=1"
    ).content.decode()
    assert 'href="?interactions_page=2"' in interactions_only
    assert (
        authenticated.get(f"/people/{first.id}/?interactions_page=2").status_code == 200
    )


def test_stale_forged_unknown_and_rollback_leave_no_partial_correction(
    authenticated, owners, monkeypatch
):
    first, second, third = parties(owners)
    interaction = make_interaction(owners[0], [first.id, second.id])
    edit_path = f"/interactions/{interaction.id}/edit/"
    assert (
        csrf_post(
            authenticated,
            edit_path,
            expected_version=1,
            occurred_at="2026-09-16T15:30:00+00:00",
            body="Accepted",
            participant_ids=[first.id, second.id],
        ).status_code
        == 303
    )
    stale = csrf_post(
        authenticated,
        edit_path,
        expected_version=1,
        occurred_at="2026-09-16T15:30:00+00:00",
        body="Submitted <draft>",
        participant_ids=[first.id, third.id],
    )
    assert stale.status_code == 409
    assert "Submitted &lt;draft&gt;" in stale.content.decode()
    interaction.refresh_from_db()
    assert interaction.body == "Accepted" and interaction.version == 2
    assert InteractionRevision.objects.filter(interaction=interaction).count() == 1
    assert (
        csrf_post(
            authenticated,
            edit_path,
            expected_version=2,
            occurred_at="2026-09-16T15:30:00+00:00",
            body="Forged",
            participant_ids=[first.id],
            authored_by=owners[1].id,
        ).status_code
        == 400
    )
    repeated = authenticated.post(
        edit_path,
        f"expected_version=2&occurred_at=2026-09-16T15%3A30%3A00%2B00%3A00&body=a&body=b&participant_ids={first.id}",
        content_type="application/x-www-form-urlencoded",
        HTTP_X_CSRFTOKEN=authenticated.cookies["csrftoken"].value,
    )
    assert repeated.status_code == 400

    original_bulk_create = InteractionRevisionParticipant.objects.bulk_create

    def fail_revision_participants(*args, **kwargs):
        raise RuntimeError("injected revision participant failure")

    monkeypatch.setattr(
        InteractionRevisionParticipant.objects,
        "bulk_create",
        fail_revision_participants,
    )
    with pytest.raises(RuntimeError):
        services.update_interaction(
            owners[0],
            interaction.id,
            2,
            interaction.occurred_at,
            "Must roll back",
            [first.id, third.id],
        )
    monkeypatch.setattr(
        InteractionRevisionParticipant.objects, "bulk_create", original_bulk_create
    )
    interaction.refresh_from_db()
    assert interaction.body == "Accepted" and interaction.version == 2
    assert set(interaction.participant_links.values_list("party_id", flat=True)) == {
        first.id,
        second.id,
    }
    assert InteractionRevision.objects.filter(interaction=interaction).count() == 1


def test_archived_participants_history_auth_flags_csrf_and_context_note_compatibility(
    authenticated, owners, settings
):
    first, second, third = parties(owners)
    interaction = make_interaction(owners[0], [first.id, second.id])
    services.set_person_archived(owners[0], second.id, 1, True)
    retained = services.update_interaction(
        owners[0],
        interaction.id,
        1,
        interaction.occurred_at,
        "Archived participant retained",
        [first.id, second.id],
    )
    updated = services.update_interaction(
        owners[0],
        interaction.id,
        retained.version,
        interaction.occurred_at,
        "Historical",
        [first.id],
    )
    assert updated.version == 3
    assert InteractionRevisionParticipant.objects.filter(party=second).exists()
    with pytest.raises(ValidationError):
        services.update_interaction(
            owners[0],
            updated.id,
            updated.version,
            updated.occurred_at,
            "No relink",
            [first.id, second.id],
        )
    services.set_person_archived(owners[0], third.id, 1, True)
    with pytest.raises(Exception):
        make_interaction(owners[0], [third.id])

    note = ContextNote.objects.create(
        workspace=first.workspace,
        person_id=first.id,
        body="Existing note",
        source="operator",
        authored_by=owners[0],
    )
    assert note.source_interaction_id is None
    foreign_client = Client(enforce_csrf_checks=True)
    foreign_client.force_login(owners[1])
    assert foreign_client.get(f"/interactions/{interaction.id}/").status_code == 404
    assert (
        foreign_client.get(f"/interactions/{interaction.id}/history/").status_code
        == 404
    )
    assert Client().get(f"/interactions/{interaction.id}/").status_code == 302
    assert (
        authenticated.post(
            f"/interactions/{interaction.id}/edit/",
            {"expected_version": 2},
        ).status_code
        == 403
    )
    Membership.objects.filter(user=owners[0]).update(active=False)
    assert authenticated.get(f"/interactions/{interaction.id}/").status_code == 302
    Membership.objects.filter(user=owners[0]).update(active=True)
    settings.INTERACTIONS_ENABLED = False
    for path in (
        "/interactions/new/",
        f"/interactions/{interaction.id}/",
        f"/interactions/{interaction.id}/edit/",
        f"/interactions/{interaction.id}/history/",
    ):
        assert authenticated.get(path).status_code == 404
        assert authenticated.post(path, {}).status_code == 404
    assert Interaction.objects.filter(pk=interaction.pk).exists()


def test_deactivated_original_author_and_database_revision_scope_are_retained(owners):
    first, second, _ = parties(owners)
    interaction = make_interaction(owners[0], [first.id, second.id])
    services.update_interaction(
        owners[0], interaction.id, 1, interaction.occurred_at, "Corrected", [first.id]
    )
    owners[0].is_active = False
    owners[0].save(update_fields=["is_active"])
    revision = InteractionRevision.objects.select_related("authored_by").get()
    assert revision.authored_by.username == "fictional_owner"
    assert revision.authored_by.is_active is False

    foreign = services.create_person(owners[1], "Foreign revision party")
    with pytest.raises(IntegrityError), transaction.atomic():
        InteractionRevision.objects.create(
            workspace=foreign.workspace,
            interaction=interaction,
            occurred_at=interaction.occurred_at,
            body="Wrong workspace revision",
            version=99,
            authored_by=owners[0],
            edited_by=owners[0],
            edited_at=datetime.now(UTC),
        )
    with pytest.raises(IntegrityError), transaction.atomic():
        InteractionRevisionParticipant.objects.create(
            workspace=foreign.workspace,
            revision=revision,
            party=foreign,
        )


@pytest.mark.django_db(transaction=True)
def test_create_waits_for_archive_and_fails_without_partial_interaction(owners):
    first, second, _ = parties(owners)
    started = Event()
    backend_pid = []

    def create_shared():
        close_old_connections()
        try:
            with connection.cursor() as cursor:
                cursor.execute("SELECT pg_backend_pid()")
                backend_pid.append(cursor.fetchone()[0])
            started.set()
            try:
                make_interaction(owners[0], [first.id, second.id])
            except Exception:
                return "rejected"
            return "created"
        finally:
            connection.close()

    with ThreadPoolExecutor(max_workers=1) as pool:
        with transaction.atomic():
            Party.objects.select_for_update().get(pk=second.pk)
            future = pool.submit(create_shared)
            assert started.wait(10)
            wait_for_database_lock(
                future, backend_pid, "Interaction creation did not wait for Party lock"
            )
            services.set_person_archived(owners[0], second.id, 1, True)
        assert future.result(timeout=10) == "rejected"
    assert not Interaction.objects.exists()
    assert not InteractionParticipant.objects.exists()


@pytest.mark.django_db(transaction=True)
def test_archive_waits_for_creation_then_preserves_shared_interaction(owners):
    first, second, _ = parties(owners)
    started = Event()
    backend_pid = []

    def archive_second():
        close_old_connections()
        try:
            with connection.cursor() as cursor:
                cursor.execute("SELECT pg_backend_pid()")
                backend_pid.append(cursor.fetchone()[0])
            started.set()
            services.set_person_archived(owners[0], second.id, 1, True)
            return "archived"
        finally:
            connection.close()

    with ThreadPoolExecutor(max_workers=1) as pool:
        with transaction.atomic():
            locked = services._lock_parties(
                first.workspace, [first.id, second.id], require_active=True
            )
            interaction = Interaction.objects.create(
                workspace=first.workspace,
                occurred_at=datetime(2026, 1, 1, tzinfo=UTC),
                body="Created before archive",
                authored_by=owners[0],
            )
            InteractionParticipant.objects.bulk_create(
                [
                    InteractionParticipant(
                        workspace=first.workspace,
                        interaction=interaction,
                        party=locked[party_id],
                    )
                    for party_id in (first.id, second.id)
                ]
            )
            future = pool.submit(archive_second)
            assert started.wait(10)
            wait_for_database_lock(
                future, backend_pid, "Party archive did not wait for creation locks"
            )
        assert future.result(timeout=10) == "archived"
    assert Interaction.objects.filter(pk=interaction.pk).exists()
    assert interaction.participant_links.count() == 2


@pytest.mark.django_db(transaction=True)
def test_update_waits_for_archive_and_rejects_new_archived_participant(owners):
    first, second, third = parties(owners)
    interaction = make_interaction(owners[0], [first.id, second.id])
    started = Event()
    backend_pid = []

    def replace_participant():
        close_old_connections()
        try:
            with connection.cursor() as cursor:
                cursor.execute("SELECT pg_backend_pid()")
                backend_pid.append(cursor.fetchone()[0])
            started.set()
            try:
                services.update_interaction(
                    owners[0],
                    interaction.id,
                    1,
                    interaction.occurred_at,
                    "Attempted replacement",
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
            future = pool.submit(replace_participant)
            assert started.wait(10)
            wait_for_database_lock(
                future, backend_pid, "Interaction update did not wait for Party lock"
            )
            services.set_person_archived(owners[0], third.id, 1, True)
        assert future.result(timeout=10) == "rejected"
    interaction.refresh_from_db()
    assert interaction.version == 1
    assert InteractionRevision.objects.filter(interaction=interaction).count() == 0
    assert set(interaction.participant_links.values_list("party_id", flat=True)) == {
        first.id,
        second.id,
    }


@pytest.mark.django_db(transaction=True)
def test_archive_waits_for_update_then_retains_corrected_history(owners):
    first, second, third = parties(owners)
    interaction = make_interaction(owners[0], [first.id, second.id])
    started = Event()
    backend_pid = []

    def archive_third():
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
            updated = services.update_interaction(
                owners[0],
                interaction.id,
                1,
                interaction.occurred_at,
                "Updated before archive",
                [first.id, third.id],
            )
            future = pool.submit(archive_third)
            assert started.wait(10)
            wait_for_database_lock(
                future, backend_pid, "Party archive did not wait for update locks"
            )
        assert future.result(timeout=10) == "archived"
    updated.refresh_from_db()
    assert updated.version == 2
    assert set(updated.participant_links.values_list("party_id", flat=True)) == {
        first.id,
        third.id,
    }
    assert InteractionRevisionParticipant.objects.filter(
        revision__interaction=interaction, party=second
    ).exists()


@pytest.mark.django_db(transaction=True)
def test_concurrent_corrections_allow_exactly_one_version(owners):
    first, second, _ = parties(owners)
    interaction = make_interaction(owners[0], [first.id, second.id])
    barrier = Barrier(2)

    def correct(body):
        close_old_connections()
        try:
            barrier.wait(timeout=10)
            try:
                services.update_interaction(
                    owners[0],
                    interaction.id,
                    1,
                    interaction.occurred_at,
                    body,
                    [first.id, second.id],
                )
            except Exception:
                return "conflict"
            return "updated"
        finally:
            connection.close()

    with ThreadPoolExecutor(max_workers=2) as pool:
        results = list(pool.map(correct, ("Correction A", "Correction B")))
    assert sorted(results) == ["conflict", "updated"]
    interaction.refresh_from_db()
    assert interaction.version == 2
    assert InteractionRevision.objects.filter(interaction=interaction).count() == 1


@pytest.mark.django_db(transaction=True)
def test_additive_migration_preserves_stage_four_records(owners):
    first, second, _ = parties(owners)
    relationship = services.create_relationship(
        owners[0], first.id, second.id, "other", None, None, None
    )
    from django.db.migrations.executor import MigrationExecutor

    executor = MigrationExecutor(connection)
    executor.migrate([("crm", "0005_relationship")])
    try:
        assert "crm_interaction" not in connection.introspection.table_names()
        assert Party.objects.filter(id=first.id).exists()
    finally:
        executor = MigrationExecutor(connection)
        executor.migrate(executor.loader.graph.leaf_nodes())
    from crm.models import Relationship

    assert Relationship.objects.filter(id=relationship.id).exists()
