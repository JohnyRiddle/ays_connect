from django.conf import settings
from django.core.exceptions import ValidationError as DjangoValidationError
from django.db.models import Prefetch, Q
from django.utils import timezone
from rest_framework import serializers, status, viewsets
from rest_framework.decorators import action, api_view, permission_classes, throttle_classes
from rest_framework.permissions import AllowAny
from rest_framework.response import Response
from rest_framework.throttling import ScopedRateThrottle
from rest_framework.views import APIView

from access_control.models import EmployeeRole, Scope
from access_control.services import PermissionService
from .models import Employee, EmployeeInvitation, RegistrationRequest
from .onboarding import InvitationService, RegistrationService


class PublicScopedThrottle(ScopedRateThrottle):
    pass


def account_status(employee):
    if employee.user_id:
        return "ACTIVE" if employee.user.is_active else "BLOCKED"
    invite = next((x for x in getattr(employee, "open_invitations", []) if not x.used_at and not x.revoked_at), None)
    if invite:
        return "INVITED" if invite.expires_at > timezone.now() else "INVITATION_EXPIRED"
    if getattr(employee, "pending_registrations", None):
        return "PENDING_APPROVAL"
    return "NO_ACCOUNT"


class EmployeeDirectorySerializer(serializers.ModelSerializer):
    display_name = serializers.CharField(read_only=True)
    position_name = serializers.SerializerMethodField()
    org_unit_name = serializers.CharField(source="org_unit.name", read_only=True, default=None)
    location_name = serializers.CharField(source="primary_location.name", read_only=True, default=None)
    legal_entity_name = serializers.CharField(source="legal_entity.name", read_only=True, default=None)
    account_status = serializers.SerializerMethodField()
    account = serializers.SerializerMethodField()
    roles = serializers.SerializerMethodField()
    functional_groups = serializers.SerializerMethodField()

    class Meta:
        model = Employee
        fields = ("id", "display_name", "position_name", "org_unit_name", "location_name", "legal_entity_name", "status", "is_active", "account_status", "account", "roles", "functional_groups")

    def get_position_name(self, obj): return obj.position_ref.name if obj.position_ref else obj.position
    def get_account_status(self, obj): return account_status(obj)
    def get_account(self, obj):
        return None if not obj.user_id else {"email": obj.user.email, "is_active": obj.user.is_active, "last_login": obj.user.last_login}
    def get_roles(self, obj): return [{"code": x.role.code, "name": x.role.name} for x in obj.access_roles.all() if x.is_active]
    def get_functional_groups(self, obj): return [{"id": str(x.group_id), "name": x.group.name, "role": x.role} for x in obj.functional_group_memberships.all() if x.is_active]


def visible_employees(user, permission):
    qs = Employee.objects.select_related("user", "position_ref", "org_unit", "legal_entity", "primary_location").prefetch_related(Prefetch("invitations", queryset=EmployeeInvitation.objects.order_by("-created_at"), to_attr="open_invitations"), Prefetch("registration_requests", queryset=RegistrationRequest.objects.filter(status=RegistrationRequest.Status.PENDING), to_attr="pending_registrations"), "access_roles__role", "functional_group_memberships__group")
    if user.is_superuser:
        return qs
    actor = getattr(user, "employee", None)
    if not actor:
        return qs.none()
    grants = EmployeeRole.objects.filter(employee=actor, is_active=True, role__is_active=True, role__permission_grants__permission__code=permission).values("role__permission_grants__scope", "org_unit_id", "legal_entity_id")
    predicate = Q(pk__in=[])
    for grant in grants:
        scope = grant["role__permission_grants__scope"]
        if scope == Scope.GLOBAL: return qs
        if scope == Scope.OWN: predicate |= Q(pk=actor.pk)
        elif scope == Scope.ORG_UNIT: predicate |= Q(org_unit_id=grant["org_unit_id"] or actor.org_unit_id)
        elif scope == Scope.LEGAL_ENTITY: predicate |= Q(legal_entity_id=grant["legal_entity_id"] or actor.legal_entity_id)
        elif scope == Scope.TEAM: predicate |= Q(manager=actor) | Q(manager_id=actor.manager_id)
    return qs.filter(predicate).distinct()


class EmployeeDirectoryViewSet(viewsets.ReadOnlyModelViewSet):
    serializer_class = EmployeeDirectorySerializer
    permission_domain = "people.employee"

    def get_queryset(self):
        qs = visible_employees(self.request.user, "people.employee.view")
        p = self.request.query_params
        if p.get("search"): qs = qs.filter(Q(first_name__icontains=p["search"]) | Q(last_name__icontains=p["search"]) | Q(middle_name__icontains=p["search"]))
        for param, field in (("legal_entity", "legal_entity_id"), ("org_unit", "org_unit_id"), ("location", "primary_location_id"), ("position", "position_ref_id"), ("employee_status", "status")):
            if p.get(param): qs = qs.filter(**{field: p[param]})
        if p.get("account_status") == "ACTIVE": qs = qs.filter(user__isnull=False, user__is_active=True)
        elif p.get("account_status") == "BLOCKED": qs = qs.filter(user__isnull=False, user__is_active=False)
        elif p.get("account_status") == "NO_ACCOUNT": qs = qs.filter(user__isnull=True, invitations__isnull=True)
        elif p.get("account_status") == "INVITED": qs = qs.filter(user__isnull=True, invitations__used_at__isnull=True, invitations__revoked_at__isnull=True, invitations__expires_at__gt=timezone.now())
        ordering = {"name": ("last_name", "first_name"), "position": ("position_ref__name", "last_name"), "org_unit": ("org_unit__name", "last_name")}.get(p.get("ordering"), ("last_name", "first_name"))
        return qs.order_by(*ordering)

    def _require(self, code, employee):
        actor = getattr(self.request.user, "employee", None)
        if not self.request.user.is_superuser and not PermissionService.has_permission(employee=actor, permission=code, obj=employee):
            from rest_framework.exceptions import PermissionDenied
            raise PermissionDenied()

    @action(detail=True, methods=["post"])
    def invite(self, request, pk=None):
        employee = self.get_object(); self._require("people.invitation.manage", employee)
        try: invitation, raw = InvitationService.issue(employee=employee, actor_user=request.user, delivery_address=request.data.get("email", ""))
        except DjangoValidationError as exc: raise serializers.ValidationError(exc.message_dict if hasattr(exc, "message_dict") else exc.messages)
        return Response({"id": invitation.pk, "expires_at": invitation.expires_at, "activation_url": f"{settings.FRONTEND_BASE_URL}/activate/{raw}"}, status=201)

    @action(detail=True, methods=["post"], url_path="revoke-invitation")
    def revoke_invitation(self, request, pk=None):
        employee = self.get_object(); self._require("people.invitation.manage", employee)
        invitation = employee.invitations.filter(used_at__isnull=True, revoked_at__isnull=True).first()
        if not invitation: raise serializers.ValidationError("No active invitation.")
        InvitationService.revoke(invitation=invitation, actor_user=request.user)
        return Response(status=204)

    @action(detail=True, methods=["post"], url_path="account/block")
    def block(self, request, pk=None):
        employee = self.get_object(); self._require("people.account.manage", employee)
        if not employee.user_id: raise serializers.ValidationError("Employee has no account.")
        employee.user.is_active = False; employee.user.save(update_fields=["is_active"])
        from .onboarding import _event
        _event("employee.account.blocked", employee, request.user, new={"user_id": employee.user_id})
        return Response(self.get_serializer(employee).data)

    @action(detail=True, methods=["post"], url_path="account/unblock")
    def unblock(self, request, pk=None):
        employee = self.get_object(); self._require("people.account.manage", employee)
        if not employee.is_active or employee.status in {"archived", "suspended", "dismissed"}: raise serializers.ValidationError("Inactive employee cannot be unblocked.")
        if not employee.user_id: raise serializers.ValidationError("Employee has no account.")
        employee.user.is_active = True; employee.user.save(update_fields=["is_active"])
        from .onboarding import _event
        _event("employee.account.unblocked", employee, request.user, new={"user_id": employee.user_id})
        return Response(self.get_serializer(employee).data)


class RegistrationSerializer(serializers.ModelSerializer):
    class Meta:
        model = RegistrationRequest
        fields = ("id", "full_name", "email", "status", "matched_employee", "created_at", "expires_at", "reviewed_at", "rejection_code")
        read_only_fields = fields


class RegistrationViewSet(viewsets.ReadOnlyModelViewSet):
    serializer_class = RegistrationSerializer

    def get_queryset(self):
        queryset = RegistrationRequest.objects.select_related("matched_employee").order_by("-created_at")
        if self.request.user.is_superuser:
            return queryset
        actor = getattr(self.request.user, "employee", None)
        global_access = EmployeeRole.objects.filter(employee=actor, is_active=True, role__permission_grants__permission__code="people.registration.manage", role__permission_grants__scope=Scope.GLOBAL).exists()
        if global_access:
            return queryset
        visible = visible_employees(self.request.user, "people.registration.manage").values("pk")
        return queryset.filter(matched_employee_id__in=visible)

    def _require(self):
        actor = getattr(self.request.user, "employee", None)
        if not self.request.user.is_superuser and not PermissionService.has_permission(employee=actor, permission="people.registration.manage"):
            from rest_framework.exceptions import PermissionDenied
            raise PermissionDenied()

    def initial(self, request, *args, **kwargs): super().initial(request, *args, **kwargs); self._require()

    @action(detail=True, methods=["post"])
    def approve(self, request, pk=None):
        employee = visible_employees(request.user, "people.registration.manage").get(pk=request.data.get("employee_id"))
        try: invitation, raw = RegistrationService.approve(registration=self.get_object(), employee=employee, actor_user=request.user)
        except DjangoValidationError as exc: raise serializers.ValidationError(exc.messages)
        return Response({"status": "approved", "activation_url": f"{settings.FRONTEND_BASE_URL}/activate/{raw}", "invitation_id": invitation.pk})

    @action(detail=True, methods=["post"])
    def reject(self, request, pk=None):
        try: item = RegistrationService.reject(registration=self.get_object(), actor_user=request.user, reason=request.data.get("reason", "rejected"))
        except DjangoValidationError as exc: raise serializers.ValidationError(exc.messages)
        return Response(self.get_serializer(item).data)


class PublicRegistrationView(APIView):
    permission_classes = (AllowAny,); authentication_classes = (); throttle_classes = (PublicScopedThrottle,); throttle_scope = "registration"
    def post(self, request):
        serializer = serializers.Serializer(data=request.data)
        serializer.fields["full_name"] = serializers.CharField(max_length=300)
        serializer.fields["email"] = serializers.EmailField()
        serializer.is_valid(raise_exception=True)
        RegistrationService.create(**serializer.validated_data)
        return Response({"detail": RegistrationService.GENERIC_MESSAGE}, status=202)


class PublicActivationView(APIView):
    permission_classes = (AllowAny,); authentication_classes = (); throttle_classes = (PublicScopedThrottle,); throttle_scope = "activation"
    def get(self, request, token):
        invitation = InvitationService.context(token)
        if not invitation: return Response({"detail": "Activation link is unavailable."}, status=400)
        employee = invitation.employee
        return Response({"valid": True, "employee_name": employee.display_name, "position": employee.position_ref.name if employee.position_ref else employee.position, "organization": employee.legal_entity.name if employee.legal_entity else ""})
    def post(self, request, token):
        try: InvitationService.activate(token=token, password=request.data.get("password", ""), password_confirmation=request.data.get("password_confirmation", ""))
        except DjangoValidationError as exc: raise serializers.ValidationError(exc.message_dict if hasattr(exc, "message_dict") else {"detail": exc.messages})
        return Response({"detail": "Account activated."})
