import json
import logging
import uuid
from datetime import UTC, datetime


class SafeJsonFormatter(logging.Formatter):
    def format(self, record):
        return json.dumps(
            {
                "timestamp": datetime.now(UTC).isoformat(),
                "level": record.levelname,
                "event": getattr(record, "event", "application"),
                "request_id": getattr(record, "request_id", None),
                "outcome": getattr(
                    record, "outcome", "error" if record.levelno >= 40 else "info"
                ),
            }
        )


class RequestLogMiddleware:
    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        request.request_id = str(uuid.uuid4())
        response = self.get_response(request)
        response["X-Request-ID"] = request.request_id
        response["Cache-Control"] = "no-store"
        logging.getLogger("common_thread").info(
            "request",
            extra={
                "event": "http_request",
                "request_id": request.request_id,
                "outcome": str(response.status_code),
            },
        )
        return response


class PersonApiInputMiddleware:
    """Bound the API body before CSRF can parse form or multipart media."""

    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        if request.path == "/api/v1/people/" and request.method == "POST":
            from django.core.exceptions import PermissionDenied, RequestDataTooBig

            from .services import workspace_for
            from .views import error

            try:
                workspace_for(request.user)
            except PermissionDenied:
                return error("unauthenticated", 401, "Authentication required")
            try:
                if len(request.body) > 16384:
                    return error("payload_too_large", 413)
            except RequestDataTooBig:
                return error("payload_too_large", 413)
            if request.content_type != "application/json":
                return error("unsupported_media_type", 415)
        return self.get_response(request)
