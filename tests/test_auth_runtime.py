import json
from unittest.mock import patch
from uuid import uuid4

import pytest
from django.core.management import call_command
from django.db import OperationalError
from django.test import Client

from .test_person_contract import assert_error

pytestmark = pytest.mark.django_db


def login(client, username="fictional_owner", password="wrong", **extra):
    client.get("/login/")
    return client.post(
        "/login/",
        {
            "username": username,
            "password": password,
            "csrfmiddlewaretoken": client.cookies["csrftoken"].value,
        },
        **extra,
    )


def test_login_rotates_session_cookie_and_logout(owners):
    client = Client(enforce_csrf_checks=True)
    session = client.session
    session["prelogin"] = "fictional"
    session.save()
    old_key = session.session_key
    response = login(client, password="Fictional-passphrase-725!")
    assert response.status_code in (302, 303)
    assert response.headers["Location"] == "/people/"
    assert client.session.session_key != old_key
    cookie = response.cookies["sessionid"]
    assert cookie["httponly"]
    assert cookie["samesite"] == "Lax"
    assert cookie["path"] == "/"
    assert not cookie["domain"]
    assert 43190 <= int(cookie["max-age"]) <= 43200
    old_key = client.session.session_key
    assert client.get("/logout/").status_code == 405
    assert client.get("/people/").status_code == 200
    assert client.post("/logout/").status_code == 403
    response = client.post(
        "/logout/",
        {
            "csrfmiddlewaretoken": client.cookies["csrftoken"].value,
        },
    )
    assert response.status_code in (302, 303)
    assert response.headers["Location"] == "/login/"
    from django.contrib.sessions.models import Session

    assert not Session.objects.filter(session_key=old_key).exists()
    assert client.get("/people/").status_code == 302


def test_login_csrf_and_open_redirect(owners):
    client = Client(enforce_csrf_checks=True)
    assert (
        client.post(
            "/login/",
            {"username": "fictional_owner", "password": "Fictional-passphrase-725!"},
        ).status_code
        == 403
    )
    client.get("/login/")
    response = client.post(
        "/login/?next=https://example.org/",
        {
            "username": "fictional_owner",
            "password": "Fictional-passphrase-725!",
            "csrfmiddlewaretoken": client.cookies["csrftoken"].value,
            "next": "https://example.org/",
        },
    )
    assert response.headers["Location"] == "/people/"


@pytest.mark.parametrize("revocation", ["membership", "user", "password"])
def test_existing_session_revocation(authenticated, owners, revocation):
    from crm.models import Membership

    if revocation == "membership":
        Membership.objects.filter(user=owners[0]).update(active=False)
    elif revocation == "user":
        owners[0].is_active = False
        owners[0].save()
    else:
        owners[0].set_password("Changed-fictional-passphrase-864!")
        owners[0].save()
    assert_error(
        authenticated.get(f"/api/v1/people/{uuid4()}/"), 401, "unauthenticated"
    )
    assert authenticated.get("/people/").status_code == 302


def test_account_rate_limit_shared_across_sources(owners):
    client = Client(enforce_csrf_checks=True)
    for number in range(5):
        assert login(client, REMOTE_ADDR=f"192.0.2.{number + 1}").status_code == 200
    response = login(client, REMOTE_ADDR="192.0.2.100")
    assert response.status_code == 429
    assert 0 < int(response.headers["Retry-After"]) <= 900


def test_source_rate_limit_across_accounts(db):
    client = Client(enforce_csrf_checks=True)
    for number in range(20):
        assert (
            login(
                client, username=f"missing-{number}", REMOTE_ADDR="192.0.2.1"
            ).status_code
            == 200
        )
    response = login(client, username="another", REMOTE_ADDR="192.0.2.1")
    assert response.status_code == 429
    assert int(response.headers["Retry-After"]) > 0


def test_failed_login_message_does_not_reveal_account(owners):
    existing = login(Client(), REMOTE_ADDR="192.0.2.1")
    missing = login(Client(), username="not-existing", REMOTE_ADDR="192.0.2.2")
    import re
    from html import unescape

    def errors(response):
        html = unescape(response.content.decode())
        return re.findall(
            r'<[^>]*(?:role="alert"|class="errorlist")[^>]*>.*?</[^>]+>',
            html,
            re.DOTALL,
        )

    assert existing.status_code == missing.status_code == 200
    assert errors(existing) and errors(existing) == errors(missing)


def test_provisioning_repeatable_without_password_overwrite(owners, monkeypatch):
    from crm.models import Membership, User, Workspace

    before = (
        User.objects.count(),
        Workspace.objects.count(),
        Membership.objects.count(),
    )
    workspace = Membership.objects.get(user=owners[0]).workspace_id
    monkeypatch.setenv("COMMON_THREAD_PASSWORD", "Different-fictional-passphrase-919!")
    call_command("provision_user", username="fictional_owner", workspace="new name")
    owners[0].refresh_from_db()
    assert owners[0].check_password("Fictional-passphrase-725!")
    assert Membership.objects.get(user=owners[0]).workspace_id == workspace
    assert (
        User.objects.count(),
        Workspace.objects.count(),
        Membership.objects.count(),
    ) == before


def test_liveness_without_database_and_readiness_failure(client):
    with patch(
        "django.db.backends.utils.CursorWrapper.execute",
        side_effect=OperationalError("private connection details"),
    ):
        live = client.get("/health/live/")
        assert live.status_code == 200 and live.json() == {"status": "ok"}
        ready = client.get("/health/ready/")
        assert ready.status_code == 503
        assert ready.json() == {"status": "not_ready"}
    for response in (live, ready):
        assert response.headers["Cache-Control"] == "no-store"
        assert "private" not in response.content.decode()
    healthy = client.get("/health/ready/")
    assert healthy.status_code == 200 and healthy.json() == {"status": "ready"}


def test_readiness_rejects_pending_migrations(client):
    with patch(
        "django.db.migrations.executor.MigrationExecutor.migration_plan",
        return_value=[("pending", False)],
    ):
        response = client.get("/health/ready/")
    assert response.status_code == 503
    assert response.json() == {"status": "not_ready"}


def test_safe_api_500(authenticated):
    with patch(
        "crm.services.get_person", side_effect=RuntimeError("secret-diagnostic")
    ):
        # Disable propagation so the production error adapter handles the exception.
        authenticated.raise_request_exception = False
        response = authenticated.get(f"/api/v1/people/{uuid4()}/")
    assert_error(response, 500, "internal_error")
    assert "secret-diagnostic" not in json.dumps(response.json())


def test_login_throttle_window_expiration_and_forwarded_header(owners):
    from datetime import timedelta

    from django.utils import timezone

    from crm.models import LoginAttempt

    client = Client()
    for _ in range(5):
        assert login(client, REMOTE_ADDR="192.0.2.1").status_code == 200
    assert (
        login(
            client, REMOTE_ADDR="192.0.2.1", HTTP_X_FORWARDED_FOR="192.0.2.200"
        ).status_code
        == 429
    )
    LoginAttempt.objects.update(window_start=timezone.now() - timedelta(seconds=901))
    assert (
        login(
            client, password="Fictional-passphrase-725!", REMOTE_ADDR="192.0.2.1"
        ).status_code
        == 302
    )


def test_session_absolute_expiration_and_no_sliding_renewal(owners):
    from django.contrib.sessions.models import Session
    from django.utils import timezone

    client = Client()
    assert login(client, password="Fictional-passphrase-725!").status_code == 302
    session = Session.objects.get(session_key=client.session.session_key)
    original_expiration = session.expire_date
    response = client.get("/people/")
    session.refresh_from_db()
    assert session.expire_date == original_expiration
    assert "sessionid" not in response.cookies
    Session.objects.filter(pk=session.pk).update(expire_date=timezone.now())
    assert client.get("/people/").status_code == 302


def test_structured_logs_do_not_contain_person_values(authenticated, caplog):
    from .conftest import post_json

    with caplog.at_level("INFO"):
        post_json(authenticated, {"display_name": "FictionalSensitiveSentinel"})
    assert "FictionalSensitiveSentinel" not in caplog.text
    from crm.middleware import SafeJsonFormatter

    requests = [
        record
        for record in caplog.records
        if getattr(record, "event", None) == "http_request"
    ]
    assert requests, "HTTP requests must emit structured operational logs"
    for record in requests:
        logged = json.loads(SafeJsonFormatter().format(record))
        assert {"timestamp", "level", "event", "request_id", "outcome"} <= logged.keys()
        assert logged["request_id"]
        assert logged["outcome"] == "201"
        assert "FictionalSensitiveSentinel" not in json.dumps(logged)
