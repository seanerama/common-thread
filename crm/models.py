import uuid

from django.contrib.auth.models import AbstractUser
from django.db import models
from django.db.models import Q


class User(AbstractUser):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)


class Workspace(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    name = models.CharField(max_length=200)


class Membership(models.Model):
    user = models.OneToOneField(User, on_delete=models.PROTECT)
    workspace = models.OneToOneField(Workspace, on_delete=models.PROTECT)
    active = models.BooleanField(default=True)


class Record(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    workspace = models.ForeignKey(Workspace, on_delete=models.PROTECT)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    archived_at = models.DateTimeField(null=True, default=None)
    version = models.PositiveIntegerField(default=1)

    class Meta:
        abstract = True


class Party(Record):
    kind = models.CharField(
        max_length=20, choices=[(x, x) for x in ("person", "organization", "household")]
    )
    display_name = models.CharField(max_length=200)
    is_client = models.BooleanField(default=False)

    class Meta:
        constraints = [
            models.CheckConstraint(
                condition=Q(version__gte=1), name="party_positive_version"
            ),
            models.UniqueConstraint(
                fields=["workspace", "id"], name="party_workspace_id"
            ),
        ]


class Person(models.Model):
    # The subtype inherits its workspace and identity through this single parent.
    party = models.OneToOneField(
        Party, primary_key=True, on_delete=models.PROTECT, related_name="person"
    )


class Organization(models.Model):
    party = models.OneToOneField(
        Party, primary_key=True, on_delete=models.PROTECT, related_name="organization"
    )


class Household(models.Model):
    party = models.OneToOneField(
        Party, primary_key=True, on_delete=models.PROTECT, related_name="household"
    )


class Relationship(Record):
    from_party = models.ForeignKey(
        Party, on_delete=models.PROTECT, related_name="relationships_from"
    )
    to_party = models.ForeignKey(
        Party, on_delete=models.PROTECT, related_name="relationships_to"
    )
    kind = models.CharField(max_length=80)
    role = models.TextField(null=True, default=None)
    starts_on = models.DateField(null=True, default=None)
    ends_on = models.DateField(null=True, default=None)

    class Meta:
        constraints = [
            models.CheckConstraint(
                condition=Q(version__gte=1), name="relationship_positive_version"
            ),
            models.CheckConstraint(
                condition=~Q(from_party=models.F("to_party")),
                name="relationship_distinct_endpoints",
            ),
            models.CheckConstraint(
                condition=(
                    Q(starts_on__isnull=True)
                    | Q(ends_on__isnull=True)
                    | Q(ends_on__gte=models.F("starts_on"))
                ),
                name="relationship_valid_dates",
            ),
            models.UniqueConstraint(
                fields=["workspace", "id"], name="relationship_workspace_id"
            ),
        ]


class LoginAttempt(models.Model):
    key = models.CharField(max_length=64, primary_key=True)
    failures = models.PositiveIntegerField(default=0)
    window_start = models.DateTimeField()


class ContactPoint(Record):
    party = models.ForeignKey(
        Party, on_delete=models.PROTECT, related_name="contact_points"
    )
    kind = models.CharField(
        max_length=5, choices=[("email", "email"), ("phone", "phone")]
    )
    value = models.CharField(max_length=320)
    label = models.TextField(null=True, default=None)

    class Meta:
        constraints = [
            models.CheckConstraint(
                condition=Q(version__gte=1), name="contact_positive_version"
            ),
            models.CheckConstraint(
                condition=Q(kind__in=["email", "phone"]), name="contact_valid_kind"
            ),
            models.UniqueConstraint(
                fields=["workspace", "id"], name="contact_workspace_id"
            ),
        ]


class ContextNote(Record):
    person = models.ForeignKey(
        Party, on_delete=models.PROTECT, related_name="context_notes"
    )
    body = models.TextField()
    source = models.CharField(max_length=500)
    authored_by = models.ForeignKey(
        User, on_delete=models.PROTECT, related_name="context_notes"
    )
    source_interaction_id = models.UUIDField(null=True, default=None)

    class Meta:
        constraints = [
            models.CheckConstraint(
                condition=Q(version__gte=1), name="note_positive_version"
            ),
            models.CheckConstraint(
                condition=Q(source_interaction_id__isnull=True),
                name="note_no_interaction_yet",
            ),
            models.UniqueConstraint(
                fields=["workspace", "id"], name="note_workspace_id"
            ),
        ]


class ContextNoteRevision(Record):
    note = models.ForeignKey(
        ContextNote, on_delete=models.PROTECT, related_name="revisions"
    )
    body = models.TextField()
    source = models.CharField(max_length=500)
    authored_by = models.ForeignKey(
        User, on_delete=models.PROTECT, related_name="authored_note_revisions"
    )
    edited_by = models.ForeignKey(
        User, on_delete=models.PROTECT, related_name="edited_note_revisions"
    )
    edited_at = models.DateTimeField()

    class Meta:
        constraints = [
            models.CheckConstraint(
                condition=Q(version__gte=1), name="note_revision_positive_version"
            ),
            models.UniqueConstraint(
                fields=["note", "version"], name="note_revision_once"
            ),
        ]
