from rest_framework.exceptions import APIException

class RequestBusinessError(APIException):
    status_code=400; default_code="request_business_error"
    def __init__(self,message=None,*,code=None):
        self.default_code=code or self.default_code; super().__init__(message or "Request operation failed.",code=self.default_code); self.code=self.default_code
class RequestInvalidTransition(RequestBusinessError): default_code="request_invalid_transition"
class RequestVersionConflict(RequestBusinessError): status_code=409; default_code="request_version_conflict"

