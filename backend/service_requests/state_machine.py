from .exceptions import RequestInvalidTransition
from .models import RequestStatus

class ServiceRequestStateMachine:
    ALLOWED={
        RequestStatus.NEW:{RequestStatus.ASSIGNED,RequestStatus.CANCELLED},
        RequestStatus.ASSIGNED:{RequestStatus.IN_PROGRESS,RequestStatus.CANCELLED},
        RequestStatus.IN_PROGRESS:{RequestStatus.WAITING_REQUESTER,RequestStatus.WAITING_EXTERNAL,RequestStatus.RESOLVED,RequestStatus.CANCELLED},
        RequestStatus.WAITING_REQUESTER:{RequestStatus.IN_PROGRESS,RequestStatus.CANCELLED},
        RequestStatus.WAITING_EXTERNAL:{RequestStatus.IN_PROGRESS,RequestStatus.CANCELLED},
        RequestStatus.RESOLVED:{RequestStatus.CLOSED,RequestStatus.IN_PROGRESS},
        RequestStatus.CLOSED:{RequestStatus.IN_PROGRESS}, RequestStatus.CANCELLED:set(),
    }
    @classmethod
    def validate(cls,old,new):
        if new not in cls.ALLOWED.get(old,set()): raise RequestInvalidTransition(f"Transition {old} -> {new} is forbidden.")

