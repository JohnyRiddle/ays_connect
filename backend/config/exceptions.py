from rest_framework.views import exception_handler


def public_message(value):
    if isinstance(value, str):
        return value
    if isinstance(value, dict):
        if "detail" in value:
            return public_message(value["detail"])
        for item in value.values():
            message = public_message(item)
            if message:
                return message
    if isinstance(value, (list, tuple)):
        for item in value:
            message = public_message(item)
            if message:
                return message
    return ""


def api_exception_handler(exc, context):
    response = exception_handler(exc, context)
    if response is None:
        return None
    if isinstance(response.data, dict) and "error" in response.data:
        return response
    code = getattr(exc, "code", None) or getattr(exc, "default_code", "request_failed")
    details = response.data
    message = public_message(details) or "Не удалось выполнить запрос."
    response.data = {"error": {"code": str(code), "message": str(message), "details": details}}
    return response
