from datetime import UTC, datetime, timedelta

import pytest
from django.db import connection
from django.http import Http404
from django.test import Client
from django.test.utils import CaptureQueriesContext
from django.utils import timezone

from crm import services
from crm.models import Membership

pytestmark = pytest.mark.django_db


def make_people(owners):
    return (
        services.create_person(owners[0], "Fictional <Alex>"),
        services.create_person(owners[0], "Fictional Blair"),
        services.create_person(owners[0], "Fictional Casey"),
    )


def make_interaction(user, people, occurred_at, body):
    return services.create_interaction(
        user, occurred_at.isoformat(), body, [person.id for person in people]
    )


def make_commitment(user, first, second, person, description, due_on=None):
    return services.create_commitment(
        user,
        description,
        first.id,
        second.id,
        due_on,
        [person.id],
        None,
        interactions_enabled=True,
    )


def enable_workflows(settings):
    settings.RELATIONSHIPS_ENABLED = True
    settings.INTERACTIONS_ENABLED = True
    settings.COMMITMENTS_ENABLED = True
    settings.PERSON_OVERVIEW_ENABLED = True


def test_overview_exact_order_counts_preview_and_full_section_agreement(
    authenticated, owners, settings
):
    enable_workflows(settings)
    first, second, third = make_people(owners)
    today = timezone.now().date()
    unbounded = services.create_relationship(
        owners[0], first.id, second.id, "referral", "Introducer", None, None
    )
    today_relationship = services.create_relationship(
        owners[0], first.id, third.id, "other", "Advisor", today, today
    )
    future = services.create_relationship(
        owners[0],
        first.id,
        second.id,
        "other",
        "Future role",
        today + timedelta(1),
        None,
    )
    services.create_relationship(
        owners[0],
        first.id,
        second.id,
        "other",
        "Former role",
        None,
        today - timedelta(1),
    )

    interactions = [
        make_interaction(
            owners[0],
            (first, second),
            datetime(2026, 1, day, 12, tzinfo=UTC),
            f"Conversation {day}",
        )
        for day in range(1, 8)
    ]
    dated = make_commitment(
        owners[0], first, second, first, "Dated promise", today + timedelta(2)
    )
    later = make_commitment(
        owners[0], second, first, first, "Later promise", today + timedelta(3)
    )
    undated = make_commitment(owners[0], first, third, first, "Undated promise", None)
    completed = make_commitment(
        owners[0], first, second, first, "Completed promise", today
    )
    services.set_commitment_completed(owners[0], completed.id, 1, True)

    overview = services.person_overview(
        owners[0],
        first,
        include_relationships=True,
        include_interactions=True,
        include_commitments=True,
    )
    assert overview["relationships"]["total"] == 2
    assert [row.id for row in overview["relationships"]["items"]] == [
        unbounded.id,
        today_relationship.id,
    ]
    assert future.id not in {row.id for row in overview["relationships"]["items"]}
    assert overview["interactions"]["total"] == 7
    assert [row.id for row in overview["interactions"]["items"]] == [
        row.id for row in reversed(interactions[-5:])
    ]
    assert overview["commitments"]["total"] == 3
    assert [row.id for row in overview["commitments"]["items"]] == [
        dated.id,
        later.id,
        undated.id,
    ]

    response = authenticated.get(f"/people/{first.id}/")
    body = response.content.decode()
    assert response.status_code == 200
    assert "Showing 5 of 7 interactions." in body
    assert body.index("Conversation 7") < body.index("Conversation 3")
    assert "Future role" not in body.split("View all relationships", 1)[0]
    assert "Future role" in body  # It remains in the full current/future panel.
    assert f"/relationships/{unbounded.id}/" in body
    assert f"/interactions/{interactions[-1].id}/" in body
    assert f"/commitments/{dated.id}/" in body
    assert "#relationships-heading" in body
    assert "#interactions-heading" in body
    assert "#commitments-heading" in body


def test_empty_large_escaped_archived_and_foreign_overviews(
    authenticated, owners, settings
):
    enable_workflows(settings)
    first, second, _ = make_people(owners)
    empty = authenticated.get(f"/people/{second.id}/").content.decode()
    assert "No current relationships." in empty
    assert "No interactions yet." in empty
    assert "No open commitments." in empty

    now = datetime(2026, 2, 1, 12, tzinfo=UTC)
    for index in range(51):
        make_interaction(
            owners[0],
            (first,),
            now + timedelta(minutes=index),
            f"Private <script>alert({index})</script> & follow-up",
        )
    first.display_name = "Archived <Person>"
    first.archived_at = timezone.now()
    first.save(update_fields=["display_name", "archived_at", "updated_at"])
    body = authenticated.get(f"/people/{first.id}/").content.decode()
    assert "Archived &lt;Person&gt;" in body
    assert "Archived person." in body
    assert "Showing 5 of 51 interactions." in body
    assert "Private &lt;script&gt;alert(50)&lt;/script&gt; &amp; follow-up" in body
    assert "<script>alert(50)</script>" not in body

    foreign = services.create_person(owners[1], "Foreign private person")
    assert authenticated.get(f"/people/{foreign.id}/").status_code == 404
    with pytest.raises(Http404):
        services.person_overview(owners[0], foreign, include_interactions=True)


def test_overview_keeps_existing_authentication_and_revocation_boundary(
    authenticated, owners, settings
):
    enable_workflows(settings)
    person, _, _ = make_people(owners)
    assert Client().get(f"/people/{person.id}/").status_code == 302
    membership = Membership.objects.get(user=owners[0])
    membership.active = False
    membership.save(update_fields=["active"])
    assert authenticated.get(f"/people/{person.id}/").status_code == 302


@pytest.mark.parametrize(
    ("relationships", "interactions", "commitments"),
    [
        (False, False, False),
        (True, False, False),
        (False, True, False),
        (False, False, True),
        (True, True, False),
        (True, False, True),
        (False, True, True),
        (True, True, True),
    ],
)
def test_independent_flags_only_compose_enabled_summary_and_panels(
    authenticated, owners, settings, relationships, interactions, commitments
):
    settings.PERSON_OVERVIEW_ENABLED = True
    settings.RELATIONSHIPS_ENABLED = relationships
    settings.INTERACTIONS_ENABLED = interactions
    settings.COMMITMENTS_ENABLED = commitments
    first, _, _ = make_people(owners)
    body = authenticated.get(f"/people/{first.id}/").content.decode()
    assert ("Current relationships" in body) is relationships
    assert ("Recent interactions" in body) is interactions
    assert ("Open commitments" in body) is commitments
    assert ('id="relationships-heading"' in body) is relationships
    assert ('id="interactions-heading"' in body) is interactions
    assert ('id="commitments-heading"' in body) is commitments
    if not any((relationships, interactions, commitments)):
        assert "No preparation sections are enabled." in body


def test_feature_off_preserves_stage_six_layout_and_strict_queries(
    authenticated, owners, settings
):
    settings.PERSON_OVERVIEW_ENABLED = False
    settings.RELATIONSHIPS_ENABLED = True
    settings.INTERACTIONS_ENABLED = True
    settings.COMMITMENTS_ENABLED = True
    first, _, _ = make_people(owners)
    response = authenticated.get(f"/people/{first.id}/")
    body = response.content.decode()
    assert "Conversation preparation" not in body
    assert "person_overview" not in response.context
    assert '<h2 id="relationships-heading">Relationships</h2>' in body
    assert '<h2 id="interactions-heading">Interactions</h2>' in body
    assert '<h2 id="commitments-heading">Commitments</h2>' in body
    assert "tabindex" not in body

    settings.PERSON_OVERVIEW_ENABLED = True
    for query in (
        "overview_page=1",
        "interactions_page=1&interactions_page=2",
        "commitments_status=bad",
        "relationships_page=0",
    ):
        assert authenticated.get(f"/people/{first.id}/?{query}").status_code == 400


def test_overview_get_is_read_only_and_query_count_does_not_grow(
    authenticated, owners, settings
):
    enable_workflows(settings)
    first, second, _ = make_people(owners)

    def add_rows(start, count):
        for index in range(start, start + count):
            services.create_relationship(
                owners[0], first.id, second.id, "other", f"Role {index}", None, None
            )
            make_interaction(
                owners[0],
                (first, second),
                datetime(2026, 3, 1, tzinfo=UTC) + timedelta(minutes=index),
                f"Interaction {index}",
            )
            make_commitment(
                owners[0], first, second, first, f"Commitment {index}", None
            )

    add_rows(0, 6)
    with CaptureQueriesContext(connection) as small:
        response = authenticated.get(f"/people/{first.id}/")
        assert response.status_code == 200
    small_count = len(small)
    assert not any(
        query["sql"].lstrip().upper().startswith(("INSERT", "UPDATE", "DELETE"))
        for query in small.captured_queries
    )

    add_rows(6, 45)
    with CaptureQueriesContext(connection) as large:
        response = authenticated.get(f"/people/{first.id}/")
        assert response.status_code == 200
    assert len(large) == small_count
    assert response.context["relationships"].has_next()
    assert response.context["interactions"].has_next()
    assert response.context["commitments"].has_next()
    body = response.content.decode()
    assert "Showing 5 of 51 current relationships." in body
    assert "Showing 5 of 51 interactions." in body
    assert "Showing 5 of 51 open commitments." in body
    assert not any(
        query["sql"].lstrip().upper().startswith(("INSERT", "UPDATE", "DELETE"))
        for query in large.captured_queries
    )


def test_stage_seven_adds_no_schema_or_migration():
    from django.db.migrations.loader import MigrationLoader

    leaf = MigrationLoader(connection).graph.leaf_nodes("crm")
    assert leaf == [("crm", "0007_commitment")]
    assert not any(
        table.startswith("crm_personoverview")
        for table in connection.introspection.table_names()
    )
