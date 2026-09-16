import pytest
from django.core.management import call_command
from django.db import connection
from django.test import Client


@pytest.fixture(autouse=True)
def require_postgresql():
    assert connection.vendor == "postgresql", "Real PostgreSQL is required"


@pytest.fixture
def owners(db, monkeypatch):
    from crm.models import User

    monkeypatch.setenv("COMMON_THREAD_PASSWORD", "Fictional-passphrase-725!")
    for username in ("fictional_owner", "fictional_other"):
        call_command("provision_user", username=username, workspace=username)
    return tuple(
        User.objects.get(username=name)
        for name in ("fictional_owner", "fictional_other")
    )


@pytest.fixture
def authenticated(owners):
    client = Client(enforce_csrf_checks=True)
    client.force_login(owners[0])
    client.get("/people/new/")
    return client


def post_json(client, payload, **kwargs):
    return client.post(
        "/api/v1/people/",
        payload,
        content_type="application/json",
        HTTP_X_CSRFTOKEN=client.cookies["csrftoken"].value,
        **kwargs,
    )
