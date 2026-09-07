from django.core.exceptions import ValidationError as DjangoValidationError
from django.db.models import Q
from django.utils import timezone
from rest_framework import serializers, viewsets
from rest_framework.decorators import action
from rest_framework.exceptions import PermissionDenied
from rest_framework.permissions import AllowAny
from rest_framework.response import Response
from rest_framework.views import APIView

from access_control.models import EmployeeRole, Scope
from access_control.services import PermissionService
from .models import Employee, EmployeeInvitation, FirstLoginProgress, OnboardingInstance, OnboardingStepInstance, OnboardingTemplate
from .onboarding import FirstLoginService, InvitationService
from .onboarding_api import PublicScopedThrottle, visible_employees
from .onboarding_lifecycle import OnboardingService, OnboardingTemplateService, TemplateResolver
from .services import AccountAccessService


def actor(request):
    return getattr(request.user, "employee", None)


def require(request, permission, obj=None):
    if request.user.is_superuser:
        return
    if not PermissionService.has_permission(employee=actor(request), permission=permission, obj=obj):
        raise PermissionDenied()


def validation_response(exc):
    detail = exc.message_dict if hasattr(exc, "message_dict") else {"detail": exc.messages}
    return serializers.ValidationError(detail)


def visible_templates(user, permission):
    qs = OnboardingTemplate.objects.select_related("published_version")
    if user.is_superuser: return qs
    employee = getattr(user, "employee", None)
    if not employee: return qs.none()
    grants = EmployeeRole.objects.filter(employee=employee, is_active=True, role__is_active=True, role__permission_grants__permission__code=permission).values("role__permission_grants__scope", "org_unit_id", "legal_entity_id", "location_id")
    predicate = Q(pk__in=[])
    for grant in grants:
        scope = grant["role__permission_grants__scope"]
        if scope == Scope.GLOBAL: return qs
        if scope == Scope.OWN: predicate |= Q(scope="global")
        elif scope == Scope.ORG_UNIT:
            value=grant["org_unit_id"] or employee.org_unit_id; predicate |= Q(scope="global") | Q(org_unit_id=value) | Q(position__org_unit_id=value)
        elif scope == Scope.LEGAL_ENTITY:
            value=grant["legal_entity_id"] or employee.legal_entity_id; predicate |= Q(scope="global") | Q(legal_entity_id=value) | Q(position__legal_entity_id=value)
        elif scope == Scope.TEAM:
            predicate |= Q(scope="global") | Q(location_id=grant["location_id"] or employee.primary_location_id) | Q(team__memberships__employee=employee, team__memberships__valid_to__isnull=True)
    return qs.filter(predicate).distinct()


class InvitationSerializer(serializers.ModelSerializer):
    employee_name = serializers.CharField(source="employee.display_name", read_only=True)
    active = serializers.SerializerMethodField()

    class Meta:
        model = EmployeeInvitation
        fields = ("id", "employee", "employee_name", "delivery_address", "status", "created_at", "sent_at", "expires_at", "used_at", "revoked_at", "revoke_reason", "version", "active")
        read_only_fields = fields

    def get_active(self, obj):
        return not obj.used_at and not obj.revoked_at and obj.expires_at > timezone.now()


class InvitationViewSet(viewsets.GenericViewSet):
    serializer_class = InvitationSerializer

    def get_queryset(self):
        qs = EmployeeInvitation.objects.select_related("employee", "created_by").filter(employee__in=visible_employees(self.request.user, "people.invitation.view"))
        p = self.request.query_params
        for param, field in (("status", "status"), ("employee", "employee_id"), ("legal_entity", "employee__legal_entity_id"), ("org_unit", "employee__org_unit_id"), ("location", "employee__primary_location_id"), ("created_by", "created_by_id")):
            if p.get(param): qs = qs.filter(**{field: p[param]})
        if p.get("expires_before"): qs = qs.filter(expires_at__lte=p["expires_before"])
        if p.get("expires_after"): qs = qs.filter(expires_at__gte=p["expires_after"])
        if p.get("active") == "true": qs = qs.filter(used_at__isnull=True, revoked_at__isnull=True, expires_at__gt=timezone.now())
        return qs.order_by("-created_at")

    def list(self, request):
        require(request, "people.invitation.view")
        page = self.paginate_queryset(self.get_queryset())
        return self.get_paginated_response(self.get_serializer(page, many=True).data)

    def retrieve(self, request, pk=None):
        require(request, "people.invitation.view")
        return Response(self.get_serializer(self.get_object()).data)

    def create(self, request):
        require(request, "people.invitation.create")
        employee = visible_employees(request.user, "people.invitation.create").get(pk=request.data.get("employee"))
        try:
            invitation, raw = InvitationService.issue(employee=employee, actor_user=request.user, delivery_address=request.data.get("email") or employee.work_email)
        except DjangoValidationError as exc:
            raise validation_response(exc)
        return Response({**self.get_serializer(invitation).data, "activation_token": raw}, status=201)

    @action(detail=True, methods=["post"])
    def resend(self, request, pk=None):
        require(request, "people.invitation.resend")
        previous = self.get_object()
        try:
            invitation, raw = InvitationService.issue(employee=previous.employee, actor_user=request.user, delivery_address=previous.delivery_address)
        except DjangoValidationError as exc: raise validation_response(exc)
        return Response({**self.get_serializer(invitation).data, "activation_token": raw})

    @action(detail=True, methods=["post"])
    def revoke(self, request, pk=None):
        require(request, "people.invitation.revoke")
        try: item = InvitationService.revoke(invitation=self.get_object(), actor_user=request.user, reason=request.data.get("reason", "revoked"))
        except DjangoValidationError as exc: raise validation_response(exc)
        return Response(self.get_serializer(item).data)


class PublicInvitationValidateView(APIView):
    permission_classes = (AllowAny,); authentication_classes = (); throttle_classes = (PublicScopedThrottle,); throttle_scope = "activation"
    def post(self, request):
        invitation = InvitationService.context(request.data.get("token", ""))
        return Response({"valid": bool(invitation), "state": "valid" if invitation else "unavailable"})


class PublicInvitationAcceptView(APIView):
    permission_classes = (AllowAny,); authentication_classes = (); throttle_classes = (PublicScopedThrottle,); throttle_scope = "activation"
    def post(self, request):
        try:
            InvitationService.activate(token=request.data.get("token", ""), password=request.data.get("password", ""), password_confirmation=request.data.get("password_confirmation", ""))
        except DjangoValidationError:
            raise serializers.ValidationError({"detail": "Invitation is unavailable or registration data is invalid."})
        return Response({"detail": "Account activated."})


class FirstLoginView(APIView):
    def get(self, request):
        employee = actor(request); require(request, "people.onboarding.view_self", employee)
        progress, _ = FirstLoginProgress.objects.get_or_create(employee=employee)
        return Response({"profile_completed": progress.profile_completed, "timezone_completed": progress.timezone_completed, "visibility_completed": progress.visibility_completed, "completed_at": progress.completed_at, "version": progress.version})
    def patch(self, request):
        employee = actor(request); require(request, "people.onboarding.view_self", employee)
        try: progress = FirstLoginService.update(employee=employee, version=request.data.get("version"), **{key: request.data.get(key) for key in ("profile_completed", "timezone_completed", "visibility_completed") if key in request.data})
        except DjangoValidationError as exc: raise validation_response(exc)
        return self.get(request)


class TemplateSerializer(serializers.ModelSerializer):
    published_version_number = serializers.IntegerField(source="published_version.number", read_only=True)
    class Meta:
        model = OnboardingTemplate
        fields = ("id", "name", "description", "status", "scope", "legal_entity", "org_unit", "location", "position", "team", "published_version", "published_version_number", "version", "created_at", "updated_at")
        read_only_fields = ("id", "status", "published_version", "published_version_number", "version", "created_at", "updated_at")


class OnboardingTemplateViewSet(viewsets.ModelViewSet):
    serializer_class = TemplateSerializer
    http_method_names = ["get", "post", "patch", "head", "options"]
    def get_queryset(self):
        method_permission = "people.onboarding_template.view" if self.request.method in {"GET","HEAD","OPTIONS"} else "people.onboarding_template.update"
        qs = visible_templates(self.request.user, method_permission).order_by("-updated_at")
        p = self.request.query_params
        for key in ("status", "scope", "legal_entity", "org_unit", "location", "position", "team"):
            if p.get(key): qs = qs.filter(**{key if key in {"status", "scope"} else key + "_id": p[key]})
        return qs
    def list(self, request, *args, **kwargs): require(request, "people.onboarding_template.view"); return super().list(request, *args, **kwargs)
    def retrieve(self, request, *args, **kwargs): require(request, "people.onboarding_template.view"); return super().retrieve(request, *args, **kwargs)
    def perform_create(self, serializer):
        require(self.request, "people.onboarding_template.create")
        serializer.instance = OnboardingTemplateService.create(actor_user=self.request.user, **serializer.validated_data)
    def perform_update(self, serializer):
        require(self.request, "people.onboarding_template.update")
        obj = self.get_object()
        if obj.status != "draft" or self.request.data.get("version") != obj.version: raise serializers.ValidationError("Only current draft templates may be edited.")
        serializer.save(version=obj.version + 1)
    @action(detail=True, methods=["post"])
    def publish(self, request, pk=None):
        require(request, "people.onboarding_template.publish")
        try: version = OnboardingTemplateService.publish(template=self.get_object(), actor_user=request.user, expected_version=request.data.get("version"), steps=[dict(x) for x in request.data.get("steps", [])])
        except DjangoValidationError as exc: raise validation_response(exc)
        return Response({"id": version.pk, "number": version.number})
    @action(detail=True, methods=["post"])
    def archive(self, request, pk=None):
        require(request, "people.onboarding_template.archive")
        try: obj = OnboardingTemplateService.archive(template=self.get_object(), actor_user=request.user, expected_version=request.data.get("version"))
        except DjangoValidationError as exc: raise validation_response(exc)
        return Response(self.get_serializer(obj).data)
    @action(detail=True, methods=["post"], url_path="preview-resolution")
    def preview_resolution(self, request, pk=None):
        require(request, "people.onboarding_template.view")
        employee = visible_employees(request.user, "people.onboarding.view").get(pk=request.data.get("employee"))
        resolved = TemplateResolver.resolve(employee, self.get_object() if request.data.get("explicit") else None)
        return Response({"template_id": resolved.pk, "scope": resolved.scope})


class StepSerializer(serializers.ModelSerializer):
    class Meta:
        model = OnboardingStepInstance
        fields = ("id", "title_snapshot", "description_snapshot", "required", "status", "responsible_employee", "resolution_detail", "due_at", "started_at", "completed_at", "skipped_at", "skip_reason", "task", "version")


class OnboardingSerializer(serializers.ModelSerializer):
    employee_name = serializers.CharField(source="employee.display_name", read_only=True)
    steps = StepSerializer(many=True, read_only=True)
    class Meta:
        model = OnboardingInstance
        fields = ("id", "employee", "employee_name", "template_version", "status", "progress_percent", "started_at", "completed_at", "cancelled_at", "cancellation_reason", "version", "created_at", "steps")
        read_only_fields = fields


class OnboardingViewSet(viewsets.GenericViewSet):
    serializer_class = OnboardingSerializer
    def get_queryset(self):
        qs = OnboardingInstance.objects.select_related("employee", "template_version__template").prefetch_related("steps").filter(employee__in=visible_employees(self.request.user, "people.onboarding.view"))
        p = self.request.query_params
        for key, field in (("status", "status"), ("employee", "employee_id"), ("template", "template_version__template_id"), ("legal_entity", "employee__legal_entity_id"), ("org_unit", "employee__org_unit_id"), ("location", "employee__primary_location_id"), ("position", "employee__position_ref_id"), ("manager", "employee__manager_id")):
            if p.get(key): qs = qs.filter(**{field: p[key]})
        if p.get("overdue") == "true": qs = qs.filter(steps__due_at__lt=timezone.now()).exclude(steps__status__in=["completed", "skipped", "cancelled"]).distinct()
        return qs.order_by("-created_at")
    def list(self, request): require(request, "people.onboarding.view"); page=self.paginate_queryset(self.get_queryset()); return self.get_paginated_response(self.get_serializer(page,many=True).data)
    def retrieve(self, request, pk=None): require(request, "people.onboarding.view"); return Response(self.get_serializer(self.get_object()).data)
    def create(self, request):
        require(request, "people.onboarding.assign")
        employee = visible_employees(request.user, "people.onboarding.assign").get(pk=request.data.get("employee"))
        template = OnboardingTemplate.objects.get(pk=request.data["template"]) if request.data.get("template") else None
        try: obj = OnboardingService.assign(employee=employee, actor_user=request.user, template=template)
        except DjangoValidationError as exc: raise validation_response(exc)
        return Response(self.get_serializer(obj).data, status=201)
    def _transition(self, request, name):
        require(request, "people.onboarding.manage")
        try: obj=OnboardingService.transition(instance=self.get_object(), actor_user=request.user, expected_version=request.data.get("version"), action=name, reason=request.data.get("reason", ""))
        except DjangoValidationError as exc: raise validation_response(exc)
        return Response(self.get_serializer(obj).data)
    @action(detail=True,methods=["post"])
    def start(self,request,pk=None):return self._transition(request,"start")
    @action(detail=True,methods=["post"])
    def pause(self,request,pk=None):return self._transition(request,"pause")
    @action(detail=True,methods=["post"])
    def resume(self,request,pk=None):return self._transition(request,"resume")
    @action(detail=True,methods=["post"])
    def cancel(self,request,pk=None):return self._transition(request,"cancel")
    @action(detail=True,methods=["post"])
    def restart(self,request,pk=None):
        require(request,"people.onboarding.manage")
        previous=self.get_object()
        if previous.status not in {"cancelled","failed","completed"}:raise serializers.ValidationError("Only final onboarding can be restarted.")
        try:obj=OnboardingService.assign(employee=previous.employee,actor_user=request.user,template=previous.template_version.template)
        except DjangoValidationError as exc:raise validation_response(exc)
        return Response(self.get_serializer(obj).data,status=201)
    @action(detail=True,methods=["post"],url_path=r"steps/(?P<step_id>[^/.]+)/skip")
    def skip_step(self,request,pk=None,step_id=None):
        require(request,"people.onboarding.step_skip")
        step=self.get_object().steps.get(pk=step_id)
        try:item=OnboardingService.step_action(step=step,actor_employee=actor(request) or step.onboarding.employee,actor_user=request.user,expected_version=request.data.get("version"),action="skip",reason=request.data.get("reason",""),allow_skip=True)
        except DjangoValidationError as exc:raise validation_response(exc)
        return Response(StepSerializer(item).data)
    @action(detail=True,methods=["post"],url_path=r"steps/(?P<step_id>[^/.]+)/resolve")
    def resolve_step(self,request,pk=None,step_id=None):
        from .onboarding_lifecycle import ResponsibleResolver
        require(request,"people.onboarding.manage")
        step=self.get_object().steps.select_related("template_step").get(pk=step_id)
        if request.data.get("version")!=step.version:raise serializers.ValidationError("Onboarding step version conflict.")
        try:responsible,detail=ResponsibleResolver.resolve(step.template_step,step.onboarding.employee)
        except Exception as exc:raise serializers.ValidationError(str(exc))
        step.responsible_employee=responsible;step.resolution_detail=detail;step.status="pending";step.version+=1;step.save()
        return Response(StepSerializer(step).data)
    @action(detail=True,methods=["post"],url_path=r"steps/(?P<step_id>[^/.]+)/create-task")
    def create_task(self,request,pk=None,step_id=None):
        require(request,"people.onboarding.manage")
        step=self.get_object().steps.get(pk=step_id)
        try:task=OnboardingService.create_task(step=step,actor_employee=actor(request) or step.onboarding.employee,actor_user=request.user)
        except DjangoValidationError as exc:raise validation_response(exc)
        return Response({"task_id":task.pk,"number":task.number})


class SelfOnboardingViewSet(viewsets.GenericViewSet):
    serializer_class = OnboardingSerializer
    def get_queryset(self):
        employee=actor(self.request); require(self.request,"people.onboarding.view_self",employee)
        return OnboardingInstance.objects.filter(employee=employee).select_related("template_version").prefetch_related("steps")
    def list(self,request):return Response(self.get_serializer(self.get_queryset(),many=True).data)
    def retrieve(self,request,pk=None):return Response(self.get_serializer(self.get_object()).data)
    @action(detail=True,methods=["post"])
    def start(self,request,pk=None):
        require(request,"people.onboarding.view_self",actor(request))
        try:item=OnboardingService.transition(instance=self.get_object(),actor_user=request.user,expected_version=request.data.get("version"),action="start")
        except DjangoValidationError as exc:raise validation_response(exc)
        return Response(self.get_serializer(item).data)
    @action(detail=True,methods=["post"],url_path=r"steps/(?P<step_id>[^/.]+)/start")
    def start_step(self,request,pk=None,step_id=None):return self._step(request,step_id,"start")
    @action(detail=True,methods=["post"],url_path=r"steps/(?P<step_id>[^/.]+)/complete")
    def complete_step(self,request,pk=None,step_id=None):return self._step(request,step_id,"complete")
    def _step(self,request,step_id,action_name):
        require(request,"people.onboarding.step_complete_self",actor(request))
        step=self.get_object().steps.get(pk=step_id)
        try:item=OnboardingService.step_action(step=step,actor_employee=actor(request),actor_user=request.user,expected_version=request.data.get("version"),action=action_name)
        except DjangoValidationError as exc:raise validation_response(exc)
        return Response(StepSerializer(item).data)


class AccountAccessView(APIView):
    action_name = "suspended"; enabled = False; permission = "people.account_access.suspend"
    def post(self, request, employee_id):
        employee=visible_employees(request.user,self.permission).get(pk=employee_id); require(request,self.permission,employee)
        try:item=AccountAccessService.set_access(employee=employee,actor_user=request.user,enabled=self.enabled,action=self.action_name)
        except DjangoValidationError as exc:raise validation_response(exc)
        return Response({"employee_id":item.pk,"user_active":item.user.is_active})


class AccountRestoreView(AccountAccessView): action_name="restored"; enabled=True; permission="people.account_access.restore"
class AccountBlockView(AccountAccessView): action_name="blocked"; enabled=False; permission="people.account_access.block"
class AccountReactivateView(AccountAccessView): action_name="reactivated"; enabled=True; permission="people.account_access.reactivate"
