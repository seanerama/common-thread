from uuid import UUID

from django.core.exceptions import PermissionDenied, ValidationError
from django.db import transaction
from django.http import Http404

from .models import Membership, Party, Person


def workspace_for(user):
    if not user.is_authenticated or not user.is_active:
        raise PermissionDenied
    membership = Membership.objects.filter(
        user=user, active=True, user__is_active=True
    ).first()
    if membership is None:
        raise PermissionDenied
    return membership.workspace


def validate_name(value):
    if (
        not isinstance(value, str)
        or not 1 <= len(value.strip()) <= 200
        or "\x00" in value
        or any(0xD800 <= ord(char) <= 0xDFFF for char in value)
    ):
        raise ValidationError({"display_name": ["Enter a name of 1–200 characters."]})
    return value.strip()


@transaction.atomic
def create_person(user, display_name):
    workspace = workspace_for(user)
    name = validate_name(display_name)
    party = Party.objects.create(workspace=workspace, kind="person", display_name=name)
    Person.objects.create(party=party)
    return party


def list_people(user):
    return Party.objects.filter(
        workspace=workspace_for(user),
        kind="person",
        person__isnull=False,
        archived_at=None,
    ).order_by("display_name", "id")


def get_person(user, person_id):
    workspace = workspace_for(user)
    try:
        person_id = UUID(str(person_id))
    except (ValueError, TypeError, AttributeError):
        raise Http404 from None
    try:
        return Party.objects.get(
            id=person_id, workspace=workspace, kind="person", person__isnull=False
        )
    except Party.DoesNotExist:
        raise Http404 from None


class Conflict(Exception):
    """The submitted revision is no longer current; no mutation was committed."""


def check_version(record, expected_version):
    if (
        isinstance(expected_version, bool)
        or not str(expected_version).isascii()
        or not str(expected_version).isdecimal()
        or len(str(expected_version)) > 10
        or int(expected_version) < 1
    ):
        raise ValidationError({"expected_version": ["Enter a positive version."]})
    if record.version != int(expected_version):
        raise Conflict("This record changed. Reload and review your changes.")


def locked_person(user, person_id):
    # Re-read under the lock: every parent and child write takes this same lock first.
    person = get_person(user, person_id)
    return Party.objects.select_for_update().get(
        pk=person.pk, workspace=person.workspace
    )


def require_active(person):
    if person.archived_at is not None:
        raise ValidationError(
            {"__all__": ["Restore this person before making changes."]}
        )


def advance(record):
    record.version += 1
    record.save()
    return record


@transaction.atomic
def update_person(user, person_id, expected_version, display_name, is_client):
    person = locked_person(user, person_id)
    check_version(person, expected_version)
    require_active(person)
    person.display_name = validate_name(display_name)
    if not isinstance(is_client, bool):
        raise ValidationError({"is_client": ["Choose a client status."]})
    person.is_client = is_client
    return advance(person)


@transaction.atomic
def set_person_archived(user, person_id, expected_version, archived):
    from django.utils import timezone

    person = locked_person(user, person_id)
    check_version(person, expected_version)
    person.archived_at = timezone.now() if archived else None
    return advance(person)


def validate_contact(kind, value, label):
    errors = {}
    if kind not in ("email", "phone"):
        errors["kind"] = ["Choose email or phone."]
    if not isinstance(value, str) or not 1 <= len(value) <= 320 or invalid_text(value):
        errors["value"] = ["Enter a contact value of 1–320 characters."]
    if label is not None and (not isinstance(label, str) or invalid_text(label)):
        errors["label"] = ["Enter a valid label."]
    if errors:
        raise ValidationError(errors)
    return kind, value, label or None


def invalid_text(value):
    return "\x00" in value or any(0xD800 <= ord(char) <= 0xDFFF for char in value)


def get_contact_point(user, person_id, point_id):
    from .models import ContactPoint

    person = get_person(user, person_id)
    try:
        return ContactPoint.objects.get(
            id=UUID(str(point_id)), party=person, workspace=person.workspace
        )
    except (ValueError, TypeError, AttributeError, ContactPoint.DoesNotExist):
        raise Http404 from None


def list_contact_points(user, person_id):
    person = get_person(user, person_id)
    return person.contact_points.filter(
        workspace=person.workspace, archived_at=None
    ).order_by("created_at", "id")


@transaction.atomic
def create_contact_point(user, person_id, expected_version, kind, value, label):
    from .models import ContactPoint

    person = locked_person(user, person_id)
    check_version(person, expected_version)
    require_active(person)
    kind, value, label = validate_contact(kind, value, label)
    point = ContactPoint.objects.create(
        workspace=person.workspace, party=person, kind=kind, value=value, label=label
    )
    advance(person)
    return point


def locked_contact(user, person, point_id, expected_version):
    from .models import ContactPoint

    point = get_contact_point(user, person.id, point_id)
    point = ContactPoint.objects.select_for_update().get(
        pk=point.pk, workspace=person.workspace, party=person
    )
    check_version(point, expected_version)
    require_active(person)
    if point.archived_at is not None:
        raise ValidationError({"__all__": ["This contact point is archived."]})
    return point


@transaction.atomic
def update_contact_point(
    user, person_id, point_id, expected_version, kind, value, label
):
    person = locked_person(user, person_id)
    point = locked_contact(user, person, point_id, expected_version)
    point.kind, point.value, point.label = validate_contact(kind, value, label)
    return advance(point)


@transaction.atomic
def archive_contact_point(user, person_id, point_id, expected_version):
    from django.utils import timezone

    person = locked_person(user, person_id)
    point = locked_contact(user, person, point_id, expected_version)
    point.archived_at = timezone.now()
    return advance(point)


def search_people(user, q="", archived="exclude", page="1"):
    from django.core.paginator import Page, Paginator
    from django.db.models import Q

    if (
        not isinstance(q, str)
        or len(q) > 200
        or invalid_text(q)
        or archived not in ("exclude", "include", "only")
        or not str(page).isascii()
        or not str(page).isdecimal()
        or not str(page).strip("0")
    ):
        raise ValidationError({"query": ["Invalid search or page."]})
    people = Party.objects.filter(
        workspace=workspace_for(user), kind="person", person__isnull=False
    )
    if archived != "include":
        people = people.filter(archived_at__isnull=archived == "exclude")
    if q:
        people = people.filter(
            Q(display_name__icontains=q)
            | Q(
                contact_points__value__icontains=q,
                contact_points__archived_at__isnull=True,
            )
        )
    people = people.distinct().order_by("display_name", "id")
    paginator = Paginator(people, 50)
    # Bound parsing and SQL offsets even for arbitrarily long positive inputs.
    digits = str(page).lstrip("0")
    number = int(digits) if len(digits) < 20 else paginator.num_pages + 1
    if number > paginator.num_pages:
        return Page([], number, paginator)
    return paginator.page(number)


PARTY_TYPES = {
    "organization": ("organization", "organization"),
    "household": ("household", "household"),
}


def _party_type(kind):
    try:
        return PARTY_TYPES[kind]
    except KeyError:
        raise ValueError("Unsupported party type") from None


@transaction.atomic
def create_typed_party(user, kind, display_name, is_client):
    from .models import Household, Organization

    relation, _ = _party_type(kind)
    if not isinstance(is_client, bool):
        raise ValidationError({"is_client": ["Choose a client status."]})
    party = Party.objects.create(
        workspace=workspace_for(user),
        kind=kind,
        display_name=validate_name(display_name),
        is_client=is_client,
    )
    {"organization": Organization, "household": Household}[relation].objects.create(
        party=party
    )
    return party


def get_typed_party(user, kind, party_id):
    relation, _ = _party_type(kind)
    try:
        party_id = UUID(str(party_id))
    except (ValueError, TypeError, AttributeError):
        raise Http404 from None
    filters = {
        "id": party_id,
        "workspace": workspace_for(user),
        "kind": kind,
        f"{relation}__isnull": False,
    }
    try:
        return Party.objects.get(**filters)
    except Party.DoesNotExist:
        raise Http404 from None


def search_typed_parties(user, kind, q="", archived="exclude", page="1"):
    from django.core.paginator import Page, Paginator

    relation, _ = _party_type(kind)
    if (
        not isinstance(q, str)
        or len(q) > 200
        or invalid_text(q)
        or archived not in ("exclude", "include", "only")
        or not str(page).isascii()
        or not str(page).isdecimal()
        or not str(page).strip("0")
    ):
        raise ValidationError({"query": ["Invalid search or page."]})
    rows = Party.objects.filter(
        workspace=workspace_for(user), kind=kind, **{f"{relation}__isnull": False}
    )
    if archived != "include":
        rows = rows.filter(archived_at__isnull=archived == "exclude")
    if q:
        rows = rows.filter(display_name__icontains=q)
    paginator = Paginator(rows.order_by("display_name", "id"), 50)
    digits = str(page).lstrip("0")
    number = int(digits) if len(digits) < 20 else paginator.num_pages + 1
    if number > paginator.num_pages:
        return Page([], number, paginator)
    return paginator.page(number)


def locked_typed_party(user, kind, party_id):
    party = get_typed_party(user, kind, party_id)
    return Party.objects.select_for_update().get(
        pk=party.pk, workspace=party.workspace, kind=kind
    )


@transaction.atomic
def update_typed_party(user, kind, party_id, expected_version, display_name, is_client):
    party = locked_typed_party(user, kind, party_id)
    check_version(party, expected_version)
    if party.archived_at is not None:
        raise ValidationError(
            {"__all__": [f"Restore this {kind} before making changes."]}
        )
    if not isinstance(is_client, bool):
        raise ValidationError({"is_client": ["Choose a client status."]})
    party.display_name = validate_name(display_name)
    party.is_client = is_client
    return advance(party)


@transaction.atomic
def set_typed_party_archived(user, kind, party_id, expected_version, archived):
    from django.utils import timezone

    party = locked_typed_party(user, kind, party_id)
    check_version(party, expected_version)
    party.archived_at = timezone.now() if archived else None
    return advance(party)


def _uuid(value, field="id"):
    try:
        return UUID(str(value))
    except (ValueError, TypeError, AttributeError):
        raise ValidationError({field: ["Select a valid party."]}) from None


def _validate_relationship(kind, role, starts_on, ends_on):
    errors = {}
    if (
        not isinstance(kind, str)
        or not 1 <= len(kind.strip()) <= 80
        or invalid_text(kind)
    ):
        errors["kind"] = ["Enter a relationship kind of 1–80 characters."]
    if role is not None and (not isinstance(role, str) or invalid_text(role)):
        errors["role"] = ["Enter a valid role."]
    if starts_on is not None and ends_on is not None and ends_on < starts_on:
        errors["ends_on"] = ["End date cannot be before start date."]
    if errors:
        raise ValidationError(errors)
    return kind.strip(), role or None, starts_on, ends_on


def _lock_parties(workspace, party_ids, require_active=False):
    ids = sorted(set(party_ids), key=str)
    parties = list(
        Party.objects.select_for_update()
        .filter(workspace=workspace, id__in=ids)
        .order_by("id")
    )
    if len(parties) != len(ids):
        raise ValidationError({"party": ["Select valid parties."]})
    if require_active and any(party.archived_at is not None for party in parties):
        raise ValidationError({"party": ["Select active parties."]})
    return {party.id: party for party in parties}


def relationship_selector(user, q="", page="1"):
    from django.core.paginator import Page, Paginator

    if (
        not isinstance(q, str)
        or len(q) > 200
        or invalid_text(q)
        or not str(page).isascii()
        or not str(page).isdecimal()
        or not str(page).strip("0")
    ):
        raise ValidationError({"query": ["Invalid selector search or page."]})
    rows = Party.objects.filter(workspace=workspace_for(user), archived_at__isnull=True)
    if q:
        rows = rows.filter(display_name__icontains=q)
    paginator = Paginator(rows.order_by("display_name", "id"), 50)
    digits = str(page).lstrip("0")
    number = int(digits) if len(digits) < 20 else paginator.num_pages + 1
    if number > paginator.num_pages:
        return Page([], number, paginator)
    return paginator.page(number)


def get_relationship(user, relationship_id):
    from .models import Relationship

    try:
        relationship_id = UUID(str(relationship_id))
    except (ValueError, TypeError, AttributeError):
        raise Http404 from None
    try:
        return Relationship.objects.select_related("from_party", "to_party").get(
            id=relationship_id, workspace=workspace_for(user)
        )
    except Relationship.DoesNotExist:
        raise Http404 from None


@transaction.atomic
def create_relationship(
    user, from_party_id, to_party_id, kind, role, starts_on, ends_on
):
    from .models import Relationship

    workspace = workspace_for(user)
    from_id = _uuid(from_party_id, "from_party_id")
    to_id = _uuid(to_party_id, "to_party_id")
    if from_id == to_id:
        raise ValidationError({"to_party_id": ["Choose two different parties."]})
    parties = _lock_parties(workspace, [from_id, to_id], require_active=True)
    kind, role, starts_on, ends_on = _validate_relationship(
        kind, role, starts_on, ends_on
    )
    return Relationship.objects.create(
        workspace=workspace,
        from_party=parties[from_id],
        to_party=parties[to_id],
        kind=kind,
        role=role,
        starts_on=starts_on,
        ends_on=ends_on,
    )


def _locked_relationship(user, relationship_id, expected_version):
    from .models import Relationship

    existing = get_relationship(user, relationship_id)
    _lock_parties(existing.workspace, [existing.from_party_id, existing.to_party_id])
    relationship = Relationship.objects.select_for_update().get(
        pk=existing.pk, workspace=existing.workspace
    )
    check_version(relationship, expected_version)
    return relationship


@transaction.atomic
def update_relationship(
    user, relationship_id, expected_version, kind, role, starts_on, ends_on
):
    relationship = _locked_relationship(user, relationship_id, expected_version)
    values = _validate_relationship(kind, role, starts_on, ends_on)
    (
        relationship.kind,
        relationship.role,
        relationship.starts_on,
        relationship.ends_on,
    ) = values
    return advance(relationship)


@transaction.atomic
def close_relationship(user, relationship_id, expected_version, ends_on):
    relationship = _locked_relationship(user, relationship_id, expected_version)
    _, _, _, ends_on = _validate_relationship(
        relationship.kind, relationship.role, relationship.starts_on, ends_on
    )
    if ends_on is None:
        raise ValidationError({"ends_on": ["Enter an end date."]})
    relationship.ends_on = ends_on
    return advance(relationship)


def relationship_panels(user, party_id, page="1", ended_page="1"):
    from django.core.paginator import Page, Paginator
    from django.db.models import F, Q
    from django.utils import timezone

    workspace = workspace_for(user)
    party_id = _uuid(party_id)
    if not Party.objects.filter(pk=party_id, workspace=workspace).exists():
        raise Http404

    def page_number(value, paginator):
        if (
            not str(value).isascii()
            or not str(value).isdecimal()
            or not str(value).strip("0")
        ):
            raise ValidationError({"page": ["Enter a positive page number."]})
        digits = str(value).lstrip("0")
        number = int(digits) if len(digits) < 20 else paginator.num_pages + 1
        return (
            Page([], number, paginator)
            if number > paginator.num_pages
            else paginator.page(number)
        )

    from .models import Relationship

    today = timezone.now().date()
    base = (
        Relationship.objects.filter(workspace=workspace)
        .filter(Q(from_party_id=party_id) | Q(to_party_id=party_id))
        .select_related("from_party", "to_party")
    )
    active = base.filter(Q(ends_on__isnull=True) | Q(ends_on__gte=today)).order_by(
        F("starts_on").asc(nulls_first=True), "id"
    )
    ended = base.filter(ends_on__lt=today).order_by("-ends_on", "id")
    active_paginator, ended_paginator = Paginator(active, 50), Paginator(ended, 50)
    active_result = page_number(page, active_paginator)
    ended_result = page_number(ended_page, ended_paginator)
    for row in active_result:
        row.timeline_status = (
            "future"
            if row.starts_on is not None and row.starts_on > today
            else "current"
        )
    for row in ended_result:
        row.timeline_status = "ended"
    return active_result, ended_result


def interaction_selector(user, q="", page="1"):
    return relationship_selector(user, q, page)


def interaction_selected_parties(user, values, retainable_ids=()):
    workspace = workspace_for(user)
    ids = _interaction_participant_ids(values) if values else []
    retainable = set(retainable_ids)
    parties = list(Party.objects.filter(workspace=workspace, id__in=ids))
    if len(parties) != len(ids) or any(
        party.archived_at is not None and party.id not in retainable
        for party in parties
    ):
        raise ValidationError({"participant_ids": ["Select valid active parties."]})
    by_id = {party.id: party for party in parties}
    return [by_id[party_id] for party_id in ids]


def _interaction_participant_ids(values):
    if isinstance(values, (str, bytes)):
        raise ValidationError({"participant_ids": ["Select one or more participants."]})
    try:
        ids = [_uuid(value, "participant_ids") for value in values]
    except TypeError:
        raise ValidationError(
            {"participant_ids": ["Select one or more participants."]}
        ) from None
    if not ids:
        raise ValidationError({"participant_ids": ["Select one or more participants."]})
    if len(ids) != len(set(ids)):
        raise ValidationError({"participant_ids": ["Select each participant once."]})
    return ids


def _validate_interaction(occurred_at, body):
    from datetime import UTC, datetime

    errors = {}
    value = occurred_at
    if isinstance(value, str):
        try:
            value = datetime.fromisoformat(value)
        except ValueError:
            value = None
    if value is None or not isinstance(value, datetime) or value.utcoffset() is None:
        errors["occurred_at"] = [
            "Enter an ISO date and time with an explicit UTC offset."
        ]
    if (
        not isinstance(body, str)
        or not body.strip()
        or len(body) > 20000
        or invalid_text(body)
    ):
        errors["body"] = ["Enter interaction text of 1–20000 characters."]
    if errors:
        raise ValidationError(errors)
    return value.astimezone(UTC), body


def get_interaction(user, interaction_id):
    from .models import Interaction

    try:
        interaction_id = UUID(str(interaction_id))
    except (ValueError, TypeError, AttributeError):
        raise Http404 from None
    try:
        return (
            Interaction.objects.select_related("authored_by")
            .prefetch_related("participant_links__party")
            .get(id=interaction_id, workspace=workspace_for(user))
        )
    except Interaction.DoesNotExist:
        raise Http404 from None


def interaction_parties(interaction):
    return sorted(
        (link.party for link in interaction.participant_links.all()),
        key=lambda party: (party.display_name, str(party.id)),
    )


@transaction.atomic
def create_interaction(user, occurred_at, body, participant_ids):
    from .models import Interaction, InteractionParticipant

    workspace = workspace_for(user)
    participant_ids = _interaction_participant_ids(participant_ids)
    parties = _lock_parties(workspace, participant_ids, require_active=True)
    occurred_at, body = _validate_interaction(occurred_at, body)
    interaction = Interaction.objects.create(
        workspace=workspace,
        occurred_at=occurred_at,
        body=body,
        authored_by=user,
    )
    InteractionParticipant.objects.bulk_create(
        [
            InteractionParticipant(
                workspace=workspace,
                interaction=interaction,
                party=parties[party_id],
            )
            for party_id in participant_ids
        ]
    )
    return interaction


@transaction.atomic
def update_interaction(
    user, interaction_id, expected_version, occurred_at, body, participant_ids
):
    from django.db.models import F
    from django.utils import timezone

    from .models import (
        Interaction,
        InteractionParticipant,
        InteractionRevision,
        InteractionRevisionParticipant,
    )

    existing = get_interaction(user, interaction_id)
    submitted_ids = _interaction_participant_ids(participant_ids)
    old_ids = {link.party_id for link in existing.participant_links.all()}
    locked_parties = _lock_parties(
        existing.workspace, old_ids | set(submitted_ids), require_active=False
    )
    interaction = Interaction.objects.select_for_update().get(
        pk=existing.pk, workspace=existing.workspace
    )
    current_ids = set(
        InteractionParticipant.objects.filter(
            interaction=interaction, workspace=interaction.workspace
        ).values_list("party_id", flat=True)
    )
    if current_ids != old_ids:
        raise Conflict("This interaction changed. Reload and review your changes.")
    check_version(interaction, expected_version)
    for party_id in set(submitted_ids) - current_ids:
        if locked_parties[party_id].archived_at is not None:
            raise ValidationError(
                {"participant_ids": ["Select active parties for new participants."]}
            )
    occurred_at, body = _validate_interaction(occurred_at, body)
    revision = InteractionRevision.objects.create(
        workspace=interaction.workspace,
        interaction=interaction,
        occurred_at=interaction.occurred_at,
        body=interaction.body,
        version=interaction.version,
        authored_by=interaction.authored_by,
        edited_by=user,
        edited_at=timezone.now(),
    )
    InteractionRevisionParticipant.objects.bulk_create(
        [
            InteractionRevisionParticipant(
                workspace=interaction.workspace,
                revision=revision,
                party=locked_parties[party_id],
            )
            for party_id in current_ids
        ]
    )
    now = timezone.now()
    InteractionParticipant.objects.filter(interaction=interaction).exclude(
        party_id__in=submitted_ids
    ).update(
        archived_at=now,
        updated_at=now,
        version=F("version") + 1,
    )
    retained_ids = current_ids & set(submitted_ids)
    new_ids = [party_id for party_id in submitted_ids if party_id not in retained_ids]
    prior_links = {
        link.party_id: link
        for link in InteractionParticipant.all_objects.filter(
            interaction=interaction, party_id__in=new_ids
        )
    }
    create_links = []
    for party_id in new_ids:
        link = prior_links.get(party_id)
        if link:
            link.archived_at = None
            link.version += 1
            link.save(update_fields=["archived_at", "version", "updated_at"])
        else:
            create_links.append(
                InteractionParticipant(
                    workspace=interaction.workspace,
                    interaction=interaction,
                    party=locked_parties[party_id],
                )
            )
    InteractionParticipant.objects.bulk_create(create_links)
    interaction.occurred_at = occurred_at
    interaction.body = body
    return advance(interaction)


def interaction_history(user, interaction_id):
    interaction = get_interaction(user, interaction_id)
    return (
        interaction.revisions.filter(workspace=interaction.workspace)
        .select_related("authored_by", "edited_by")
        .prefetch_related("participant_links__party")
        .order_by("-version", "id")
    )


def interaction_panels(user, party_id, page="1"):
    from django.core.paginator import Page, Paginator

    workspace = workspace_for(user)
    party_id = _uuid(party_id)
    if not Party.objects.filter(pk=party_id, workspace=workspace).exists():
        raise Http404
    if not str(page).isascii() or not str(page).isdecimal() or not str(page).strip("0"):
        raise ValidationError({"page": ["Enter a positive page number."]})
    from .models import Interaction

    rows = (
        Interaction.objects.filter(
            workspace=workspace,
            participant_links__workspace=workspace,
            participant_links__party_id=party_id,
            participant_links__archived_at__isnull=True,
        )
        .select_related("authored_by")
        .prefetch_related("participant_links__party")
        .order_by("-occurred_at", "id")
    )
    paginator = Paginator(rows, 50)
    digits = str(page).lstrip("0")
    number = int(digits) if len(digits) < 20 else paginator.num_pages + 1
    return (
        Page([], number, paginator)
        if number > paginator.num_pages
        else paginator.page(number)
    )


UNSET = object()


def _positive_page(value, paginator):
    from django.core.paginator import Page

    if (
        not str(value).isascii()
        or not str(value).isdecimal()
        or not str(value).strip("0")
    ):
        raise ValidationError({"page": ["Enter a positive page number."]})
    digits = str(value).lstrip("0")
    number = int(digits) if len(digits) < 20 else paginator.num_pages + 1
    return (
        Page([], number, paginator)
        if number > paginator.num_pages
        else paginator.page(number)
    )


def commitment_person_selector(user, q="", page="1"):
    from django.core.paginator import Paginator

    if not isinstance(q, str) or len(q) > 200 or invalid_text(q):
        raise ValidationError({"query": ["Invalid selector search."]})
    rows = Party.objects.filter(
        workspace=workspace_for(user),
        kind="person",
        person__isnull=False,
        archived_at__isnull=True,
    )
    if q:
        rows = rows.filter(display_name__icontains=q)
    return _positive_page(page, Paginator(rows.order_by("display_name", "id"), 50))


def commitment_selected_party(user, value, retainable_id=None):
    party_id = _uuid(value, "party")
    try:
        party = Party.objects.get(id=party_id, workspace=workspace_for(user))
    except Party.DoesNotExist:
        raise ValidationError({"party": ["Select a valid party."]}) from None
    if party.archived_at is not None and party.id != retainable_id:
        raise ValidationError({"party": ["Select an active party."]})
    return party


def commitment_selected_people(user, values, retainable_ids=()):
    ids = _commitment_person_ids(values) if values else []
    retainable = set(retainable_ids)
    people = list(
        Party.objects.filter(
            workspace=workspace_for(user),
            id__in=ids,
            kind="person",
            person__isnull=False,
        )
    )
    if len(people) != len(ids) or any(
        person.archived_at is not None and person.id not in retainable
        for person in people
    ):
        raise ValidationError({"person_ids": ["Select valid active people."]})
    by_id = {person.id: person for person in people}
    return [by_id[person_id] for person_id in ids]


def commitment_source_selector(user, q="", page="1"):
    from django.core.paginator import Paginator

    if not isinstance(q, str) or len(q) > 200 or invalid_text(q):
        raise ValidationError({"query": ["Invalid source selector search."]})
    from .models import Interaction

    rows = Interaction.objects.filter(
        workspace=workspace_for(user), archived_at__isnull=True
    )
    if q:
        rows = rows.filter(body__icontains=q)
    return _positive_page(page, Paginator(rows.order_by("-occurred_at", "id"), 50))


def _commitment_person_ids(values):
    if isinstance(values, (str, bytes)):
        raise ValidationError({"person_ids": ["Select one or more people."]})
    try:
        ids = [_uuid(value, "person_ids") for value in values]
    except TypeError:
        raise ValidationError({"person_ids": ["Select one or more people."]}) from None
    if not ids:
        raise ValidationError({"person_ids": ["Select one or more people."]})
    if len(ids) != len(set(ids)):
        raise ValidationError({"person_ids": ["Select each person once."]})
    return ids


def _validate_commitment(description):
    if (
        not isinstance(description, str)
        or not 1 <= len(description.strip()) <= 2000
        or invalid_text(description)
    ):
        raise ValidationError(
            {"description": ["Enter a description of 1–2000 characters."]}
        )
    return description


def get_commitment(user, commitment_id):
    from .models import Commitment

    try:
        commitment_id = UUID(str(commitment_id))
    except (ValueError, TypeError, AttributeError):
        raise Http404 from None
    try:
        return (
            Commitment.objects.select_related(
                "owed_by", "owed_to", "created_by", "source_interaction"
            )
            .prefetch_related("person_links__person")
            .get(id=commitment_id, workspace=workspace_for(user))
        )
    except Commitment.DoesNotExist:
        raise Http404 from None


def commitment_people(commitment):
    return sorted(
        (
            link.person
            for link in commitment.person_links.all()
            if link.archived_at is None
        ),
        key=lambda party: (party.display_name, str(party.id)),
    )


def _lock_interactions(workspace, ids):
    from .models import Interaction

    ids = sorted(set(ids), key=str)
    rows = list(
        Interaction.objects.select_for_update()
        .filter(workspace=workspace, id__in=ids)
        .order_by("id")
    )
    if len(rows) != len(ids):
        raise ValidationError(
            {"source_interaction_id": ["Select a valid interaction."]}
        )
    return {row.id: row for row in rows}


@transaction.atomic
def create_commitment(
    user,
    description,
    owed_by_party_id,
    owed_to_party_id,
    due_on,
    person_ids,
    source_interaction_id=None,
    interactions_enabled=True,
):
    from .models import Commitment, CommitmentPerson

    workspace = workspace_for(user)
    owed_by_id = _uuid(owed_by_party_id, "owed_by_party_id")
    owed_to_id = _uuid(owed_to_party_id, "owed_to_party_id")
    person_ids = _commitment_person_ids(person_ids)
    parties = _lock_parties(
        workspace, {owed_by_id, owed_to_id, *person_ids}, require_active=True
    )
    if Person.objects.filter(party_id__in=person_ids).count() != len(person_ids):
        raise ValidationError({"person_ids": ["Select valid people."]})
    source_id = None
    if source_interaction_id not in (None, ""):
        if not interactions_enabled:
            raise ValidationError(
                {"source_interaction_id": ["Source interactions are disabled."]}
            )
        source_id = _uuid(source_interaction_id, "source_interaction_id")
    interactions = _lock_interactions(workspace, [source_id] if source_id else [])
    commitment = Commitment.objects.create(
        workspace=workspace,
        description=_validate_commitment(description),
        owed_by=parties[owed_by_id],
        owed_to=parties[owed_to_id],
        due_on=due_on,
        status="open",
        completed_at=None,
        created_by=user,
        source_interaction=interactions.get(source_id),
    )
    CommitmentPerson.objects.bulk_create(
        [
            CommitmentPerson(
                workspace=workspace, commitment=commitment, person=parties[person_id]
            )
            for person_id in person_ids
        ]
    )
    return commitment


@transaction.atomic
def update_commitment(
    user,
    commitment_id,
    expected_version,
    description,
    owed_by_party_id,
    owed_to_party_id,
    due_on,
    person_ids,
    source_interaction_id=UNSET,
    interactions_enabled=True,
):
    from django.db.models import F
    from django.utils import timezone

    from .models import Commitment, CommitmentPerson

    existing = get_commitment(user, commitment_id)
    old_person_ids = {person.id for person in commitment_people(existing)}
    new_person_ids = _commitment_person_ids(person_ids)
    owed_by_id = _uuid(owed_by_party_id, "owed_by_party_id")
    owed_to_id = _uuid(owed_to_party_id, "owed_to_party_id")
    old_party_ids = {
        existing.owed_by_id,
        existing.owed_to_id,
        *old_person_ids,
    }
    new_party_ids = {owed_by_id, owed_to_id, *new_person_ids}
    locked_parties = _lock_parties(existing.workspace, old_party_ids | new_party_ids)
    if Person.objects.filter(party_id__in=new_person_ids).count() != len(
        new_person_ids
    ):
        raise ValidationError({"person_ids": ["Select valid people."]})
    if source_interaction_id is UNSET:
        target_source_id = existing.source_interaction_id
    elif source_interaction_id in (None, ""):
        target_source_id = None
    else:
        target_source_id = _uuid(source_interaction_id, "source_interaction_id")
    if (
        not interactions_enabled
        and target_source_id is not None
        and target_source_id != existing.source_interaction_id
    ):
        raise ValidationError(
            {"source_interaction_id": ["Source interactions are disabled."]}
        )
    interaction_ids = {
        value for value in (existing.source_interaction_id, target_source_id) if value
    }
    interactions = _lock_interactions(existing.workspace, interaction_ids)
    commitment = Commitment.objects.select_for_update().get(
        pk=existing.pk, workspace=existing.workspace
    )
    current_person_ids = set(
        CommitmentPerson.objects.filter(
            commitment=commitment,
            workspace=commitment.workspace,
            archived_at__isnull=True,
        ).values_list("person_id", flat=True)
    )
    if (
        current_person_ids != old_person_ids
        or commitment.owed_by_id != existing.owed_by_id
        or commitment.owed_to_id != existing.owed_to_id
        or commitment.source_interaction_id != existing.source_interaction_id
    ):
        raise Conflict("This commitment changed. Reload and review your changes.")
    check_version(commitment, expected_version)
    newly_linked = set(new_person_ids) - old_person_ids
    if owed_by_id != existing.owed_by_id:
        newly_linked.add(owed_by_id)
    if owed_to_id != existing.owed_to_id:
        newly_linked.add(owed_to_id)
    for party_id in newly_linked:
        if locked_parties[party_id].archived_at is not None:
            raise ValidationError({"party": ["Select active parties for new links."]})
    description = _validate_commitment(description)
    now = timezone.now()
    CommitmentPerson.objects.filter(commitment=commitment).exclude(
        person_id__in=new_person_ids
    ).update(archived_at=now, updated_at=now, version=F("version") + 1)
    prior = {
        link.person_id: link
        for link in CommitmentPerson.objects.filter(
            commitment=commitment, person_id__in=new_person_ids
        )
    }
    additions = []
    for person_id in new_person_ids:
        link = prior.get(person_id)
        if link:
            if link.archived_at is not None:
                link.archived_at = None
                link.version += 1
                link.save(update_fields=["archived_at", "version", "updated_at"])
        else:
            additions.append(
                CommitmentPerson(
                    workspace=commitment.workspace,
                    commitment=commitment,
                    person=locked_parties[person_id],
                )
            )
    CommitmentPerson.objects.bulk_create(additions)
    commitment.description = description
    commitment.owed_by = locked_parties[owed_by_id]
    commitment.owed_to = locked_parties[owed_to_id]
    commitment.due_on = due_on
    commitment.source_interaction = interactions.get(target_source_id)
    return advance(commitment)


@transaction.atomic
def set_commitment_completed(user, commitment_id, expected_version, completed):
    from django.utils import timezone

    from .models import Commitment

    existing = get_commitment(user, commitment_id)
    party_ids = {
        existing.owed_by_id,
        existing.owed_to_id,
        *(person.id for person in commitment_people(existing)),
    }
    _lock_parties(existing.workspace, party_ids)
    if existing.source_interaction_id:
        _lock_interactions(existing.workspace, [existing.source_interaction_id])
    commitment = Commitment.objects.select_for_update().get(
        pk=existing.pk, workspace=existing.workspace
    )
    check_version(commitment, expected_version)
    target = "completed" if completed else "open"
    if commitment.status == target:
        raise ValidationError({"__all__": [f"This commitment is already {target}."]})
    commitment.status = target
    commitment.completed_at = timezone.now() if completed else None
    return advance(commitment)


def list_commitments(user, status="open", due="all", page="1"):
    from django.core.paginator import Paginator
    from django.db.models import F
    from django.utils import timezone

    if status not in ("open", "completed", "all") or due not in (
        "all",
        "overdue",
        "today",
        "undated",
    ):
        raise ValidationError({"query": ["Invalid commitment filter."]})
    from .models import Commitment

    rows = Commitment.objects.filter(workspace=workspace_for(user)).select_related(
        "owed_by", "owed_to", "created_by"
    )
    if status != "all":
        rows = rows.filter(status=status)
    today = timezone.now().date()
    if due == "overdue":
        rows = rows.filter(status="open", due_on__lt=today)
    elif due == "today":
        rows = rows.filter(due_on=today)
    elif due == "undated":
        rows = rows.filter(due_on__isnull=True)
    rows = rows.order_by(F("due_on").asc(nulls_last=True), "created_at", "id")
    return _positive_page(page, Paginator(rows, 50))


def commitment_panels(user, person_id, status="open", page="1"):
    from django.core.paginator import Paginator
    from django.db.models import F

    person = get_person(user, person_id)
    if status not in ("open", "completed", "all"):
        raise ValidationError({"query": ["Invalid commitment status."]})
    from .models import Commitment

    rows = Commitment.objects.filter(
        workspace=person.workspace,
        person_links__workspace=person.workspace,
        person_links__person=person,
        person_links__archived_at__isnull=True,
    ).select_related("owed_by", "owed_to", "created_by")
    if status != "all":
        rows = rows.filter(status=status)
    rows = rows.order_by(F("due_on").asc(nulls_last=True), "created_at", "id")
    return _positive_page(page, Paginator(rows, 50))


def validate_note(body, source):
    errors = {}
    for field, value, limit in (("body", body, 20000), ("source", source, 500)):
        if (
            not isinstance(value, str)
            or not value.strip()
            or len(value) > limit
            or invalid_text(value)
        ):
            errors[field] = [f"Enter {field} of 1–{limit} characters."]
    if errors:
        raise ValidationError(errors)
    return body, source


def get_context_note(user, person_id, note_id):
    from .models import ContextNote

    person = get_person(user, person_id)
    try:
        return ContextNote.objects.get(
            id=UUID(str(note_id)), person=person, workspace=person.workspace
        )
    except (ValueError, TypeError, AttributeError, ContextNote.DoesNotExist):
        raise Http404 from None


def list_context_notes(user, person_id):
    person = get_person(user, person_id)
    return (
        person.context_notes.filter(workspace=person.workspace)
        .select_related("authored_by")
        .order_by("created_at", "id")
    )


def context_note_history(user, person_id, note_id):
    note = get_context_note(user, person_id, note_id)
    return (
        note.revisions.filter(workspace=note.workspace)
        .select_related("authored_by", "edited_by")
        .order_by("-version")
    )


@transaction.atomic
def create_context_note(user, person_id, expected_version, body, source):
    from .models import ContextNote

    person = locked_person(user, person_id)
    check_version(person, expected_version)
    require_active(person)
    body, source = validate_note(body, source)
    note = ContextNote.objects.create(
        workspace=person.workspace,
        person=person,
        body=body,
        source=source,
        authored_by=user,
    )
    advance(person)
    return note


@transaction.atomic
def update_context_note(user, person_id, note_id, expected_version, body, source):
    from django.utils import timezone

    from .models import ContextNote, ContextNoteRevision

    person = locked_person(user, person_id)
    existing = get_context_note(user, person_id, note_id)
    note = ContextNote.objects.select_for_update().get(
        pk=existing.pk, person=person, workspace=person.workspace
    )
    check_version(note, expected_version)
    require_active(person)
    body, source = validate_note(body, source)
    ContextNoteRevision.objects.create(
        workspace=note.workspace,
        note=note,
        body=note.body,
        source=note.source,
        version=note.version,
        authored_by=note.authored_by,
        edited_by=user,
        edited_at=timezone.now(),
    )
    note.body, note.source = body, source
    return advance(note)
