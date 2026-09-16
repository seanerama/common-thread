from concurrent.futures import ThreadPoolExecutor
from threading import Event
from time import monotonic, sleep
from uuid import uuid4

import pytest
from django.db import IntegrityError, close_old_connections, connection, transaction
from django.test import Client

from crm import services
from crm.models import ContactPoint, Membership, Party

pytestmark = pytest.mark.django_db


@pytest.fixture(autouse=True)
def enabled(settings):
    settings.PEOPLE_MANAGEMENT_ENABLED = True


def post(client, path, **data):
    return client.post(path, data, HTTP_X_CSRFTOKEN=client.cookies["csrftoken"].value)


def person(owners, index=0, name="Fictional person"):
    return services.create_person(owners[index], name)


def contact(client, p, **data):
    return post(
        client,
        f"/people/{p.id}/contact-points/new/",
        expected_version=p.version,
        kind="email",
        value=data.get("value", "shared@example.test"),
        label=data.get("label", ""),
    )


def test_shared_contact_identity_explicit_client_and_stale_atomicity(
    authenticated, owners
):
    a, b = person(owners), person(owners)
    for p in (a, b):
        assert contact(authenticated, p).status_code == 303
        p.refresh_from_db()
        assert p.version == 2 and not p.is_client
    assert a.id != b.id and ContactPoint.objects.count() == 2
    path = f"/people/{a.id}/edit/"
    assert (
        post(
            authenticated,
            path,
            expected_version=2,
            display_name="New name",
            is_client="on",
        ).status_code
        == 303
    )
    response = post(
        authenticated, path, expected_version=2, display_name="Uncommitted <name>"
    )
    assert response.status_code == 409
    assert "Uncommitted &lt;name&gt;" in response.content.decode()
    a.refresh_from_db()
    assert (a.display_name, a.version, a.is_client) == ("New name", 3, True)
    point = ContactPoint.objects.get(party=a)
    path = f"/people/{a.id}/contact-points/{point.id}/edit/"
    assert (
        post(
            authenticated,
            path,
            expected_version=1,
            kind="phone",
            value="555-0100",
            label="work",
        ).status_code
        == 303
    )
    assert (
        post(
            authenticated,
            path,
            expected_version=1,
            kind="email",
            value="stale@example.test",
        ).status_code
        == 409
    )
    point.refresh_from_db()
    assert (point.kind, point.value, point.version) == ("phone", "555-0100", 2)


def test_archive_restore_and_contact_archive_search(authenticated, owners):
    p = person(owners)
    assert contact(authenticated, p).status_code == 303
    p.refresh_from_db()
    detail = f"/people/{p.id}/"
    assert (
        post(authenticated, detail + "archive/", expected_version=2).status_code == 303
    )
    assert not authenticated.get("/people/").context["people"]
    assert authenticated.get("/people/?archived=only").context["people"]
    assert authenticated.get(detail).status_code == 200
    assert authenticated.get(f"/api/v1/people/{p.id}/").json()["data"]["archived_at"]
    p.refresh_from_db()
    assert contact(authenticated, p).status_code == 200
    point = ContactPoint.objects.get(party=p)
    assert (
        post(
            authenticated,
            detail + f"contact-points/{point.id}/edit/",
            expected_version=1,
            kind="email",
            value="blocked",
        ).status_code
        == 200
    )
    assert ContactPoint.objects.count() == 1
    assert (
        post(authenticated, detail + "restore/", expected_version=2).status_code == 409
    )
    assert (
        post(authenticated, detail + "restore/", expected_version=3).status_code == 303
    )
    assert (
        post(
            authenticated,
            detail + f"contact-points/{point.id}/archive/",
            expected_version=1,
        ).status_code
        == 303
    )
    assert not authenticated.get("/people/?q=shared@").context["people"]
    assert ContactPoint.objects.get(pk=point.pk).archived_at
    assert authenticated.get(detail + "archive/").status_code == 405


def test_search_pagination_scoping_dedup_and_validation(authenticated, owners):
    for n in range(52):
        person(owners, name=f"Match {n:03}")
    foreign = person(owners, index=1, name="Match secret")
    p = Party.objects.exclude(pk=foreign.pk).first()
    for value in ("Match-one", "Match-two"):
        services.create_contact_point(owners[0], p.id, p.version, "email", value, None)
        p.refresh_from_db()
    first = authenticated.get("/people/?q=mAtCh")
    assert len(first.context["people"]) == 50
    assert len(authenticated.get("/people/?q=Match&page=2").context["people"]) == 2
    assert "Match secret" not in first.content.decode()
    assert (
        len(authenticated.get("/people/", {"page": "0" * 100 + "1"}).context["people"])
        == 50
    )
    for page in ("3", "99999999999", "9" * 5000):
        assert not authenticated.get("/people/", {"page": page}).context["people"]
    for data in (
        {"q": "x" * 201},
        {"q": "\x00"},
        {"page": "0"},
        {"page": "-1"},
        {"page": "wat"},
        {"archived": "bad"},
    ):
        assert authenticated.get("/people/", data).status_code == 400


def test_forged_children_auth_csrf_and_revocation(authenticated, owners):
    a, b, foreign = person(owners), person(owners), person(owners, 1)
    own_point = services.create_contact_point(
        owners[0], b.id, 1, "email", "private", None
    )
    foreign_point = services.create_contact_point(
        owners[1], foreign.id, 1, "email", "private", None
    )
    for point_id in (own_point.id, foreign_point.id, uuid4(), "invalid"):
        assert (
            post(
                authenticated,
                f"/people/{a.id}/contact-points/{point_id}/edit/",
                expected_version=1,
                kind="phone",
                value="forged",
            ).status_code
            == 404
        )
    assert (
        post(
            authenticated, f"/people/{foreign.id}/archive/", expected_version=2
        ).status_code
        == 404
    )
    path = f"/people/{a.id}/edit/"
    assert (
        authenticated.post(
            path, {"expected_version": 1, "display_name": "No CSRF"}
        ).status_code
        == 403
    )
    assert Client().get(path).status_code == 302
    Membership.objects.filter(user=owners[0]).update(active=False)
    assert (
        post(
            authenticated, path, expected_version=1, display_name="revoked"
        ).status_code
        == 302
    )
    a.refresh_from_db()
    assert a.version == 1
    assert set(ContactPoint.objects.values_list("value", flat=True)) == {"private"}


def test_feature_off_routes_and_stage0_preserve_data(authenticated, owners, settings):
    p = person(owners)
    contact(authenticated, p)
    cp = ContactPoint.objects.get(party=p)
    settings.PEOPLE_MANAGEMENT_ENABLED = False
    for suffix in (
        "edit/",
        "archive/",
        "restore/",
        "contact-points/new/",
        f"contact-points/{cp.id}/edit/",
        f"contact-points/{cp.id}/archive/",
    ):
        for method in (authenticated.get, authenticated.post):
            assert method(f"/people/{p.id}/" + suffix).status_code == 404
    assert (
        len(
            authenticated.get("/people/?q=nomatch&archived=bad&page=bad").context[
                "people"
            ]
        )
        == 1
    )
    detail = authenticated.get(f"/people/{p.id}/").content.decode()
    assert "shared@example.test" not in detail and "Edit person" not in detail
    assert (
        post(authenticated, "/people/new/", display_name="Stage zero").status_code
        == 303
    )
    assert authenticated.get(f"/api/v1/people/{p.id}/").status_code == 200
    assert ContactPoint.objects.filter(pk=cp.pk).exists()


@pytest.mark.parametrize(
    "data",
    [
        {"kind": "bad"},
        {"value": ""},
        {"value": "x" * 321},
        {"value": "\x00"},
        {"label": "\x00"},
        {"expected_version": "9" * 5000},
    ],
)
def test_invalid_child_no_partial_parent_update(authenticated, owners, data):
    p = person(owners)
    values = dict(expected_version=1, kind="email", value="valid", label="")
    values.update(data)
    assert (
        post(authenticated, f"/people/{p.id}/contact-points/new/", **values).status_code
        == 200
    )
    p.refresh_from_db()
    assert p.version == 1 and not ContactPoint.objects.exists()


def test_database_rejects_cross_workspace_child(owners):
    a, b = person(owners), person(owners, 1)
    with pytest.raises(IntegrityError), transaction.atomic():
        ContactPoint.objects.create(
            workspace=b.workspace, party=a, kind="email", value="bad"
        )


@pytest.mark.django_db(transaction=True)
@pytest.mark.parametrize("first", ["archive", "child"])
def test_concurrent_archive_and_child_http_are_serialized(owners, settings, first):
    p = person(owners)
    clients = []
    for _ in range(2):
        c = Client(enforce_csrf_checks=True)
        c.force_login(owners[0])
        c.get("/people/new/")
        clients.append(c)
    locked, release, second_started = Event(), Event(), Event()
    original = services.locked_person
    backend_pids = {}

    def held_lock(user, person_id):
        row = original(user, person_id)
        if not locked.is_set():
            locked.set()
            assert release.wait(10)
        return row

    def request(index, action):
        close_old_connections()
        try:
            if index == 1:
                with connection.cursor() as cursor:
                    cursor.execute("SELECT pg_backend_pid()")
                    backend_pids[index] = cursor.fetchone()[0]
                second_started.set()
            if action == "archive":
                return post(
                    clients[index], f"/people/{p.id}/archive/", expected_version=1
                ).status_code
            return contact(clients[index], p).status_code
        finally:
            connection.close()

    from unittest.mock import patch

    with (
        patch.object(services, "locked_person", held_lock),
        ThreadPoolExecutor(max_workers=2) as pool,
    ):
        first_future = pool.submit(request, 0, first)
        assert locked.wait(10)
        second_future = pool.submit(
            request, 1, "child" if first == "archive" else "archive"
        )
        assert second_started.wait(10)
        try:
            deadline = monotonic() + 5
            while monotonic() < deadline:
                with connection.cursor() as cursor:
                    cursor.execute(
                        "SELECT wait_event_type FROM pg_stat_activity WHERE pid = %s",
                        [backend_pids[1]],
                    )
                    row = cursor.fetchone()
                if row and row[0] == "Lock":
                    break
                assert not second_future.done(), (
                    "Concurrent write bypassed the held parent lock"
                )
                sleep(0.01)
            else:
                pytest.fail(
                    "Second HTTP write never waited for the parent database lock"
                )
        finally:
            release.set()
        assert first_future.result(timeout=10) == 303
        assert second_future.result(timeout=10) == 409
    p.refresh_from_db()
    assert p.version == 2
    assert bool(p.archived_at) == (first == "archive")
    assert ContactPoint.objects.filter(party=p).count() == (first == "child")


@pytest.mark.django_db(transaction=True)
def test_additive_migration_preserves_stage0_data(owners):
    from django.db.migrations.executor import MigrationExecutor

    executor = MigrationExecutor(connection)
    executor.migrate([("crm", "0001_initial")])
    try:
        p = person(owners, name="Pre-migration person")
        identity, workspace, created = p.id, p.workspace_id, p.created_at
    finally:
        executor = MigrationExecutor(connection)
        executor.migrate(executor.loader.graph.leaf_nodes())
    p = Party.objects.get(pk=identity)
    assert (p.workspace_id, p.created_at, p.display_name, p.version) == (
        workspace,
        created,
        "Pre-migration person",
        1,
    )
    services.create_contact_point(owners[0], p.id, 1, "email", "new@example.test", None)
    assert ContactPoint.objects.get(party=p).workspace_id == workspace


@pytest.mark.django_db(transaction=True)
def test_existing_child_edit_waits_for_archive_and_writes_nothing(owners):
    p = person(owners)
    cp = services.create_contact_point(owners[0], p.id, 1, "email", "original", None)
    p.refresh_from_db()
    c = Client(enforce_csrf_checks=True)
    c.force_login(owners[0])
    c.get("/people/new/")
    started = Event()

    def edit():
        close_old_connections()
        try:
            started.set()
            return post(
                c,
                f"/people/{p.id}/contact-points/{cp.id}/edit/",
                expected_version=1,
                kind="phone",
                value="must not commit",
            ).status_code
        finally:
            connection.close()

    with ThreadPoolExecutor(max_workers=1) as pool:
        with transaction.atomic():
            Party.objects.select_for_update().get(pk=p.pk)
            future = pool.submit(edit)
            assert started.wait(10)
            services.set_person_archived(owners[0], p.id, p.version, True)
        assert future.result(timeout=10) == 200
    cp.refresh_from_db()
    assert (cp.kind, cp.value, cp.version) == ("email", "original", 1)
