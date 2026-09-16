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


class LoginAttempt(models.Model):
    key = models.CharField(max_length=64, primary_key=True)
    failures = models.PositiveIntegerField(default=0)
    window_start = models.DateTimeField()
