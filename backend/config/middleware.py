import logging
import time
import uuid


logger = logging.getLogger("ays.request")


class RequestContextMiddleware:
    def __init__(self, get_response): self.get_response = get_response

    def __call__(self, request):
        supplied = request.headers.get("X-Request-ID", "")
        try: request_id = str(uuid.UUID(supplied))
        except (ValueError, TypeError, AttributeError): request_id = str(uuid.uuid4())
        request.request_id = request_id; started = time.monotonic()
        response = self.get_response(request)
        response["X-Request-ID"] = request_id
        logger.info("request complete", extra={"request_id": request_id, "method": request.method, "path": request.path, "status": response.status_code, "duration_ms": round((time.monotonic()-started)*1000, 2)})
        return response
