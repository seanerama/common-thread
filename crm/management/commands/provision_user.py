import os

from django.contrib.auth.password_validation import validate_password
from django.core.exceptions import ValidationError
from django.core.management.base import BaseCommand, CommandError
from django.db import transaction

from crm.models import Membership, User, Workspace


class Command(BaseCommand):
    help = "Provision a private owner; existing credentials are never overwritten."

    def add_arguments(self, parser):
        parser.add_argument("--username", required=True)
        parser.add_argument("--workspace", required=True)

    @transaction.atomic
    def handle(self, *args, **options):
        username = options["username"]
        if (
            not username
            or len(username) > 150
            or not options["workspace"].strip()
            or len(options["workspace"]) > 200
        ):
            raise CommandError("Invalid username or workspace name")
        user = User.objects.filter(username=username).first()
        if user is None:
            password = os.environ.get("COMMON_THREAD_PASSWORD")
            if not password:
                raise CommandError("Set COMMON_THREAD_PASSWORD for a new user")
            user = User(username=username)
            try:
                user.full_clean(exclude=["password"])
                validate_password(password, user)
            except ValidationError as exc:
                raise CommandError("Invalid user or password") from exc
            user.set_password(password)
            user.save()
        if not Membership.objects.filter(user=user).exists():
            workspace = Workspace.objects.create(name=options["workspace"].strip())
            Membership.objects.create(user=user, workspace=workspace)
        self.stdout.write("Private owner provisioned (existing credentials preserved).")
