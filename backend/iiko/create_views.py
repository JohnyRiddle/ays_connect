from django.conf import settings
from decimal import Decimal
from rest_framework import serializers
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from drf_spectacular.utils import OpenApiTypes, extend_schema

from . import views
from .client import uuid_value
from .config import ConfigurationError, Connection, read_env_file
from .creation import PILOT_ORGANIZATION, REFERENCE_CATEGORIES, create_card, receipt
from .models import CardCreation, CardCategory
from .reviews import build_review, present_review
from .client import IikoError


class CanCreateIikoCard(views.CanReadIikoCard):
    action = "create"
    message = "Нет права создания карт этой локации."


class CanReassignIikoCard(views.CanReadIikoCard):
    action = "delete_guest"
    message = "Нет права удаления прежнего гостя iikoCard."


class CanTopupIikoCard(views.CanReadIikoCard):
    action = "topup"
    message = "Нет права пополнения кошелька iikoCard."


class CreateInput(views.CardCheckInput):
    confirmationToken = serializers.CharField(max_length=4096, required=False, allow_blank=True)
    confirmReplacement = serializers.ChoiceField(choices=["yes", ""], required=False)
    confirmDuplicates = serializers.ChoiceField(choices=["yes", ""], required=False)
    operationId = serializers.UUIDField()
    surname = serializers.CharField(max_length=100)
    name = serializers.CharField(max_length=100)
    patronymic = serializers.CharField(max_length=100, allow_blank=True)
    comment = serializers.CharField(max_length=2000, required=False, allow_blank=True, trim_whitespace=False)
    topupAmount = serializers.DecimalField(max_digits=12, decimal_places=2, min_value=Decimal("0.01"))

    def validate_topupAmount(self, value):
        return format(value, ".2f")

    def validate(self, attrs):
        if attrs["cardType"] == REFERENCE_CATEGORIES["cardType"] and Decimal(attrs["topupAmount"]) > Decimal("10000"):
            raise serializers.ValidationError({"topupAmount": "Сумма для карты питания не может превышать 10 000 ₽."})
        return attrs
    legalEntity = serializers.ChoiceField(choices=[])
    department = serializers.ChoiceField(choices=[])
    cardType = serializers.ChoiceField(choices=[])
    approval = serializers.ChoiceField(choices=[])

    def __init__(self, *args, connection_id="sheregesh", organization_id=PILOT_ORGANIZATION, **kwargs):
        super().__init__(*args, **kwargs)
        rows = list(CardCategory.objects.filter(connection_id=connection_id, organization_id=organization_id))
        for field in REFERENCE_CATEGORIES:
            self.fields[field].choices = [(str(row.external_id), row.name) for row in rows if row.field == field]

    def to_internal_value(self, data):
        optional = {"confirmationToken", "confirmReplacement", "confirmDuplicates", "comment"}
        if not isinstance(data, dict) or not set(self.fields).difference(optional).issubset(data) or set(data).difference(self.fields) or any(not isinstance(value, str) for value in data.values()):
            raise serializers.ValidationError({"form": "Передайте все поля формы строками, без дополнительных параметров."})
        if any(any(ord(char) < 32 and not (key == "comment" and char in "\r\n\t") for char in value) for key, value in data.items()):
            raise serializers.ValidationError({"form": "Управляющие символы недопустимы."})
        return serializers.Serializer.to_internal_value(self, data)


class CardCreateView(views.CardCheckView):
    preview_only = False
    permission_classes = [IsAuthenticated, CanCreateIikoCard, CanTopupIikoCard]
    throttle_classes = [views.CardCheckThrottle]

    @extend_schema(request=CreateInput, responses={200: OpenApiTypes.OBJECT, 201: OpenApiTypes.OBJECT})
    def post(self, request, connection_id):
        data = CreateInput(data=request.data, connection_id=connection_id,
                           organization_id=settings.IIKO_CONNECTIONS[connection_id].get("organization_id"))
        data.is_valid(raise_exception=True)
        values = dict(data.validated_data)
        operation_id = values.pop("operationId")
        approvals = {key: values.pop(key) for key in ["confirmationToken", "confirmReplacement", "confirmDuplicates"] if key in values}
        if not self.preview_only and approvals.get("confirmReplacement") == "yes" and not CanReassignIikoCard().has_permission(request, self):
            self.permission_denied(request, message=CanReassignIikoCard.message)
        entry = settings.IIKO_CONNECTIONS[connection_id]
        try:
            config = Connection.from_env(read_env_file(entry["env_file"])) if entry.get("env_file") else Connection.from_env()
            organization_id = uuid_value(entry.get("organization_id"))
            if config.connection_id != connection_id or connection_id != "sheregesh" or organization_id != PILOT_ORGANIZATION:
                raise ConfigurationError("Creation reference scope mismatch.")
            client, gate = views.client_for(config)
        except (ConfigurationError, KeyError):
            return Response({"error": {"code": "not_configured"}}, status=503)
        if not gate.acquire(blocking=False):
            return Response({"error": {"code": "check_busy"}}, status=429)
        try:
            if self.preview_only:
                try:
                    plan = build_review(client, connection_id, organization_id, values)
                    result = present_review(plan, actor=request.user, connection_id=connection_id,
                        organization_id=organization_id, operation_id=operation_id, data=values)
                    result["canReplace"] = CanReassignIikoCard().has_permission(request, self)
                    return Response(result)
                except IikoError as exc:
                    return Response({"error": {"code": exc.code}}, status=502)
            result, status = create_card(client=client, connection_id=connection_id, organization_id=organization_id,
                                         actor=request.user, operation_id=operation_id, data=values, approvals=approvals)
        finally:
            gate.release()
        return Response(result, status=status)


class CardCreationStatusView(views.CardCheckView):
    permission_classes = [IsAuthenticated, CanCreateIikoCard]
    http_method_names = ["get", "head", "options"]
    throttle_classes = []

    def get(self, request, connection_id, operation_id):
        queryset = CardCreation.objects.filter(pk=operation_id, connection_id=connection_id)
        if not request.user.is_superuser:
            queryset = queryset.filter(actor=request.user)
        operation = queryset.first()
        if operation is None:
            return Response({"error": {"code": "operation_not_found"}}, status=404)
        return Response(receipt(operation))


class CanReadCardCatalog(views.CanReadIikoCard):
    def has_permission(self, request, view):
        return super().has_permission(request, view) or CanCreateIikoCard().has_permission(request, view)


class CardCatalogView(views.CardCheckView):
    permission_classes = [IsAuthenticated, CanReadCardCatalog]
    http_method_names = ["get", "head", "options"]
    throttle_classes = []

    def get(self, request, connection_id):
        organization_id = uuid_value(settings.IIKO_CONNECTIONS[connection_id].get("organization_id"))
        fields = {field: [] for field in REFERENCE_CATEGORIES}
        for row in CardCategory.objects.filter(connection_id=connection_id, organization_id=organization_id):
            fields[row.field].append({"id": str(row.external_id), "name": row.name})
        return Response({"connectionId": connection_id, "organizationId": organization_id, "fields": fields})


class CardPrepareView(CardCreateView):
    preview_only = True
