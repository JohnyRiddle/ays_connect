from rest_framework.exceptions import APIException

class SLAError(APIException):
    status_code=400;default_code="sla_invalid"
    def __init__(self,message=None,*,code=None):self.default_code=code or self.default_code;super().__init__(message or "Invalid SLA configuration.",code=self.default_code);self.code=self.default_code
class SLAPolicyAmbiguous(SLAError):default_code="sla_policy_ambiguous"

