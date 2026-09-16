from concurrent.futures import ThreadPoolExecutor
from threading import Event
from time import monotonic, sleep
from unittest.mock import patch
from uuid import uuid4

import pytest
from django.core.exceptions import ValidationError
from django.db import IntegrityError, close_old_connections, connection, transaction
from django.db.models.deletion import ProtectedError
from django.http import Http404
from django.test import Client
from django.utils import timezone

from crm import services
from crm.models import ContextNote, ContextNoteRevision, Membership, Party, User

pytestmark = pytest.mark.django_db


@pytest.fixture(autouse=True)
def enabled(settings):
    settings.CONTEXT_NOTES_ENABLED = True
    settings.PEOPLE_MANAGEMENT_ENABLED = True


def post(client, path, **data):
    return client.post(path, data, HTTP_X_CSRFTOKEN=client.cookies["csrftoken"].value)


def create_note(owner, body="Fictional context", source="Author's recollection"):
    person = services.create_person(owner, "Fictional person")
    note = services.create_context_note(owner, person.id, 1, body, source)
    person.refresh_from_db()
    return person, note


def paths(person, note):
    base = f"/people/{person.id}/notes/"
    return base + "new/", base + f"{note.id}/edit/", base + f"{note.id}/history/"


def test_create_correct_and_history_preserve_provenance(authenticated, owners):
    person = services.create_person(owners[0], "Fictional person")
    path = f"/people/{person.id}/notes/new/"
    form = authenticated.get(path)
    assert form.status_code == 200
    assert 'name="expected_version"' in form.content.decode()
    response = post(
        authenticated,
        path,
        expected_version=1,
        body="<script>fictional café</script>",
        source="<b>Conversation</b>",
    )
    assert response.status_code == 303
    assert response["Location"] == f"/people/{person.id}/"
    note = ContextNote.objects.get(person=person)
    assert note.authored_by_id == owners[0].id
    assert note.source_interaction_id is None and note.version == 1
    person.refresh_from_db()
    assert person.version == 2
    editor = User.objects.create_user(username="fictional_editor")
    Membership.objects.filter(user=owners[0]).update(user=editor)
    owners[0].is_active = False
    owners[0].save(update_fields=["is_active"])
    authenticated.force_login(editor)
    before = timezone.now()
    response = post(
        authenticated,
        paths(person, note)[1],
        expected_version=1,
        body="Corrected <em>context</em>",
        source="Follow-up <source>",
    )
    assert response.status_code == 303
    note.refresh_from_db()
    assert (note.body, note.source, note.version, note.authored_by_id) == (
        "Corrected <em>context</em>",
        "Follow-up <source>",
        2,
        owners[0].id,
    )
    revision = ContextNoteRevision.objects.get(note=note)
    assert (revision.body, revision.source, revision.version) == (
        "<script>fictional café</script>",
        "<b>Conversation</b>",
        1,
    )
    assert revision.authored_by_id == owners[0].id
    assert revision.edited_by_id == editor.id
    assert before <= revision.edited_at <= timezone.now()
    assert revision.workspace_id == person.workspace_id
    detail = authenticated.get(f"/people/{person.id}/").content.decode()
    assert "Corrected &lt;em&gt;context&lt;/em&gt;" in detail
    assert "Follow-up &lt;source&gt;" in detail
    history = authenticated.get(paths(person, note)[2]).content.decode()
    assert "&lt;script&gt;fictional café&lt;/script&gt;" in history
    assert "&lt;b&gt;Conversation&lt;/b&gt;" in history
    assert "<script>fictional" not in history
    assert owners[0].username in history and editor.username in history
    with pytest.raises(ProtectedError):
        owners[0].delete()
    assert User.objects.filter(pk=owners[0].pk, is_active=False).exists()
    assert ContextNote.objects.get(pk=note.pk).authored_by_id == owners[0].pk
    assert (
        ContextNoteRevision.objects.get(pk=revision.pk).authored_by_id == owners[0].pk
    )


def test_stale_and_failed_correction_leave_no_partial_history(authenticated, owners):
    person, note = create_note(owners[0])
    edit = paths(person, note)[1]
    assert (
        post(
            authenticated, edit, expected_version=1, body="Accepted", source="Verified"
        ).status_code
        == 303
    )
    response = post(
        authenticated,
        edit,
        expected_version=1,
        body="Rejected <draft>",
        source="Draft <source>",
    )
    assert response.status_code == 409
    assert "Rejected &lt;draft&gt;" in response.content.decode()
    assert "Draft &lt;source&gt;" in response.content.decode()
    note.refresh_from_db()
    assert (note.body, note.version) == ("Accepted", 2)
    assert ContextNoteRevision.objects.filter(note=note).count() == 1
    with patch.object(ContextNote, "save", side_effect=IntegrityError("injected")):
        with pytest.raises(IntegrityError):
            services.update_context_note(
                owners[0], person.id, note.id, 2, "Failed", "Failure source"
            )
    note.refresh_from_db()
    assert (note.body, note.source, note.version) == ("Accepted", "Verified", 2)
    assert ContextNoteRevision.objects.filter(note=note).count() == 1


@pytest.mark.parametrize(
    "values",
    [
        {"body": ""},
        {"body": "x" * 20001},
        {"body": "\x00"},
        {"source": ""},
        {"source": " "},
        {"source": "x" * 501},
        {"source": "\x00"},
        {"expected_version": "9" * 5000},
    ],
)
def test_invalid_forms_are_atomic(authenticated, owners, values):
    person, note = create_note(owners[0])
    for path, version in zip(paths(person, note)[:2], (2, 1), strict=True):
        data = dict(expected_version=version, body="New context", source="New source")
        data.update(values)
        assert post(authenticated, path, **data).status_code == 200
    person.refresh_from_db()
    note.refresh_from_db()
    assert person.version == 2 and note.version == 1
    assert ContextNote.objects.count() == 1
    assert not ContextNoteRevision.objects.exists()


def test_unicode_limits_and_surrogates(owners):
    person, note = create_note(owners[0], body="🌻" * 20000, source="é" * 500)
    assert len(note.body) == 20000 and len(note.source) == 500
    for body, source in (("\ud800", "Valid"), ("Valid", "\udfff")):
        with pytest.raises(ValidationError):
            services.update_context_note(owners[0], person.id, note.id, 1, body, source)
    assert not ContextNoteRevision.objects.exists()


@pytest.mark.parametrize(
    "field",
    [
        "workspace_id",
        "person_id",
        "authored_by",
        "authored_by_id",
        "source_interaction_id",
        "note_id",
        "edited_by",
    ],
)
def test_forged_fields_rejected(authenticated, owners, field):
    person, note = create_note(owners[0])
    for path, version in zip(paths(person, note)[:2], (2, 1), strict=True):
        data = dict(expected_version=version, body="Forged", source="Forged source")
        data[field] = str(uuid4())
        assert post(authenticated, path, **data).status_code == 400
    note.refresh_from_db()
    person.refresh_from_db()
    assert note.version == 1 and person.version == 2
    assert ContextNote.objects.count() == 1
    assert not ContextNoteRevision.objects.exists()


def test_auth_csrf_foreign_parent_history_and_revocation(authenticated, owners):
    person, note = create_note(owners[0])
    other, other_note = create_note(owners[0])
    foreign, foreign_note = create_note(owners[1])
    services.update_context_note(
        owners[1], foreign.id, foreign_note.id, 1, "Secret", "Secret source"
    )
    for target in (other_note.id, foreign_note.id, uuid4(), "invalid"):
        for suffix in ("edit/", "history/"):
            url = f"/people/{person.id}/notes/{target}/{suffix}"
            assert authenticated.get(url).status_code == 404
            if suffix == "edit/":
                assert (
                    post(
                        authenticated,
                        url,
                        expected_version=1,
                        body="Forged",
                        source="Forged",
                    ).status_code
                    == 404
                )
    for url in paths(foreign, foreign_note):
        assert authenticated.get(url).status_code == 404
    with pytest.raises(Http404):
        list(services.context_note_history(owners[0], foreign.id, foreign_note.id))
    with pytest.raises(Http404):
        list(services.list_context_notes(owners[0], foreign.id))
    for url in paths(person, note):
        assert Client().get(url).status_code == 302
    for url in paths(person, note)[:2]:
        assert (
            authenticated.post(
                url,
                {
                    "body": "No CSRF",
                    "source": "No CSRF",
                    "expected_version": 1,
                },
            ).status_code
            == 403
        )
    assert authenticated.post(paths(person, note)[2]).status_code == 403
    Membership.objects.filter(user=owners[0]).update(active=False)
    for url in paths(person, note):
        assert authenticated.get(url).status_code == 302
    assert (
        post(
            authenticated,
            paths(person, note)[1],
            expected_version=1,
            body="Revoked",
            source="Revoked",
        ).status_code
        == 302
    )
    note.refresh_from_db()
    assert note.version == 1


def test_archive_preserves_readable_notes_and_history(authenticated, owners):
    person, note = create_note(owners[0])
    services.update_context_note(
        owners[0], person.id, note.id, 1, "Current context", "Current source"
    )
    services.set_person_archived(owners[0], person.id, 2, True)
    assert (
        "Current context" in authenticated.get(f"/people/{person.id}/").content.decode()
    )
    assert (
        "Fictional context"
        in authenticated.get(paths(person, note)[2]).content.decode()
    )
    for url, version in zip(paths(person, note)[:2], (3, 2), strict=True):
        assert (
            post(
                authenticated,
                url,
                expected_version=version,
                body="Blocked",
                source="Blocked",
            ).status_code
            == 200
        )
    note.refresh_from_db()
    assert note.version == 2 and note.body == "Current context"
    assert ContextNote.objects.count() == 1
    assert ContextNoteRevision.objects.count() == 1


def test_flags_independent_and_preserve_data(authenticated, owners, settings):
    person, note = create_note(owners[0])
    settings.PEOPLE_MANAGEMENT_ENABLED = False
    assert authenticated.get(paths(person, note)[0]).status_code == 200
    assert (
        post(
            authenticated,
            paths(person, note)[1],
            expected_version=1,
            body="Independent context",
            source="Independent source",
        ).status_code
        == 303
    )
    assert (
        "Independent context"
        in authenticated.get(f"/people/{person.id}/").content.decode()
    )
    settings.CONTEXT_NOTES_ENABLED = False
    for url in paths(person, note):
        for method in (authenticated.get, authenticated.post):
            assert method(url).status_code == 404
    detail = authenticated.get(f"/people/{person.id}/").content.decode()
    assert "Independent context" not in detail
    assert authenticated.get(f"/api/v1/people/{person.id}/").status_code == 200
    assert ContextNote.objects.count() == 1 and ContextNoteRevision.objects.count() == 1
    settings.CONTEXT_NOTES_ENABLED = True
    assert (
        "Independent context"
        in authenticated.get(f"/people/{person.id}/").content.decode()
    )


def test_database_rejects_cross_workspace_parents_and_revisions(owners):
    person, note = create_note(owners[0])
    foreign, _ = create_note(owners[1])
    with pytest.raises(IntegrityError), transaction.atomic():
        ContextNote.objects.create(
            workspace=foreign.workspace,
            person=person,
            body="Invalid",
            source="Invalid",
            authored_by=owners[0],
        )
    with pytest.raises(IntegrityError), transaction.atomic():
        ContextNoteRevision.objects.create(
            workspace=foreign.workspace,
            note=note,
            body=note.body,
            source=note.source,
            version=1,
            authored_by=owners[0],
            edited_by=owners[0],
            edited_at=timezone.now(),
        )


@pytest.mark.django_db(transaction=True)
@pytest.mark.parametrize("first", ["edit", "archive"])
def test_concurrent_correction_waits_for_parent_and_has_no_partial_history(
    owners, first
):
    person, note = create_note(owners[0])
    client = Client(enforce_csrf_checks=True)
    client.force_login(owners[0])
    client.get("/people/new/")
    started = Event()
    pids = []

    def correction():
        close_old_connections()
        try:
            with connection.cursor() as cursor:
                cursor.execute("SELECT pg_backend_pid()")
                pids.append(cursor.fetchone()[0])
            started.set()
            return post(
                client,
                paths(person, note)[1],
                expected_version=1,
                body="Concurrent draft",
                source="Concurrent source",
            ).status_code
        finally:
            connection.close()

    with ThreadPoolExecutor(max_workers=1) as pool:
        with transaction.atomic():
            Party.objects.select_for_update().get(pk=person.pk)
            future = pool.submit(correction)
            assert started.wait(10)
            deadline = monotonic() + 5
            while monotonic() < deadline:
                with connection.cursor() as cursor:
                    cursor.execute(
                        "SELECT wait_event_type FROM pg_stat_activity WHERE pid = %s",
                        pids,
                    )
                    row = cursor.fetchone()
                if row and row[0] == "Lock":
                    break
                assert not future.done(), "Correction bypassed the parent lock"
                sleep(0.01)
            else:
                pytest.fail("Correction did not wait for the database parent lock")
            if first == "edit":
                services.update_context_note(
                    owners[0], person.id, note.id, 1, "Winning edit", "Winning source"
                )
            else:
                services.set_person_archived(owners[0], person.id, 2, True)
        assert future.result(timeout=10) == (409 if first == "edit" else 200)
    note.refresh_from_db()
    assert note.body == ("Winning edit" if first == "edit" else "Fictional context")
    assert note.version == (2 if first == "edit" else 1)
    assert ContextNoteRevision.objects.filter(note=note).count() == (first == "edit")


def test_stale_parent_create_and_duplicate_fields_do_not_write(authenticated, owners):
    person, note = create_note(owners[0])
    response = post(
        authenticated,
        paths(person, note)[0],
        expected_version=1,
        body="Stale <body>",
        source="Stale source",
    )
    assert response.status_code == 409
    assert "Stale &lt;body&gt;" in response.content.decode()
    response = post(
        authenticated,
        paths(person, note)[1],
        expected_version=1,
        body=["First", "Second"],
        source="Ambiguous",
    )
    assert response.status_code == 400
    assert ContextNote.objects.count() == 1
    assert not ContextNoteRevision.objects.exists()
    note.refresh_from_db()
    assert note.version == 1


@pytest.mark.django_db(transaction=True)
def test_additive_note_migration_preserves_stage1_data(owners):
    from django.db.migrations.executor import MigrationExecutor

    executor = MigrationExecutor(connection)
    executor.migrate([("crm", "0002_contactpoint")])
    try:
        person = services.create_person(owners[0], "Pre-note migration person")
        point = services.create_contact_point(
            owners[0], person.id, 1, "email", "fictional@example.test", "Home"
        )
        created = point.created_at
    finally:
        executor = MigrationExecutor(connection)
        executor.migrate(executor.loader.graph.leaf_nodes())
    person.refresh_from_db()
    point.refresh_from_db()
    assert (person.display_name, person.version) == ("Pre-note migration person", 2)
    assert (point.value, point.label, point.created_at) == (
        "fictional@example.test",
        "Home",
        created,
    )
    note = services.create_context_note(
        owners[0], person.id, 2, "Post-migration context", "Recollection"
    )
    assert note.workspace_id == person.workspace_id


def test_urlencoded_maximum_unicode_note_is_accepted(authenticated, owners):
    from urllib.parse import urlencode

    person = services.create_person(owners[0], "Fictional Unicode person")
    body, source = "🌻" * 20000, "🌲" * 500
    response = authenticated.post(
        f"/people/{person.id}/notes/new/",
        urlencode({"body": body, "source": source, "expected_version": 1}),
        content_type="application/x-www-form-urlencoded",
        HTTP_X_CSRFTOKEN=authenticated.cookies["csrftoken"].value,
    )
    assert response.status_code == 303
    note = ContextNote.objects.get(person=person)
    assert (note.body, note.source) == (body, source)
