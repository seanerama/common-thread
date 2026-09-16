import hashlib
import json
import logging
from datetime import timedelta
from functools import wraps

from django.conf import settings
from django.contrib.auth import authenticate, login, logout
from django.core.exceptions import PermissionDenied, RequestDataTooBig, ValidationError
from django.db import connection, transaction
from django.db.migrations.executor import MigrationExecutor
from django.http import Http404, HttpResponse, JsonResponse
from django.shortcuts import redirect, render
from django.utils import timezone
from django.views.decorators.http import require_http_methods

from . import services
from .forms import (
    ContactPointForm,
    PartyCreateForm,
    PartyForm,
    PersonForm,
    RelationshipCloseForm,
    RelationshipCreateForm,
    RelationshipForm,
    VersionForm,
)
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
    if not settings.PEOPLE_MANAGEMENT_ENABLED:
        return render(
            request, "people.html", {"people": services.list_people(request.user)}
        )
    query = request.GET.get("q", "")
    archived = request.GET.get("archived", "exclude")
    try:
        page = services.search_people(
            request.user, q=query, archived=archived, page=request.GET.get("page", "1")
        )
    except ValidationError:
        return render(
            request,
            "people.html",
            {
                "management_enabled": True,
                "q": query,
                "archived": archived,
                "query_error": (
                    "Enter a search of up to 200 characters, a valid archive "
                    "filter, and a positive page number."
                ),
            },
            status=400,
        )
    return render(
        request,
        "people.html",
        {
            "people": page,
            "page_obj": page,
            "management_enabled": True,
            "q": query,
            "archived": archived,
        },
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
    person = services.get_person(request.user, person_id)
    context = {
        "person": person,
        "management_enabled": settings.PEOPLE_MANAGEMENT_ENABLED,
    }
    if settings.PEOPLE_MANAGEMENT_ENABLED:
        context["contact_points"] = services.list_contact_points(
            request.user, person_id
        )
    context["notes_enabled"] = settings.CONTEXT_NOTES_ENABLED
    if settings.CONTEXT_NOTES_ENABLED:
        context["notes"] = services.list_context_notes(request.user, person_id)
    context["relationships_enabled"] = settings.RELATIONSHIPS_ENABLED
    if settings.RELATIONSHIPS_ENABLED:
        try:
            if set(request.GET) - {
                "relationships_page",
                "relationships_ended_page",
            } or any(len(request.GET.getlist(key)) != 1 for key in request.GET):
                raise ValidationError("Invalid relationship page")
            context["relationships"], context["ended_relationships"] = (
                services.relationship_panels(
                    request.user,
                    person_id,
                    request.GET.get("relationships_page", "1"),
                    request.GET.get("relationships_ended_page", "1"),
                )
            )
        except ValidationError:
            return HttpResponse("Invalid relationship page", status=400)
    return render(request, "person_detail.html", context)


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
    except (ValueError, UnicodeDecodeError, RecursionError):
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


def management_enabled(view):
    @wraps(view)
    def wrapped(request, *args, **kwargs):
        if not settings.PEOPLE_MANAGEMENT_ENABLED:
            raise Http404
        return view(request, *args, **kwargs)

    return wrapped


def workflow_form(request, person, form, title, save, submit_label="Save changes"):
    status = 200
    conflict = False
    if request.method == "POST" and form.is_valid():
        try:
            save(form.cleaned_data)
        except services.Conflict:
            status = 409
            conflict = True
            form.add_error(
                None,
                "This record changed. Reload and review the latest version before "
                "saving again. Your submitted values are shown below.",
            )
        except ValidationError as exc:
            if hasattr(exc, "message_dict"):
                for field, messages in exc.message_dict.items():
                    form.add_error(field if field in form.fields else None, messages)
            else:
                form.add_error(None, exc)
        else:
            return redirect303(f"/people/{person.id}/")
    return render(
        request,
        "person_form.html",
        {
            "person": person,
            "form": form,
            "title": title,
            "submit_label": submit_label,
            "conflict": conflict,
        },
        status=status,
    )


@require_http_methods(["GET", "POST"])
@authorized
@management_enabled
def person_edit(request, person_id):
    person = services.get_person(request.user, person_id)
    form = PersonForm(
        request.POST if request.method == "POST" else None,
        initial={
            "display_name": person.display_name,
            "is_client": person.is_client,
            "expected_version": person.version,
        },
    )
    return workflow_form(
        request,
        person,
        form,
        "Edit person",
        lambda data: services.update_person(request.user, person_id, **data),
        "Save person",
    )


@require_http_methods(["POST"])
@authorized
@management_enabled
def person_archive(request, person_id, archived=True):
    person = services.get_person(request.user, person_id)
    title = "Archive person" if archived else "Restore person"
    return workflow_form(
        request,
        person,
        VersionForm(request.POST),
        title,
        lambda data: services.set_person_archived(
            request.user, person_id, archived=archived, **data
        ),
        title,
    )


@require_http_methods(["GET", "POST"])
@authorized
@management_enabled
def contact_point_new(request, person_id):
    person = services.get_person(request.user, person_id)
    form = ContactPointForm(
        request.POST if request.method == "POST" else None,
        initial={"expected_version": person.version, "kind": "email"},
    )
    return workflow_form(
        request,
        person,
        form,
        "Add contact point",
        lambda data: services.create_contact_point(request.user, person_id, **data),
        "Save contact",
    )


@require_http_methods(["GET", "POST"])
@authorized
@management_enabled
def contact_point_edit(request, person_id, point_id):
    person = services.get_person(request.user, person_id)
    point = services.get_contact_point(request.user, person_id, point_id)
    form = ContactPointForm(
        request.POST if request.method == "POST" else None,
        initial={
            "expected_version": point.version,
            "kind": point.kind,
            "value": point.value,
            "label": point.label or "",
        },
    )
    return workflow_form(
        request,
        person,
        form,
        "Edit contact point",
        lambda data: services.update_contact_point(
            request.user, person_id, point_id, **data
        ),
        "Save contact",
    )


@require_http_methods(["POST"])
@authorized
@management_enabled
def contact_point_archive(request, person_id, point_id):
    person = services.get_person(request.user, person_id)
    services.get_contact_point(request.user, person_id, point_id)
    return workflow_form(
        request,
        person,
        VersionForm(request.POST),
        "Archive contact point",
        lambda data: services.archive_contact_point(
            request.user, person_id, point_id, **data
        ),
        "Archive contact point",
    )


def notes_enabled(view):
    @wraps(view)
    def wrapped(request, *args, **kwargs):
        if not settings.CONTEXT_NOTES_ENABLED:
            raise Http404
        return view(request, *args, **kwargs)

    return wrapped


def party_directory_enabled(view):
    @wraps(view)
    def wrapped(request, *args, **kwargs):
        if not settings.PARTY_DIRECTORY_ENABLED:
            raise Http404
        return view(request, *args, **kwargs)

    return wrapped


PARTY_UI = {
    "organization": ("organizations", "Organization", "Organizations"),
    "household": ("households", "Household", "Households"),
}


def _party_ui(kind):
    try:
        return PARTY_UI[kind]
    except KeyError:
        raise Http404 from None


def _strict_form_post(request, allowed):
    return not (set(request.POST) - (set(allowed) | {"csrfmiddlewaretoken"})) and all(
        len(request.POST.getlist(key)) == 1 for key in request.POST
    )


@require_http_methods(["GET"])
@authorized
@party_directory_enabled
def party_list(request, kind):
    prefix, singular, plural = _party_ui(kind)
    query = request.GET.get("q", "")
    archived = request.GET.get("archived", "exclude")
    try:
        if set(request.GET) - {"q", "archived", "page"} or any(
            len(request.GET.getlist(key)) != 1 for key in request.GET
        ):
            raise ValidationError("Invalid query")
        page = services.search_typed_parties(
            request.user, kind, query, archived, request.GET.get("page", "1")
        )
    except ValidationError:
        return render(
            request,
            "party_list.html",
            {
                "prefix": prefix,
                "plural": plural,
                "singular_lower": singular.lower(),
                "q": query,
                "archived": archived,
                "query_error": (
                    "Enter a search of up to 200 characters, a valid archive "
                    "filter, and a positive page number."
                ),
            },
            status=400,
        )
    return render(
        request,
        "party_list.html",
        {
            "prefix": prefix,
            "plural": plural,
            "singular_lower": singular.lower(),
            "parties": page,
            "page_obj": page,
            "q": query,
            "archived": archived,
        },
    )


@require_http_methods(["GET", "POST"])
@authorized
@party_directory_enabled
def party_new(request, kind):
    prefix, singular, _ = _party_ui(kind)
    if request.method == "POST" and not _strict_form_post(
        request, {"display_name", "is_client"}
    ):
        return HttpResponse("Invalid request", status=400)
    form = PartyCreateForm(request.POST if request.method == "POST" else None)
    if request.method == "POST" and form.is_valid():
        try:
            party = services.create_typed_party(request.user, kind, **form.cleaned_data)
        except ValidationError as exc:
            for field, messages in exc.message_dict.items():
                form.add_error(field if field in form.fields else None, messages)
        else:
            return redirect303(f"/{prefix}/{party.id}/")
    return render(
        request,
        "party_form.html",
        {
            "form": form,
            "title": f"Add {singular.lower()}",
            "submit_label": f"Save {singular.lower()}",
            "cancel_path": f"/{prefix}/",
        },
    )


@require_http_methods(["GET"])
@authorized
@party_directory_enabled
def party_detail(request, kind, party_id):
    prefix, singular, _ = _party_ui(kind)
    party = services.get_typed_party(request.user, kind, party_id)
    context = {
        "party": party,
        "prefix": prefix,
        "singular": singular,
        "singular_lower": singular.lower(),
        "relationships_enabled": settings.RELATIONSHIPS_ENABLED,
    }
    if settings.RELATIONSHIPS_ENABLED:
        try:
            if set(request.GET) - {
                "relationships_page",
                "relationships_ended_page",
            } or any(len(request.GET.getlist(key)) != 1 for key in request.GET):
                raise ValidationError("Invalid relationship page")
            context["relationships"], context["ended_relationships"] = (
                services.relationship_panels(
                    request.user,
                    party_id,
                    request.GET.get("relationships_page", "1"),
                    request.GET.get("relationships_ended_page", "1"),
                )
            )
        except ValidationError:
            return HttpResponse("Invalid relationship page", status=400)
    return render(
        request,
        "party_detail.html",
        context,
    )


def _party_workflow_form(request, kind, party, form, title, save, submit_label):
    prefix, singular, _ = _party_ui(kind)
    status = 200
    conflict = False
    if request.method == "POST" and form.is_valid():
        try:
            save(form.cleaned_data)
        except services.Conflict:
            status, conflict = 409, True
            form.add_error(
                None,
                "This record changed. Reload and review the latest version before "
                "saving again. Your submitted values are shown below.",
            )
        except ValidationError as exc:
            for field, messages in exc.message_dict.items():
                form.add_error(field if field in form.fields else None, messages)
        else:
            return redirect303(f"/{prefix}/{party.id}/")
    return render(
        request,
        "party_form.html",
        {
            "party": party,
            "form": form,
            "title": title,
            "submit_label": submit_label,
            "conflict": conflict,
            "cancel_path": f"/{prefix}/{party.id}/",
            "singular_lower": singular.lower(),
        },
        status=status,
    )


@require_http_methods(["GET", "POST"])
@authorized
@party_directory_enabled
def party_edit(request, kind, party_id):
    _, singular, _ = _party_ui(kind)
    party = services.get_typed_party(request.user, kind, party_id)
    if request.method == "POST" and not _strict_form_post(
        request, {"display_name", "is_client", "expected_version"}
    ):
        return HttpResponse("Invalid request", status=400)
    form = PartyForm(
        request.POST if request.method == "POST" else None,
        initial={
            "display_name": party.display_name,
            "is_client": party.is_client,
            "expected_version": party.version,
        },
    )
    return _party_workflow_form(
        request,
        kind,
        party,
        form,
        f"Edit {singular.lower()}",
        lambda data: services.update_typed_party(request.user, kind, party_id, **data),
        f"Save {singular.lower()}",
    )


@require_http_methods(["POST"])
@authorized
@party_directory_enabled
def party_archive(request, kind, party_id, archived=True):
    _, singular, _ = _party_ui(kind)
    party = services.get_typed_party(request.user, kind, party_id)
    if not _strict_form_post(request, {"expected_version"}):
        return HttpResponse("Invalid request", status=400)
    action = "Archive" if archived else "Restore"
    return _party_workflow_form(
        request,
        kind,
        party,
        VersionForm(request.POST),
        f"{action} {singular.lower()}",
        lambda data: services.set_typed_party_archived(
            request.user, kind, party_id, archived=archived, **data
        ),
        f"{action} {singular.lower()}",
    )


@require_http_methods(["GET", "POST"])
@authorized
@notes_enabled
def context_note_form(request, person_id, note_id=None):
    from .forms import ContextNoteForm

    person = services.get_person(request.user, person_id)
    note = (
        services.get_context_note(request.user, person_id, note_id) if note_id else None
    )
    if request.method == "POST":
        allowed = {"body", "source", "expected_version", "csrfmiddlewaretoken"}
        if set(request.POST) - allowed or any(
            len(request.POST.getlist(key)) != 1 for key in request.POST
        ):
            return HttpResponse("Invalid request", status=400)
    initial = {"expected_version": note.version if note else person.version}
    if note:
        initial.update(body=note.body, source=note.source)
    form = ContextNoteForm(
        request.POST if request.method == "POST" else None, initial=initial
    )
    return workflow_form(
        request,
        person,
        form,
        "Correct note" if note else "Add context note",
        lambda data: (
            services.update_context_note(request.user, person_id, note_id, **data)
            if note
            else services.create_context_note(request.user, person_id, **data)
        ),
        "Save note",
    )


@require_http_methods(["GET"])
@authorized
@notes_enabled
def context_note_history(request, person_id, note_id):
    person = services.get_person(request.user, person_id)
    note = services.get_context_note(request.user, person_id, note_id)
    revisions = services.context_note_history(request.user, person_id, note_id)
    return render(
        request,
        "note_history.html",
        {"person": person, "note": note, "revisions": revisions},
    )


def relationships_enabled(view):
    @wraps(view)
    def wrapped(request, *args, **kwargs):
        if not settings.RELATIONSHIPS_ENABLED:
            raise Http404
        return view(request, *args, **kwargs)

    return wrapped


def _relationship_post_valid(request, allowed):
    return _strict_form_post(request, allowed)


def _relationship_form_response(
    request, relationship, form, title, save, submit_label, extra_context=None
):
    status = 200
    conflict = False
    if request.method == "POST" and form.is_valid():
        try:
            saved = save(form.cleaned_data)
        except services.Conflict:
            status, conflict = 409, True
            form.add_error(
                None,
                "This record changed. Reload and review the latest version before "
                "saving again. Your submitted values are shown below.",
            )
        except ValidationError as exc:
            endpoint_error = any(
                field in exc.message_dict
                for field in ("party", "from_party_id", "to_party_id")
            )
            if endpoint_error:
                return HttpResponse("Invalid related party", status=400)
            for field, messages in exc.message_dict.items():
                form.add_error(field if field in form.fields else None, messages)
        else:
            return redirect303(f"/relationships/{saved.id}/")
    context = {
        "relationship": relationship,
        "form": form,
        "title": title,
        "submit_label": submit_label,
        "conflict": conflict,
        "cancel_path": (
            f"/relationships/{relationship.id}/" if relationship else "/people/"
        ),
    }
    context.update(extra_context or {})
    return render(request, "relationship_form.html", context, status=status)


@require_http_methods(["GET", "POST"])
@authorized
@relationships_enabled
def relationship_new(request):
    if request.method == "POST" and not _relationship_post_valid(
        request,
        {"from_party_id", "to_party_id", "kind", "role", "starts_on", "ends_on"},
    ):
        return HttpResponse("Invalid request", status=400)
    try:
        selector_keys = {"from_q", "from_page", "to_q", "to_page"}
        if set(request.GET) - selector_keys or any(
            len(request.GET.getlist(key)) != 1 for key in request.GET
        ):
            raise ValidationError("Invalid selector query")
        from_choices = services.relationship_selector(
            request.user,
            request.GET.get("from_q", ""),
            request.GET.get("from_page", "1"),
        )
        to_choices = services.relationship_selector(
            request.user,
            request.GET.get("to_q", ""),
            request.GET.get("to_page", "1"),
        )
    except ValidationError:
        return HttpResponse("Invalid selector query", status=400)
    form = RelationshipCreateForm(
        request.POST if request.method == "POST" else None,
        from_parties=from_choices,
        to_parties=to_choices,
        initial={"kind": "employment"},
    )
    if request.method == "POST" and not form.is_valid():
        # Choice failures use the generic response for scoped lookup failures.
        if "from_party_id" in form.errors or "to_party_id" in form.errors:
            return HttpResponse("Invalid related party", status=400)
    return _relationship_form_response(
        request,
        None,
        form,
        "Add relationship",
        lambda data: services.create_relationship(request.user, **data),
        "Save relationship",
        {"from_selector_page": from_choices, "to_selector_page": to_choices},
    )


@require_http_methods(["GET"])
@authorized
@relationships_enabled
def relationship_detail(request, relationship_id):
    relationship = services.get_relationship(request.user, relationship_id)
    return render(
        request,
        "relationship_detail.html",
        {
            "relationship": relationship,
            "party_directory_enabled": settings.PARTY_DIRECTORY_ENABLED,
        },
    )


@require_http_methods(["GET", "POST"])
@authorized
@relationships_enabled
def relationship_edit(request, relationship_id):
    relationship = services.get_relationship(request.user, relationship_id)
    if request.method == "POST" and not _relationship_post_valid(
        request, {"kind", "role", "starts_on", "ends_on", "expected_version"}
    ):
        return HttpResponse("Invalid request", status=400)
    form = RelationshipForm(
        request.POST if request.method == "POST" else None,
        initial={
            "kind": relationship.kind,
            "role": relationship.role or "",
            "starts_on": relationship.starts_on,
            "ends_on": relationship.ends_on,
            "expected_version": relationship.version,
        },
    )
    return _relationship_form_response(
        request,
        relationship,
        form,
        "Correct relationship",
        lambda data: services.update_relationship(
            request.user, relationship_id, **data
        ),
        "Save relationship",
    )


@require_http_methods(["POST"])
@authorized
@relationships_enabled
def relationship_close(request, relationship_id):
    relationship = services.get_relationship(request.user, relationship_id)
    if not _relationship_post_valid(request, {"ends_on", "expected_version"}):
        return HttpResponse("Invalid request", status=400)
    form = RelationshipCloseForm(request.POST)
    return _relationship_form_response(
        request,
        relationship,
        form,
        "Close relationship",
        lambda data: services.close_relationship(request.user, relationship_id, **data),
        "Close relationship",
    )
