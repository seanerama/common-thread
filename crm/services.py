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
