import json
from datetime import datetime
from uuid import UUID, uuid4

import pytest
from django.test import Client

from .conftest import post_json

pytestmark = pytest.mark.django_db


def assert_error(response, status, code):
    assert response.status_code == status
    assert response.headers["Content-Type"].startswith("application/json")
    assert response.headers["Cache-Control"] == "no-store"
    error = response.json()["error"]
    assert error["code"] == code
    assert isinstance(error["message"], str)
    assert isinstance(error["fields"], dict)
    assert all(isinstance(value, list) for value in error["fields"].values())
    return response.json()


def test_create_read_persists_and_retries_are_distinct(authenticated):
    from crm.models import Party, Person

    response = post_json(authenticated, {"display_name": "  Alex Example  "})
    assert response.status_code == 201
    person = response.json()["data"]
    UUID(person["id"])
    assert person["display_name"] == "Alex Example"
    assert person["is_client"] is False
    assert person["archived_at"] is None
    assert person["version"] == 1 and type(person["version"]) is int
    for key in ("created_at", "updated_at"):
        assert datetime.fromisoformat(person[key]).utcoffset().total_seconds() == 0
    assert response.headers["Location"] == f"/api/v1/people/{person['id']}/"
    assert response.headers["Cache-Control"] == "no-store"
    assert authenticated.get(response.headers["Location"]).json() == response.json()
    assert Person.objects.filter(pk=person["id"]).exists()
    assert Party.objects.filter(pk=person["id"], kind="person").exists()
    repeated = post_json(authenticated, {"display_name": "Alex Example"})
    assert repeated.json()["data"]["id"] != person["id"]


@pytest.mark.parametrize(
    "payload",
    [
        {},
        {"display_name": ""},
        {"display_name": "  \t\n"},
        {"display_name": "x" * 201},
        {"display_name": None},
        {"display_name": 3},
        {"display_name": True},
        {"display_name": []},
        {"display_name": "Alex\x00Example"},
        {"display_name": "\ud800"},
        [],
        None,
        "text",
    ]
    + [
        {"display_name": "Alex", key: "forged"}
        for key in (
            "id",
            "workspace_id",
            "kind",
            "version",
            "created_at",
            "authored_by",
            "unknown",
        )
    ],
)
def test_invalid_input_is_atomic(authenticated, payload):
    from crm.models import Party, Person

    before = (Party.objects.count(), Person.objects.count())
    assert_error(post_json(authenticated, json.dumps(payload)), 400, "validation_error")
    assert (Party.objects.count(), Person.objects.count()) == before


@pytest.mark.parametrize("body", ['{"display_name":', b"\xff", "{bad json}"])
def test_malformed_json(authenticated, body):
    assert_error(post_json(authenticated, body), 400, "validation_error")


def test_payload_size_and_media_type(authenticated):
    assert_error(
        post_json(authenticated, "x" * (16 * 1024 + 1)), 413, "payload_too_large"
    )
    response = authenticated.post(
        "/api/v1/people/",
        "display_name=Alex",
        content_type="text/plain",
        HTTP_X_CSRFTOKEN=authenticated.cookies["csrftoken"].value,
    )
    assert_error(response, 415, "unsupported_media_type")


def test_unicode_name_at_limit(authenticated):
    response = post_json(authenticated, {"display_name": "é" * 200})
    assert response.status_code == 201
    assert response.json()["data"]["display_name"] == "é" * 200


def test_workspace_isolation_even_for_superuser(authenticated, owners):
    person = post_json(authenticated, {"display_name": "Private Fictional"}).json()[
        "data"
    ]
    owner = owners[1]
    owner.is_superuser = owner.is_staff = True
    owner.save()
    outsider = Client()
    outsider.force_login(owner)
    foreign = outsider.get(f"/api/v1/people/{person['id']}/")
    missing = outsider.get(f"/api/v1/people/{uuid4()}/")
    invalid = outsider.get("/api/v1/people/invalid-uuid/")
    assert_error(foreign, 404, "not_found")
    assert foreign.json() == missing.json() == invalid.json()
    assert outsider.get(f"/people/{person['id']}/").status_code == 404
    assert "Private Fictional" not in outsider.get("/people/").content.decode()


def test_anonymous_and_csrf_rejection(owners):
    client = Client(enforce_csrf_checks=True)
    assert_error(client.get(f"/api/v1/people/{uuid4()}/"), 401, "unauthenticated")
    assert client.get("/people/").status_code == 302
    assert_error(
        client.post(
            "/api/v1/people/", {"display_name": "Alex"}, content_type="application/json"
        ),
        401,
        "unauthenticated",
    )
    client.force_login(owners[0])
    assert_error(
        client.post(
            "/api/v1/people/", {"display_name": "Alex"}, content_type="application/json"
        ),
        403,
        "csrf_failed",
    )


def test_html_validation_redirect_escape_and_no_get_writes(authenticated):
    from crm.models import Person

    token = authenticated.cookies["csrftoken"].value
    invalid = authenticated.post(
        "/people/new/",
        {
            "display_name": "   ",
            "csrfmiddlewaretoken": token,
        },
    )
    assert invalid.status_code == 200
    assert Person.objects.count() == 0
    response = authenticated.post(
        "/people/new/",
        {
            "display_name": "<script>alert('fictional')</script>",
            "csrfmiddlewaretoken": token,
        },
    )
    assert response.status_code == 303
    detail = authenticated.get(response.headers["Location"])
    assert "&lt;script&gt;" in detail.content.decode()
    assert "<script>alert('fictional')</script>" not in detail.content.decode()
    count = Person.objects.count()
    authenticated.get("/people/new/?display_name=Unwanted")
    assert Person.objects.count() == count
