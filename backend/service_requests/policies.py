from django.db.models import Q
from django.utils import timezone
from access_control.models import EmployeeRole, Scope

class ServiceRequestAccessPolicy:
    @staticmethod
    def _grants(employee,permission):
        now=timezone.now()
        return EmployeeRole.objects.filter(employee=employee,is_active=True,role__is_active=True,role__permission_grants__permission__code=permission).filter(Q(active_from__isnull=True)|Q(active_from__lte=now),Q(active_until__isnull=True)|Q(active_until__gte=now)).select_related("org_unit","legal_entity","location","role").distinct()
    @classmethod
    def allows(cls,*,employee,permission,request=None):
        if not employee or not employee.is_active:return False
        for grant in cls._grants(employee,permission):
            for scope in grant.role.permission_grants.filter(permission__code=permission).values_list("scope",flat=True):
                if request is None or scope==Scope.GLOBAL:return True
                participating=employee.pk in {request.requester_id,request.responsible_employee_id,request.assigned_employee_id} or request.created_by_id==getattr(employee,"user_id",None) or request.watcher_records.filter(employee=employee,employee__is_active=True,removed_at__isnull=True).exists()
                if scope==Scope.PARTICIPATING and participating:return True
                if scope==Scope.OWN and request.requester_id==employee.pk:return True
                if scope==Scope.ORG_UNIT and request.org_unit_id==(grant.org_unit_id or employee.org_unit_id):return True
                if scope==Scope.LEGAL_ENTITY and request.legal_entity_id==(grant.legal_entity_id or employee.legal_entity_id):return True
                if scope==Scope.TEAM and request.assigned_employee and request.assigned_employee.manager_id==employee.pk:return True
        return False
    @classmethod
    def visibility_query(cls,*,employee,permission="request.view"):
        q=Q(pk__in=[])
        for grant in cls._grants(employee,permission):
            for scope in grant.role.permission_grants.filter(permission__code=permission).values_list("scope",flat=True):
                if scope==Scope.GLOBAL:return Q()
                if scope==Scope.PARTICIPATING:q|=Q(requester=employee)|Q(responsible_employee=employee)|Q(assigned_employee=employee)|Q(created_by_id=getattr(employee,"user_id",None))|Q(watcher_records__employee=employee,watcher_records__employee__is_active=True,watcher_records__removed_at__isnull=True)
                elif scope==Scope.OWN:q|=Q(requester=employee)
                elif scope==Scope.ORG_UNIT:q|=Q(org_unit_id=grant.org_unit_id or employee.org_unit_id)
                elif scope==Scope.LEGAL_ENTITY:q|=Q(legal_entity_id=grant.legal_entity_id or employee.legal_entity_id)
                elif scope==Scope.TEAM:q|=Q(assigned_employee__manager=employee)
        return q

    @classmethod
    def can_view_internal(cls,*,employee,request,kind="comment"):
        return cls.allows(employee=employee,permission=f"request.{kind}_internal",request=request)
