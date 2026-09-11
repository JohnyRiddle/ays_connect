from dataclasses import dataclass
from functools import lru_cache
import threading

from django.conf import settings
from drf_spectacular.utils import OpenApiTypes, extend_schema
from rest_framework import serializers
from rest_framework.exceptions import NotFound
from rest_framework.permissions import BasePermission, IsAuthenticated
from rest_framework.response import Response
from rest_framework.throttling import UserRateThrottle
from rest_framework.views import APIView

from access_control.services import PermissionService
from .client import IikoClient, IikoError, uuid_value
from .config import ConfigurationError, Connection, read_env_file
from .reviews import observe


@dataclass(frozen=True)
class ConnectionScope:
    """Unmapped external cabinet: only an explicit GLOBAL grant is sufficient."""
    pk: str


class CanReadIikoCard(BasePermission):
    action = "view"
    message = "Нет права проверки карт этой локации. Обратитесь к администратору."

    def has_permission(self, request, view):
        connection_id = view.kwargs["connection_id"]
        if connection_id not in settings.IIKO_CONNECTIONS:
            raise NotFound("Подключение недоступно.")
        return request.user.is_superuser or PermissionService.has_permission(
            employee=getattr(request.user, "employee", None),
            permission=f"iiko.{connection_id}.card.{self.action}", obj=ConnectionScope(connection_id),
        )


class CardCheckThrottle(UserRateThrottle):
    scope = "iiko_card_check"
    rate = "10/min"


class CardCheckInput(serializers.Serializer):
    cardNumber = serializers.CharField(max_length=256, trim_whitespace=True)

    def to_internal_value(self, data):
        if not isinstance(data, dict) or set(data) != {"cardNumber"} or not isinstance(data.get("cardNumber"), str):
            raise serializers.ValidationError({"cardNumber": "Передайте только строковый номер карты."})
        return super().to_internal_value(data)

    def validate_cardNumber(self, value):
        if any(ord(char) < 32 for char in value):
            raise serializers.ValidationError("Недопустимые символы в номере карты.")
        return value


@lru_cache(maxsize=16)
def client_for(config):
    # Cache token/client per immutable configuration (including credentials), never guest responses.
    return IikoClient(config), threading.BoundedSemaphore(1)


ERROR_MESSAGES = {
    "card_not_found": "Карта с этим номером не зарегистрирована в iiko.",
    "authentication_failed": "Не удалось авторизовать подключение iiko. Обратитесь к администратору.",
    "access_denied": "Ключ iiko не разрешает чтение карты.",
    "rate_limited": "iiko ограничил частоту запросов. Повторите проверку позже.",
    "bad_request": "iiko не смог обработать номер. Проверьте его; отсутствие карты не подтверждено.",
    "not_found_unconfirmed": "iiko не вернул карту. Проверьте номер и подключение; отсутствие карты не подтверждено.",
    "customer_not_returned_unconfirmed": "iiko не вернул владельца. Отсутствие карты не подтверждено.",
}


class CardCheckView(APIView):
    permission_classes = [IsAuthenticated, CanReadIikoCard]
    throttle_classes = [CardCheckThrottle]

    def finalize_response(self, request, response, *args, **kwargs):
        response = super().finalize_response(request, response, *args, **kwargs)
        response["Cache-Control"] = "no-store, private"
        response["Pragma"] = "no-cache"
        return response

    def handle_exception(self, exc):
        # Never emit debug tracebacks containing a posted card number or upstream credentials.
        try:
            return super().handle_exception(exc)
        except Exception:
            return Response({"error": {"code": "check_unavailable", "message": "Проверка временно недоступна."}}, status=503)

    @extend_schema(request=CardCheckInput, responses={200: OpenApiTypes.OBJECT})
    def post(self, request, connection_id):
        data = CardCheckInput(data=request.data)
        data.is_valid(raise_exception=True)
        entry = settings.IIKO_CONNECTIONS[connection_id]
        try:
            config = Connection.from_env(read_env_file(entry["env_file"])) if entry.get("env_file") else Connection.from_env()
            organization_id = uuid_value(entry.get("organization_id"))
            if config.connection_id != connection_id or not organization_id:
                raise ConfigurationError("Connection scope mismatch.")
            client, gate = client_for(config)
        except (ConfigurationError, KeyError):
            return Response({"error": {"code": "not_configured", "message": "Подключение локации не настроено. Обратитесь к администратору."}}, status=503)
        if not gate.acquire(blocking=False):
            return Response({"error": {"code": "check_busy", "message": "Уже выполняется проверка в этой локации. Повторите запрос позже."}}, status=429)
        try:
            result = client.card(organization_id, data.validated_data["cardNumber"], reveal_numbers=True, include_owner=True)
            observe(connection_id, organization_id, result)
        except IikoError as exc:
            return Response({"error": {
                "code": exc.code,
                "message": ERROR_MESSAGES.get(exc.code, "Не удалось получить ответ iiko. Повторите проверку позже."),
                "correlationId": exc.correlation_id,
            }}, status=429 if exc.code == "rate_limited" else 502)
        finally:
            gate.release()
        return Response(result)
