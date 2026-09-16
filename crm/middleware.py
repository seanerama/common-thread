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
