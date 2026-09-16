import hashlib
import json
import logging
from datetime import timedelta
from functools import wraps

from django.contrib.auth import authenticate, login, logout
from django.core.exceptions import PermissionDenied, RequestDataTooBig, ValidationError
from django.db import connection, transaction
from django.db.migrations.executor import MigrationExecutor
from django.http import Http404, HttpResponse, JsonResponse
from django.shortcuts import redirect, render
from django.utils import timezone
from django.views.decorators.http import require_http_methods

from . import services
from .models import LoginAttempt


def error(code, status, message="Invalid request", fields=None):
    return JsonResponse(
        {"error": {"code": code, "message": message, "fields": fields or {}}},
        status=status,
    )


def csrf_failure(request, reason=""):
    if request.path.startswith("/api/"):
        try:
            services.workspace_for(request.user)
        except PermissionDenied:
            return error("unauthenticated", 401, "Authentication required")
        return error("csrf_failed", 403)
    return HttpResponse(
        "Request verification failed. Reload and try again.", status=403
    )


def not_found(request, exception=None):
    if request.path.startswith("/api/"):
        return error("not_found", 404, "Not found")
    return HttpResponse("Not found", status=404)


def server_error(request):
    if request.path.startswith("/api/"):
        return error("internal_error", 500, "Internal error")
    return HttpResponse("Something went wrong", status=500)


def authorized(view):
    @wraps(view)
    def wrapped(request, *args, **kwargs):
        try:
            services.workspace_for(request.user)
        except PermissionDenied:
            if request.path.startswith("/api/"):
                return error("unauthenticated", 401, "Authentication required")
            return redirect("/login/")
        return view(request, *args, **kwargs)

    return wrapped


def envelope(party):
    return {
        "data": {
            "id": str(party.id),
            "display_name": party.display_name,
            "is_client": party.is_client,
            "created_at": party.created_at.isoformat().replace("+00:00", "Z"),
            "updated_at": party.updated_at.isoformat().replace("+00:00", "Z"),
            "archived_at": party.archived_at.isoformat().replace("+00:00", "Z")
            if party.archived_at
            else None,
            "version": party.version,
        }
    }


def redirect303(path):
    response = HttpResponse(status=303)
    response["Location"] = path
    return response


@require_http_methods(["GET", "POST"])
def login_view(request):
    message = None
    if request.method == "POST":
        username = request.POST.get("username", "")
        password = request.POST.get("password", "")
        # Only REMOTE_ADDR is trusted. Forwarded IPs cannot evade throttling.
        keys = [
            ("account:" + username.casefold(), 5),
            ("source:" + request.META.get("REMOTE_ADDR", "unknown"), 20),
        ]
        now = timezone.now()
        with transaction.atomic():
            rows = []
            for value, limit in keys:
                key = hashlib.sha256(value.encode()).hexdigest()
                LoginAttempt.objects.get_or_create(
                    key=key, defaults={"window_start": now}
                )
                row = LoginAttempt.objects.select_for_update().get(key=key)
                if row.window_start <= now - timedelta(seconds=900):
                    row.failures = 0
                    row.window_start = now
                    row.save()
                rows.append((row, limit))
            limited = [row for row, limit in rows if row.failures >= limit]
            if limited:
                response = render(
                    request,
                    "login.html",
                    {"error": "Too many attempts. Try again later."},
                    status=429,
                )
                response["Retry-After"] = str(
                    max(
                        1,
                        max(
                            int(
                                (
                                    row.window_start + timedelta(seconds=900) - now
                                ).total_seconds()
                            )
                            for row in limited
                        ),
                    )
                )
                return response
            user = authenticate(request, username=username, password=password)
            if user is not None:
                try:
                    services.workspace_for(user)
                except PermissionDenied:
                    user = None
            if user is None:
                for row, _ in rows:
                    row.failures += 1
                    row.save(update_fields=["failures"])
                message = "Invalid username or password."
            else:
                login(request, user)
                # datetime expiry enforces an absolute lifetime even if session changes.
                request.session.set_expiry(now + timedelta(hours=12))
                return redirect("/people/")
    return render(request, "login.html", {"error": message})


@require_http_methods(["POST"])
def logout_view(request):
    logout(request)
    return redirect("/login/")


@require_http_methods(["GET"])
@authorized
def people(request):
    return render(
        request, "people.html", {"people": services.list_people(request.user)}
    )


@require_http_methods(["GET", "POST"])
@authorized
def person_new(request):
    fields = {}
    if request.method == "POST":
        try:
            person = services.create_person(
                request.user, request.POST.get("display_name")
            )
        except ValidationError as exc:
            fields = exc.message_dict
        else:
            return redirect303(f"/people/{person.id}/")
    return render(
        request,
        "person_new.html",
        {"errors": fields, "display_name": request.POST.get("display_name", "")},
    )


@require_http_methods(["GET"])
@authorized
def person_detail(request, person_id):
    return render(
        request,
        "person_detail.html",
        {"person": services.get_person(request.user, person_id)},
    )


@require_http_methods(["POST"])
@authorized
def api_create(request):
    try:
        if int(request.META.get("CONTENT_LENGTH") or 0) > 16384:
            return error("payload_too_large", 413)
        if request.content_type != "application/json":
            return error("unsupported_media_type", 415)
        raw = request.body
        if len(raw) > 16384:
            return error("payload_too_large", 413)
        data = json.loads(raw)
        if not isinstance(data, dict) or set(data) != {"display_name"}:
            return error("validation_error", 400)
        person = services.create_person(request.user, data["display_name"])
    except RequestDataTooBig:
        return error("payload_too_large", 413)
    except (ValueError, UnicodeDecodeError):
        return error("validation_error", 400)
    except ValidationError as exc:
        return error("validation_error", 400, fields=exc.message_dict)
    response = JsonResponse(envelope(person), status=201)
    response["Location"] = f"/api/v1/people/{person.id}/"
    return response


@require_http_methods(["GET"])
@authorized
def api_detail(request, person_id):
    try:
        person = services.get_person(request.user, person_id)
    except Http404:
        return error("not_found", 404, "Not found")
    return JsonResponse(envelope(person))


@require_http_methods(["GET"])
def live(request):
    return JsonResponse({"status": "ok"})


@require_http_methods(["GET"])
def ready(request):
    try:
        with connection.cursor() as cursor:
            cursor.execute("SELECT 1")
        executor = MigrationExecutor(connection)
        if executor.migration_plan(executor.loader.graph.leaf_nodes()):
            return JsonResponse({"status": "not_ready"}, status=503)
    except Exception:
        logging.getLogger("common_thread").error(
            "readiness failure", extra={"event": "readiness", "outcome": "not_ready"}
        )
        return JsonResponse({"status": "not_ready"}, status=503)
    return JsonResponse({"status": "ready"})
