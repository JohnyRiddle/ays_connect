from rest_framework.views import exception_handler


def api_exception_handler(exc, context):
    response = exception_handler(exc, context)
    if response is None:
        return None
    if isinstance(response.data, dict) and "error" in response.data:
        return response
    code = getattr(exc, "code", None) or getattr(exc, "default_code", "request_failed")
    details = response.data
    message = details.get("detail", str(exc)) if isinstance(details, dict) else str(exc)
    response.data = {"error": {"code": str(code), "message": str(message), "details": details}}
    return response
