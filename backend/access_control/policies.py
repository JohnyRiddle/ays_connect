from .models import EmployeeRole, Scope


class EmployeeAccessPolicy:
    @staticmethod
    def allows(*, actor, target, grant: EmployeeRole, scope: str) -> bool:
        if scope == Scope.GLOBAL:
            return True
        if scope == Scope.OWN:
            return actor.pk == target.pk
        if scope == Scope.LEGAL_ENTITY:
            context = grant.legal_entity_id or actor.legal_entity_id
            return bool(context and target.legal_entity_id == context)
        if scope == Scope.ORG_UNIT:
            context = grant.org_unit_id or actor.org_unit_id
            return bool(context and target.org_unit_id == context)
        if scope == Scope.TEAM:
            return target.manager_id == actor.pk or actor.manager_id == target.manager_id
        return False


class OrganizationAccessPolicy:
    @staticmethod
    def allows(*, actor, target, grant: EmployeeRole, scope: str) -> bool:
        if scope == Scope.GLOBAL:
            return True
        if scope == Scope.LEGAL_ENTITY:
            return bool(grant.legal_entity_id and getattr(target, "legal_entity_id", None) == grant.legal_entity_id)
        if scope == Scope.ORG_UNIT:
            target_id = getattr(target, "pk", None) if target.__class__.__name__ == "OrgUnit" else getattr(target, "org_unit_id", None)
            return bool(grant.org_unit_id and target_id == grant.org_unit_id)
        return False
