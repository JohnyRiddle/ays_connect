from django.db import transaction
from django.conf import settings
from access_control.models import Role, EmployeeRole
from django.shortcuts import get_object_or_404
from django.utils import timezone
from rest_framework import serializers, viewsets
from rest_framework.decorators import action
from rest_framework.permissions import AllowAny
from rest_framework.response import Response
from rest_framework.views import APIView

from .models import Employee, EmployeeInvitation, RegistrationRequest
from .onboarding import InvitationService, token_hash
from .registration_throttle import RegistrationThrottle
from .registration import (ObjectInvitationService, ObjectRegistrationService,
    ResponsibilityService, locations_for, public_locations, require)
from organizations.models import Location


class StrictSerializer(serializers.Serializer):
    def to_internal_value(self, data):
        if set(data) - set(self.fields):
            raise serializers.ValidationError({"non_field_errors": ["Недопустимые поля."]})
        return super().to_internal_value(data)


class SubmitSerializer(StrictSerializer):
    first_name = serializers.CharField(max_length=150)
    last_name = serializers.CharField(max_length=150)
    middle_name = serializers.CharField(max_length=150, required=False, allow_blank=True, default="")
    email = serializers.EmailField(max_length=254)
    location = serializers.UUIDField(required=False)
    invite_token = serializers.CharField(required=False, max_length=512, write_only=True)
    password = serializers.CharField(max_length=128, trim_whitespace=False, write_only=True)
    password_confirmation = serializers.CharField(max_length=128, trim_whitespace=False, write_only=True)


class PublicView(APIView):
    permission_classes = (AllowAny,)
    authentication_classes = ()
    throttle_classes = (RegistrationThrottle,)
    throttle_scope = "registration"

    def finalize_response(self, request, response, *args, **kwargs):
        response = super().finalize_response(request, response, *args, **kwargs)
        response["Cache-Control"] = "no-store"
        response["Referrer-Policy"] = "no-referrer"
        return response


class PublicLocations(PublicView):
    throttle_scope = "registration_locations"
    def get(self, request):
        return Response(list(public_locations().values("id", "name")))


class Submit(PublicView):
    def post(self, request):
        serializer = SubmitSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        data = serializer.validated_data
        token = data.pop("invite_token", None)
        invitation = ObjectInvitationService.context(token) if token else None
        location_id = data.pop("location", None)
        if invitation:
            if location_id and location_id != invitation.employment_location_id:
                raise serializers.ValidationError("Объект приглашения нельзя изменить.")
            location = invitation.employment_location
        else:
            location = get_object_or_404(public_locations(), pk=location_id)
        item, key = ObjectRegistrationService.submit(**data, location=location, invitation=invitation)
        return Response({"detail": "Заявка обработана. Для существующего аккаунта используйте вход или восстановление.",
                         "status": item.status if item else "pending", "status_token": key}, status=202)


class Confirm(PublicView):
    def post(self, request):
        return Response({"detail": "Подтверждение e-mail отключено."}, status=410)


class OwnStatus(PublicView):
    throttle_scope = "registration_status"
    def post(self, request):
        # Token in body, never URL. No work JWT or User.session is created.
        item = get_object_or_404(RegistrationRequest, status_token_hash=token_hash(request.data.get("token", "")), employment_location__isnull=False)
        if item.expires_at <= timezone.now() and item.status in {"email_pending", "pending"}:
            return Response({"status": "expired"})
        return Response({"status": item.status, "rejection_reason": item.rejection_code})


class Resend(PublicView):
    def post(self, request):
        return Response({"detail": "Письма регистрации не отправляются."}, status=410)


class Cancel(OwnStatus):
    @transaction.atomic
    def post(self, request):
        item = get_object_or_404(RegistrationRequest.objects.select_for_update(), status_token_hash=token_hash(request.data.get("token", "")), status__in=["email_pending", "pending"])
        item.status = "cancelled"
        item.password_hash = ""
        item.save(update_fields=["status", "password_hash"])
        from .onboarding import _event
        _event("registration.cancelled", item, new={"status": item.status})
        return Response({"status": item.status})


class InviteContext(PublicView):
    throttle_scope = "activation"
    def post(self, request):
        item = ObjectInvitationService.context(request.data.get("token", ""))
        return Response({"location": {"id": str(item.employment_location_id), "name": item.employment_location.name},
            "email_required": bool(item.delivery_address), "expires_at": item.expires_at})


class RequestSerializer(serializers.ModelSerializer):
    location_name = serializers.CharField(source="employment_location.name", read_only=True)
    class Meta:
        model = RegistrationRequest
        fields = ("id", "first_name", "last_name", "middle_name", "email", "employment_location", "location_name", "status", "created_at", "reviewed_at", "reviewed_by", "rejection_code")


class RequestFilter(serializers.Serializer):
    status = serializers.ChoiceField(choices=RegistrationRequest.Status.choices, required=False)
    employment_location = serializers.UUIDField(required=False)


class Requests(viewsets.ReadOnlyModelViewSet):
    serializer_class = RequestSerializer
    def get_queryset(self):
        qs = RegistrationRequest.objects.filter(employment_location__in=locations_for(self.request.user, "people.registration.manage")).select_related("employment_location").order_by("-created_at")
        filters = RequestFilter(data={key: self.request.query_params[key] for key in ("status", "employment_location") if self.request.query_params.get(key)})
        filters.is_valid(raise_exception=True)
        qs = qs.filter(**filters.validated_data)
        return qs

    @action(detail=True, methods=["post"])
    def approve(self, request, pk=None):
        data = Decision(data=request.data)
        data.is_valid(raise_exception=True)
        employee = get_object_or_404(Employee, pk=data.validated_data["employee"]) if data.validated_data.get("employee") else None
        item = ObjectRegistrationService.approve(registration=self.get_object(), actor=request.user,
            plan=data.validated_data["plan"], employee=employee)
        return Response(self.get_serializer(item).data)

    @action(detail=True, methods=["post"])
    def reject(self, request, pk=None):
        item = ObjectRegistrationService.reject(registration=self.get_object(), actor=request.user, reason=request.data.get("reason", ""))
        return Response(self.get_serializer(item).data)


class Plan(StrictSerializer):
    role = serializers.UUIDField()
    access_locations = serializers.ListField(child=serializers.UUIDField(), max_length=100)
    responsibility_mode = serializers.ChoiceField(choices=["selected", "all"], default="selected")
    responsibility_locations = serializers.ListField(child=serializers.UUIDField(), max_length=100, default=list)
    def validate(self, attrs):
        return {key: [str(v) for v in value] if isinstance(value, list) else str(value) for key, value in attrs.items()}


class Decision(StrictSerializer):
    plan = Plan()
    employee = serializers.UUIDField(required=False)


class Issue(Decision):
    plan = Plan(required=False)
    location = serializers.UUIDField()
    email = serializers.EmailField(required=False, allow_blank=True, default="")
    days = serializers.IntegerField(min_value=1, max_value=7, default=7)


class InvitationSerializer(serializers.ModelSerializer):
    location_name = serializers.CharField(source="employment_location.name", read_only=True)
    effective_status = serializers.SerializerMethodField()
    def get_effective_status(self, obj):
        return "expired" if not obj.used_at and not obj.revoked_at and obj.expires_at <= timezone.now() else obj.status
    class Meta:
        model = EmployeeInvitation
        fields = ("id", "employee", "employment_location", "location_name", "delivery_address", "access_plan", "effective_status", "expires_at", "created_by", "created_at")


class Invitations(viewsets.ReadOnlyModelViewSet):
    serializer_class = InvitationSerializer
    def get_queryset(self):
        return EmployeeInvitation.objects.filter(employment_location__in=locations_for(self.request.user, "people.invitation.manage")).select_related("employment_location").order_by("-created_at")

    @action(detail=False, methods=["get"], url_path="options")
    def choices(self, request):
        from .registration import live_grants, eligible_role
        locations = locations_for(request.user, "people.invitation.manage").filter(pk__in=locations_for(request.user, "people.invitation.delegate").values("pk"))
        roles = Role.objects.filter(is_active=True)
        if not request.user.is_superuser:
            now = timezone.now()
            roles = roles.filter(employee_assignments__employee=getattr(request.user, "employee", None),
                employee_assignments__is_active=True, employee_assignments__location__in=locations).filter(
                Q(employee_assignments__active_from__isnull=True) | Q(employee_assignments__active_from__lte=now),
                Q(employee_assignments__active_until__isnull=True) | Q(employee_assignments__active_until__gt=now))
        eligible = [role.pk for role in roles.distinct() if eligible_role(role)]
        from .onboarding_api import visible_employees
        employees = visible_employees(request.user, "people.employee.manage").filter(is_active=True).filter(Q(user__isnull=True) | Q(user__is_active=False))[:100]
        return Response({"locations": list(locations.filter(pk__in=public_locations().values("pk")).values("id", "name")),
            "employees": [{"id": str(employee.pk), "name": employee.display_name} for employee in employees],
            "roles": list(roles.filter(pk__in=eligible).values("id", "name", "code")),
            "allow_all_responsibility": request.user.is_superuser or live_grants(request.user, "people.responsibility.all").filter(role__permission_grants__scope="global", role__permission_grants__permission__code="people.responsibility.all").exists()})

    def create(self, request):
        data = Issue(data=request.data)
        data.is_valid(raise_exception=True)
        args = data.validated_data
        location = get_object_or_404(locations_for(request.user, "people.invitation.manage"), pk=args.pop("location"))
        if args.get("employee"):
            from .onboarding_api import visible_employees
            args["employee"] = get_object_or_404(visible_employees(request.user, "people.employee.manage"), pk=args["employee"])
        item, token = ObjectInvitationService.issue(actor=request.user, location=location, **args)
        return Response({**self.get_serializer(item).data, "invitation_url": f"{settings.FRONTEND_BASE_URL}/register#invite={token}"}, status=201, headers={"Cache-Control": "no-store"})

    @action(detail=True, methods=["post"])
    def revoke(self, request, pk=None):
        item = self.get_object()
        require(request.user, "people.invitation.manage", item.employment_location)
        InvitationService.revoke(invitation=item, actor_user=request.user)
        return Response(status=204)

    @action(detail=True, methods=["post"])
    @transaction.atomic
    def reissue(self, request, pk=None):
        item = self.get_object()
        if item.employee_id:
            Employee.objects.select_for_update().get(pk=item.employee_id)
        require(request.user, "people.invitation.manage", item.employment_location)
        if item.used_at:
            raise serializers.ValidationError("Приглашение уже принято.")
        if not item.revoked_at:
            InvitationService.revoke(invitation=item, actor_user=request.user, reason="superseded")
        for pending in RegistrationRequest.objects.select_for_update().filter(invitation=item, status__in=["email_pending", "pending"]):
            pending.status = "cancelled"
            pending.password_hash = ""
            pending.save(update_fields=["status", "password_hash"])
            from .onboarding import _event
            _event("registration.cancelled", pending, request.user, new={"reason": "invitation_reissued"})
        created, token = ObjectInvitationService.issue(actor=request.user, location=item.employment_location,
            plan=item.access_plan, email=item.delivery_address, employee=item.employee)
        from django.conf import settings
        return Response({**self.get_serializer(created).data, "invitation_url": f"{settings.FRONTEND_BASE_URL}/register#invite={token}"}, status=201, headers={"Cache-Control": "no-store"})


class EmployeeObjects(APIView):
    def get(self, request, employee_id):
        from .onboarding_api import visible_employees
        employee = get_object_or_404(visible_employees(request.user, "people.employee.view"), pk=employee_id)
        visible = LocationAccessPolicy.visible(request.user)
        now = timezone.now()
        item = employee.object_responsibility_history.filter(valid_to__isnull=True).first()
        return Response({"employment_location": str(employee.primary_location_id) if visible.filter(pk=employee.primary_location_id).exists() else None,
            "can_manage": visible_employees(request.user, "people.employee.manage").filter(pk=employee.pk).exists(),
            "employment_location_name": visible.filter(pk=employee.primary_location_id).values_list("name", flat=True).first(),
            "responsibility_mode": item.mode if item else "selected",
            "responsibility_locations": list(ResponsibilityService.effective(employee).filter(pk__in=visible.values("pk")).values("id", "name")),
            "roles": [{"name": assignment.role.name, "location": str(assignment.location_id) if assignment.location_id else None,
                "location_name": assignment.location.name if assignment.location_id else "Контекст роли",
                "scopes": list(assignment.role.permission_grants.values_list("scope", flat=True).distinct())}
                for assignment in employee.access_roles.filter(is_active=True, role__is_active=True).filter(
                    Q(location__in=visible) | Q(location__isnull=True, org_unit__isnull=True, legal_entity__isnull=True)).filter(
                    Q(active_from__isnull=True) | Q(active_from__lte=now), Q(active_until__isnull=True) | Q(active_until__gt=now)).select_related("role", "location")]})

    @transaction.atomic
    def post(self, request, employee_id):
        from .onboarding_api import visible_employees
        employee = get_object_or_404(visible_employees(request.user, "people.employee.manage"), pk=employee_id)
        data = ResponsibilityInput(data=request.data)
        data.is_valid(raise_exception=True)
        ResponsibilityService.replace(employee=employee, actor=request.user, **data.validated_data)
        return self.get(request, employee_id)


class EmployeeAccessScope(APIView):
    @transaction.atomic
    def post(self, request, employee_id):
        from .onboarding_api import visible_employees
        from .registration import validate_plan, active_employee
        from access_control.services import RoleService
        from organizations.object_services import object_write
        employee = get_object_or_404(visible_employees(request.user, "people.employee.manage").select_for_update(of=("self",)), pk=employee_id)
        if not active_employee(employee):
            raise serializers.ValidationError("Сотрудник неактивен.")
        data = AccessInput(data=request.data)
        data.is_valid(raise_exception=True)
        values = data.validated_data
        location = get_object_or_404(locations_for(request.user, "people.invitation.delegate"), pk=values["access_locations"][0])
        with object_write():
            plan = validate_plan(request.user, location, {"role": str(values["role"]), "access_locations": [str(pk) for pk in values["access_locations"]]})
            role = Role.objects.get(pk=plan["role"])
            for pk in plan["access_locations"]:
                existing = employee.access_roles.filter(role=role, location_id=pk, is_active=True, org_unit__isnull=True, legal_entity__isnull=True)
                if values["action"] == "revoke":
                    for assignment in existing:
                        RoleService.revoke_role(assignment=assignment, actor_user=request.user)
                elif not existing.exists():
                    RoleService.assign_role(employee=employee, role=role, location_id=pk, actor_user=request.user)
            from .onboarding import _event
            _event("people.access_scope.changed", employee, request.user, new={"action": values["action"], "role": str(role.pk), "locations": plan["access_locations"]})
        return Response(status=204)


class AccessInput(StrictSerializer):
    role = serializers.UUIDField()
    action = serializers.ChoiceField(choices=["assign", "revoke"])
    access_locations = serializers.ListField(child=serializers.UUIDField(), min_length=1, max_length=100)


class EmployeeEmployment(APIView):
    @transaction.atomic
    def post(self, request, employee_id):
        from .onboarding_api import visible_employees
        from .services import EmployeeAssignmentService
        from access_control.services import PermissionService
        from .onboarding import _event
        from rest_framework.exceptions import PermissionDenied
        employee = get_object_or_404(visible_employees(request.user, "people.employee.manage").select_for_update(of=("self",)), pk=employee_id)
        if not request.user.is_superuser and not PermissionService.has_permission(employee=getattr(request.user, "employee", None), permission="people.assignment.manage", obj=employee):
            raise PermissionDenied()
        serializer = EmploymentInput(data=request.data)
        serializer.is_valid(raise_exception=True)
        location = get_object_or_404(locations_for(request.user, "people.invitation.delegate").filter(pk__in=public_locations().values("pk")), pk=serializer.validated_data["location"])
        before = str(employee.primary_location_id) if employee.primary_location_id else None
        assignment = EmployeeAssignmentService.replace_primary(employee=employee, actor_user=request.user,
            location=location, position=employee.position_ref, org_unit=employee.org_unit, legal_entity=employee.legal_entity)
        _event("people.employment_location.changed", employee, request.user, old={"location": before},
            new={"location": str(location.pk), "assignment": str(assignment.pk)})
        return Response({"assignment": str(assignment.pk), "location": str(location.pk)})


class EmploymentInput(StrictSerializer):
    location = serializers.UUIDField()


class ResponsibilityInput(StrictSerializer):
    mode = serializers.ChoiceField(choices=["all", "selected"])
    locations = serializers.ListField(child=serializers.UUIDField(), max_length=100)


from organizations.object_policies import LocationAccessPolicy
from django.db.models import Q
