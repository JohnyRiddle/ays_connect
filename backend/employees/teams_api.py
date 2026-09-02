from django.db.models import Count, Q
from django.utils import timezone
from django.utils.dateparse import parse_datetime
from rest_framework import serializers, status, viewsets
from rest_framework.decorators import action
from rest_framework.exceptions import PermissionDenied
from rest_framework.permissions import BasePermission
from rest_framework.response import Response

from access_control.models import EmployeeRole, Scope
from access_control.services import PermissionService
from .assignment import AssignmentResolver, AssignmentTargetUnresolved
from .models import AssignmentTarget, Employee, Team, TeamMembership
from .teams import TeamConflict, TeamMembershipService, TeamService


class TeamMembershipSerializer(serializers.ModelSerializer):
    employee_name=serializers.CharField(source="employee.display_name",read_only=True)
    class Meta:
        model=TeamMembership
        fields="__all__"
        read_only_fields=("id","team","created_at","updated_at","created_by","ended_by","end_reason","version")


class TeamSerializer(serializers.ModelSerializer):
    members_summary=serializers.SerializerMethodField(); available_actions=serializers.SerializerMethodField()
    class Meta:
        model=Team
        fields="__all__"
        read_only_fields=("id","code","status","parent_team","owner_employee","lead_employee","valid_from","valid_to","is_assignable","version","created_at","updated_at","created_by","updated_by")
    def get_members_summary(self,obj):
        return {"active":getattr(obj,"active_members",obj.memberships.filter(valid_to__isnull=True).count()),"total":getattr(obj,"total_members",obj.memberships.count())}
    def get_available_actions(self,obj):
        lifecycle={"draft":["activate","close"],"active":["suspend","close"],"suspended":["resume","close"],"closed":[]}.get(obj.status,[])
        request=self.context.get("request")
        if not request or request.user.is_superuser:
            return lifecycle
        actor=getattr(request.user,"employee",None)
        result=[]
        for item in lifecycle:
            permission="people.team.close" if item=="close" else "people.team.manage"
            if _team_permission(actor,permission,obj): result.append(item)
        if _team_permission(actor,"people.team.update",obj): result.append("update")
        return result


def _team_grants(actor, permission):
    now=timezone.now()
    return EmployeeRole.objects.filter(
        employee=actor,is_active=True,role__is_active=True,
        role__permission_grants__permission__code=permission,
    ).filter(
        Q(active_from__isnull=True)|Q(active_from__lte=now),
        Q(active_until__isnull=True)|Q(active_until__gte=now),
    ).values("role__permission_grants__scope","org_unit_id","legal_entity_id","location_id")


def _team_permission(actor, permission, team):
    if not actor or not actor.is_active: return False
    for grant in _team_grants(actor,permission):
        scope=grant["role__permission_grants__scope"]
        if scope==Scope.GLOBAL: return True
        if scope in {Scope.OWN,Scope.TEAM} and TeamMembership.objects.filter(team=team,employee=actor,valid_to__isnull=True).exists(): return True
        if scope==Scope.ORG_UNIT and team.org_unit_id==(grant["org_unit_id"] or actor.org_unit_id): return True
        if scope==Scope.LEGAL_ENTITY and team.legal_entity_id==(grant["legal_entity_id"] or actor.legal_entity_id): return True
    return False


def visible_teams(user, permission="people.team.view"):
    qs=Team.objects.all()
    if user.is_superuser: return qs
    actor=getattr(user,"employee",None)
    if not actor: return qs.none()
    predicate=Q(pk__in=[])
    for grant in _team_grants(actor,permission):
        scope=grant["role__permission_grants__scope"]
        if scope==Scope.GLOBAL: return qs
        if scope in {Scope.OWN,Scope.TEAM}: predicate|=Q(memberships__employee=actor,memberships__valid_to__isnull=True)
        elif scope==Scope.ORG_UNIT: predicate|=Q(org_unit_id=grant["org_unit_id"] or actor.org_unit_id)
        elif scope==Scope.LEGAL_ENTITY: predicate|=Q(legal_entity_id=grant["legal_entity_id"] or actor.legal_entity_id)
    return qs.filter(predicate).distinct()


class TeamAPIPermission(BasePermission):
    def code(self, request, view):
        action=getattr(view,"action",None)
        if action=="create": return "people.team.create"
        if action in {"update","partial_update"}: return "people.team.update"
        if action=="close": return "people.team.close"
        if action=="members": return "people.team_membership.view" if request.method=="GET" else "people.team_membership.manage"
        if action=="member_history": return "people.team_membership.view_history"
        if action in {"change_role","end_member"}: return "people.team_membership.manage"
        if action in {"activate","suspend","resume","move","assign_owner","assign_lead"}: return "people.team.manage"
        return "people.team.view"
    def has_permission(self,request,view):
        if not request.user.is_authenticated: return False
        if request.user.is_superuser: return True
        actor=getattr(request.user,"employee",None)
        return bool(actor and _team_grants(actor,self.code(request,view)).exists())
    def has_object_permission(self,request,view,obj):
        if request.user.is_superuser: return True
        return _team_permission(getattr(request.user,"employee",None),self.code(request,view),obj)


class TeamViewSet(viewsets.ModelViewSet):
    permission_classes=(TeamAPIPermission,); http_method_names=["get","post","patch","head","options"]
    serializer_class=TeamSerializer
    def get_queryset(self):
        qs=Team.objects.select_related("legal_entity","org_unit","location","parent_team","owner_employee","lead_employee").annotate(active_members=Count("memberships",filter=Q(memberships__valid_to__isnull=True),distinct=True),total_members=Count("memberships",distinct=True))
        permission=TeamAPIPermission().code(self.request,self)
        qs=qs.filter(pk__in=visible_teams(self.request.user,permission).values("pk"))
        p=self.request.query_params
        if p.get("search"): qs=qs.filter(Q(name__icontains=p["search"])|Q(code__icontains=p["search"]))
        for field in ("team_type","status","legal_entity","org_unit","location","owner_employee","lead_employee","parent_team"):
            if p.get(field): qs=qs.filter(**{field:p[field]})
        if p.get("has_active_members") in {"1","true"}: qs=qs.filter(active_members__gt=0)
        if p.get("has_active_members") in {"0","false"}: qs=qs.filter(active_members=0)
        if p.get("as_of"):
            at=parse_datetime(p["as_of"])
            if at: qs=qs.filter(valid_from__lte=at).filter(Q(valid_to__isnull=True)|Q(valid_to__gt=at))
        return qs.order_by("name")
    def perform_create(self,s):
        if not self.request.user.is_superuser:
            candidate=Team(**s.validated_data)
            if not _team_permission(getattr(self.request.user,"employee",None),"people.team.create",candidate):
                raise PermissionDenied()
        s.instance=TeamService.create(actor_user=self.request.user,**s.validated_data)
    def perform_update(self,s): s.instance=TeamService.update(team=self.get_object(),expected_version=int(self.request.data.get("version",0)),actor_user=self.request.user,**s.validated_data)
    def _transition(self,request,target): return Response(self.get_serializer(TeamService.transition(team=self.get_object(),target=target,expected_version=int(request.data.get("version",0)),actor_user=request.user,reason=request.data.get("reason","") )).data)
    @action(detail=True,methods=["post"])
    def activate(self,r,pk=None): return self._transition(r,Team.Status.ACTIVE)
    @action(detail=True,methods=["post"])
    def suspend(self,r,pk=None): return self._transition(r,Team.Status.SUSPENDED)
    @action(detail=True,methods=["post"])
    def resume(self,r,pk=None): return self._transition(r,Team.Status.ACTIVE)
    @action(detail=True,methods=["post"])
    def close(self,r,pk=None): return self._transition(r,Team.Status.CLOSED)
    @action(detail=True,methods=["post"])
    def move(self,r,pk=None):
        parent=self.get_queryset().get(pk=r.data["parent_team"]) if r.data.get("parent_team") else None
        return Response(self.get_serializer(TeamService.move(team=self.get_object(),parent=parent,expected_version=int(r.data.get("version",0)),actor_user=r.user)).data)
    def _leadership(self,r,field):
        employee=Employee.objects.get(pk=r.data["employee"]) if r.data.get("employee") else None
        return Response(self.get_serializer(TeamService.assign_leadership(team=self.get_object(),employee=employee,field=field,expected_version=int(r.data.get("version",0)),actor_user=r.user)).data)
    @action(detail=True,methods=["post"],url_path="assign-owner")
    def assign_owner(self,r,pk=None): return self._leadership(r,"owner_employee")
    @action(detail=True,methods=["post"],url_path="assign-lead")
    def assign_lead(self,r,pk=None): return self._leadership(r,"lead_employee")
    @action(detail=True,methods=["get","post"])
    def members(self,r,pk=None):
        team=self.get_object()
        if r.method=="GET":
            at=parse_datetime(r.query_params.get("as_of","")) if r.query_params.get("as_of") else timezone.now()
            qs=TeamMembershipService.as_of(team,at, r.query_params.get("include_descendants") in {"1","true"})
            if r.query_params.get("employee"): qs=qs.filter(employee_id=r.query_params["employee"])
            if r.query_params.get("role"): qs=qs.filter(role=r.query_params["role"])
            if r.query_params.get("membership_type"): qs=qs.filter(membership_type=r.query_params["membership_type"])
            return Response(TeamMembershipSerializer(qs,many=True).data)
        s=TeamMembershipSerializer(data=r.data);s.is_valid(raise_exception=True)
        membership=TeamMembershipService.add(team=team,actor_user=r.user,**s.validated_data)
        return Response(TeamMembershipSerializer(membership).data,status=201)
    @action(detail=True,methods=["get"],url_path="members/history")
    def member_history(self,r,pk=None):
        qs=self.get_object().memberships.select_related("employee")
        if r.query_params.get("employee"): qs=qs.filter(employee_id=r.query_params["employee"])
        if r.query_params.get("role"): qs=qs.filter(role=r.query_params["role"])
        if r.query_params.get("membership_type"): qs=qs.filter(membership_type=r.query_params["membership_type"])
        return Response(TeamMembershipSerializer(qs,many=True).data)
    @action(detail=True,methods=["post"],url_path=r"members/(?P<membership_id>[^/.]+)/change-role")
    def change_role(self,r,pk=None,membership_id=None):
        membership=self.get_object().memberships.get(pk=membership_id)
        return Response(TeamMembershipSerializer(TeamMembershipService.change_role(membership=membership,role=r.data["role"],actor_user=r.user,reason=r.data.get("reason","") )).data)
    @action(detail=True,methods=["post"],url_path=r"members/(?P<membership_id>[^/.]+)/end")
    def end_member(self,r,pk=None,membership_id=None):
        membership=self.get_object().memberships.get(pk=membership_id)
        return Response(TeamMembershipSerializer(TeamMembershipService.end(membership=membership,actor_user=r.user,reason=r.data.get("reason","") )).data)
    @action(detail=True,methods=["post"])
    def resolve(self,r,pk=None):
        team=self.get_object(); as_of=parse_datetime(r.data.get("as_of","")) if r.data.get("as_of") else timezone.now()
        target=AssignmentTarget(team=team,target_type="team",strategy=r.data.get("strategy","all_active_members"),team_role=r.data.get("role",""),explicit_employee_id=r.data.get("employee"))
        base={"team":{"id":str(team.pk),"code":team.code,"name":team.name},"strategy":target.strategy,"role":target.team_role or None,"as_of":as_of,"employees":[],"excluded":[],"warnings":[]}
        try: employees,detail=AssignmentResolver.resolve_team(target,as_of)
        except AssignmentTargetUnresolved as exc:
            return Response({**base,"assignable":False,"warnings":[str(exc)]})
        return Response({**base,"employees":[{"id":str(e.pk),"name":e.display_name} for e in employees],"excluded":detail["excluded"],"assignable":True})
    @action(detail=False,methods=["get"])
    def tree(self,r):
        queryset=self.get_queryset()
        if queryset.count()>1000: return Response({"detail":"Слишком много команд для tree preview."},status=400)
        rows=list(queryset.values("id","parent_team_id","code","name","team_type","status","active_members","total_members")); children={}
        for row in rows: children.setdefault(row["parent_team_id"],[]).append(row)
        for values in children.values(): values.sort(key=lambda item:(item["name"],str(item["id"])))
        def node(row): return {**row,"children":[node(x) for x in children.get(row["id"],[])]}
        return Response([node(x) for x in children.get(None,[])])
