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
