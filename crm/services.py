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
