from .exceptions import TaskInvalidTransition
from .models import TaskStatus


class TaskStateMachine:
    ALLOWED = {
        TaskStatus.DRAFT: {TaskStatus.OPEN, TaskStatus.CANCELLED},
        TaskStatus.OPEN: {TaskStatus.IN_PROGRESS, TaskStatus.CANCELLED},
        TaskStatus.IN_PROGRESS: {TaskStatus.WAITING, TaskStatus.REVIEW, TaskStatus.COMPLETED, TaskStatus.CANCELLED},
        TaskStatus.WAITING: {TaskStatus.IN_PROGRESS, TaskStatus.CANCELLED},
        TaskStatus.REVIEW: {TaskStatus.COMPLETED, TaskStatus.IN_PROGRESS, TaskStatus.CANCELLED},
        TaskStatus.COMPLETED: {TaskStatus.IN_PROGRESS},
        TaskStatus.CANCELLED: set(),
    }

    @classmethod
    def validate(cls, from_status, to_status):
        if to_status not in cls.ALLOWED.get(from_status, set()):
            raise TaskInvalidTransition(f"Переход {from_status} → {to_status} запрещён.")
