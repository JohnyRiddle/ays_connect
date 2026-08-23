from rest_framework.exceptions import APIException


class TaskBusinessError(APIException):
    status_code = 400
    default_code = "task_business_error"

    def __init__(self, message=None, *, code=None):
        self.default_code = code or self.default_code
        super().__init__(message or self.default_detail, code=self.default_code)
        self.code = self.default_code


class TaskInvalidTransition(TaskBusinessError):
    default_code = "task_invalid_transition"


class TaskVersionConflict(TaskBusinessError):
    status_code = 409
    default_code = "task_version_conflict"


class TaskValidationError(TaskBusinessError):
    pass
