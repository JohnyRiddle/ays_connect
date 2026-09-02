from django.core.exceptions import ValidationError as DjangoValidationError
from django.http import FileResponse
from rest_framework import serializers, status, viewsets
from rest_framework.decorators import action
from rest_framework.exceptions import PermissionDenied
from rest_framework.response import Response
from rest_framework.views import APIView

from access_control.services import PermissionService
from .models import Employee, EmployeeDataChangeRequest, EmployeeProfile
from .onboarding_api import visible_employees
from .profile_services import ChangeRequestService, ProfileService, can_see, completeness, ensure_profile


def employee_for(request):
    employee=getattr(request.user,"employee",None)
    if not employee or not employee.is_active: raise PermissionDenied("Active employee profile is required.")
    return employee


def error_call(callback):
    try:return callback()
    except DjangoValidationError as exc: raise serializers.ValidationError(exc.message_dict if hasattr(exc,"message_dict") else exc.messages)


class ProfileSerializer(serializers.ModelSerializer):
    class Meta:
        model=EmployeeProfile
        fields=("preferred_name","bio","additional_email","additional_phone","timezone","preferred_language","bio_visibility","additional_email_visibility","additional_phone_visibility","version")
        read_only_fields=("version",)


class ChangeRequestSerializer(serializers.ModelSerializer):
    requested_value=serializers.SerializerMethodField()
    current_value_snapshot=serializers.SerializerMethodField()
    class Meta:
        model=EmployeeDataChangeRequest
        fields=("id","employee","field_type","requested_value","current_value_snapshot","reason","status","submitted_at","reviewed_at","reviewed_by","review_comment","applied_at","version")
        read_only_fields=fields
    def _safe(self,obj,value):
        own=self.context["request"].user.pk==obj.employee.user_id
        return value if own or self.context["request"].user.is_superuser else {"masked":True}
    def get_requested_value(self,obj):return self._safe(obj,obj.requested_value)
    def get_current_value_snapshot(self,obj):return self._safe(obj,obj.current_value_snapshot)


def profile_payload(request, employee, directory=False):
    profile=ensure_profile(employee,request.user)
    avatar_url=(f"/api/internal/v1/people/directory/{employee.pk}/avatar/" if directory else "/api/internal/v1/people/me/avatar/") if employee.avatar else None
    data={"id":str(employee.pk),"employee_number":employee.employee_number,"display_name":profile.preferred_name or employee.display_name,"avatar_url":avatar_url,"position":employee.position_ref.name if employee.position_ref else employee.position,"org_unit":employee.org_unit.name if employee.org_unit else None,"legal_entity":employee.legal_entity.name if employee.legal_entity else None,"location":employee.primary_location.name if employee.primary_location else None,"manager":None if not employee.manager else {"id":str(employee.manager_id),"name":employee.manager.display_name},"work_email":employee.work_email,"work_phone":employee.work_phone,"timezone":profile.timezone,"preferred_language":profile.preferred_language,"version":profile.version}
    for field in ("bio","additional_email","additional_phone"):
        data[field]=getattr(profile,field) if not directory or can_see(profile,field,request.user,employee) else None
    if not directory:
        data.update({"visibility":{key:getattr(profile,key) for key in ("bio_visibility","additional_email_visibility","additional_phone_visibility")},"completeness":completeness(employee,profile),"available_actions":["update_profile","change_visibility","upload_avatar","request_data_change"]})
    return data


class MeView(APIView):
    def get(self,request):return Response(profile_payload(request,employee_for(request)))
    def patch(self,request):
        employee=employee_for(request); expected=request.data.get("version")
        if expected is None: raise serializers.ValidationError({"version":"Required."})
        profile=error_call(lambda:ProfileService.update(employee,request.user,int(expected),{k:v for k,v in request.data.items() if k!="version"}))
        return Response(profile_payload(request,employee))


class CompletenessView(APIView):
    def get(self,request):return Response(completeness(employee_for(request)))


class OrganizationView(APIView):
    def get(self,request):
        e=employee_for(request);return Response({"legal_entity":None if not e.legal_entity else {"id":e.legal_entity_id,"name":e.legal_entity.name},"org_unit":None if not e.org_unit else {"id":e.org_unit_id,"name":e.org_unit.name},"manager":None if not e.manager else {"id":e.manager_id,"name":e.manager.display_name}})


class TeamsView(APIView):
    def get(self,request):
        e=employee_for(request);return Response([{"id":x.team_id,"code":x.team.code,"name":x.team.name,"role":x.role} for x in e.team_memberships.filter(valid_to__isnull=True).select_related("team")])


class VisibilityView(APIView):
    def get(self,request):return Response(ProfileSerializer(ensure_profile(employee_for(request),request.user)).data)
    def patch(self,request):
        e=employee_for(request);expected=request.data.get("version")
        if expected is None:raise serializers.ValidationError({"version":"Required."})
        profile=error_call(lambda:ProfileService.visibility(e,request.user,int(expected),{k:v for k,v in request.data.items() if k!="version"}))
        return Response(ProfileSerializer(profile).data)


class AvatarView(APIView):
    def get(self,request):
        employee=employee_for(request)
        if not employee.avatar:return Response(status=404)
        return FileResponse(employee.avatar.open("rb"),content_type="application/octet-stream",as_attachment=False)
    def post(self,request):
        e=employee_for(request);error_call(lambda:ProfileService.avatar(e,request.user,request.FILES.get("avatar")));return Response(profile_payload(request,e),status=201)
    def delete(self,request):ProfileService.remove_avatar(employee_for(request),request.user);return Response(status=204)


class SelfChangeRequestViewSet(viewsets.ReadOnlyModelViewSet):
    serializer_class=ChangeRequestSerializer
    def get_queryset(self):return EmployeeDataChangeRequest.objects.filter(employee=employee_for(self.request))
    def create(self,request):
        e=employee_for(request);item=error_call(lambda:ChangeRequestService.submit(e,request.user,request.data.get("field_type"),request.data.get("requested_value") or {},request.data.get("reason","").strip()))
        return Response(self.get_serializer(item).data,status=201)
    @action(detail=True,methods=["post"])
    def cancel(self,request,pk=None):return Response(self.get_serializer(error_call(lambda:ChangeRequestService.cancel(self.get_object(),request.user,int(request.data.get("version",0))))).data)


class ChangeRequestReviewViewSet(viewsets.ReadOnlyModelViewSet):
    serializer_class=ChangeRequestSerializer;queryset=EmployeeDataChangeRequest.objects.select_related("employee__user","reviewed_by")
    def initial(self,request,*args,**kwargs):
        super().initial(request,*args,**kwargs)
        actor=getattr(request.user,"employee",None)
        code="people.change_request.apply" if getattr(self,"action",None)=="apply" else "people.change_request.review"
        if not request.user.is_superuser and not PermissionService.has_permission(employee=actor,permission=code):raise PermissionDenied()
    @action(detail=True,methods=["post"])
    def approve(self,request,pk=None):return Response(self.get_serializer(error_call(lambda:ChangeRequestService.transition(self.get_object(),request.user,int(request.data.get("version",0)),"approved",request.data.get("comment","")))).data)
    @action(detail=True,methods=["post"])
    def reject(self,request,pk=None):return Response(self.get_serializer(error_call(lambda:ChangeRequestService.transition(self.get_object(),request.user,int(request.data.get("version",0)),"rejected",request.data.get("comment","")))).data)
    @action(detail=True,methods=["post"])
    def apply(self,request,pk=None):return Response(self.get_serializer(error_call(lambda:ChangeRequestService.apply(self.get_object(),request.user,int(request.data.get("version",0))))).data)


class DirectoryViewSet(viewsets.ReadOnlyModelViewSet):
    def get_queryset(self):
        qs=visible_employees(self.request.user,"people.directory.view").filter(is_active=True).select_related("manager","manager__user")
        p=self.request.query_params
        if p.get("team"):qs=qs.filter(team_memberships__team_id=p["team"],team_memberships__valid_to__isnull=True)
        return qs.order_by("last_name","first_name","pk")
    def list(self,request):return Response([profile_payload(request,e,True) for e in self.filter_queryset(self.get_queryset())])
    def retrieve(self,request,pk=None):return Response(profile_payload(request,self.get_object(),True))
    @action(detail=True,methods=["get"])
    def avatar(self,request,pk=None):
        employee=self.get_object()
        if not employee.avatar:return Response(status=404)
        return FileResponse(employee.avatar.open("rb"),content_type="application/octet-stream",as_attachment=False)
