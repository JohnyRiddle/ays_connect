import base64
import http.client
import json
import math
import re
import ssl
import threading
import time
from dataclasses import dataclass, field
from decimal import Decimal, InvalidOperation
from datetime import timezone
from email.utils import parsedate_to_datetime
from uuid import UUID

from .config import Connection


PATHS = {
    "auth": "/api/v2/access_token",
    "organizations": "/api/1/organizations",
    "categories": "/api/1/loyalty/iiko/customer_category",
    "programs": "/api/1/loyalty/iiko/program",
    "card": "/api/1/loyalty/iiko/customer/info",
}
MAX_RESPONSE_BYTES = 4 * 1024 * 1024
ANONYMOUS_CARD_HINT = "iiko запретил удаление единственной карты анонимного гостя. Передача остановлена; требуется разбор регистрации прежнего гостя в iiko. Повторять удаление без изменения условий не следует."


def anonymous_card_rejection(diagnostics):
    fields = diagnostics.get("fields", {})
    return (diagnostics.get("endpoint") == "/api/1/loyalty/iiko/customer/card/remove"
            and fields.get("message") == "Can't delete a single card from an anonymous guest.")


WRITE_PATHS = {
    "topup_wallet": "/api/1/loyalty/iiko/customer/wallet/topup",
    "delete_customer": "/api/1/loyalty/iiko/delete_customers",
    "remove_card": "/api/1/loyalty/iiko/customer/card/remove",
    "create_customer": "/api/1/loyalty/iiko/customer/create_or_update",
    "add_category": "/api/1/loyalty/iiko/customer_category/add",
    "add_card": "/api/1/loyalty/iiko/customer/card/add",
}


def uuid_value(value):
    try:
        return str(UUID(str(value)))
    except (ValueError, TypeError, AttributeError):
        return None


class IikoError(Exception):
    """Safe exception text; redacted write diagnostics are separate, never logged implicitly."""
    def __init__(self, code, *, status=None, correlation_id=None, diagnostics=None):
        self.code = code
        self.status = status
        self.correlation_id = correlation_id
        self.diagnostics = diagnostics or {}
        super().__init__(f"iiko: {code}; HTTP={status or '-'}; correlationId={correlation_id or '-'}")


@dataclass(repr=False)
class Response:
    status: int
    body: dict = field(repr=False)
    retry_after: str | None = None


class Transport:
    def post(self, config, path, payload, token=None):
        conn = http.client.HTTPSConnection("api-ru.iiko.services", timeout=config.connect_timeout,
                                           context=ssl.create_default_context())
        try:
            conn.connect()
            conn.sock.settimeout(config.read_timeout)
            headers = {"Content-Type": "application/json", "Accept": "application/json",
                       "Timeout": str(max(1, math.ceil(config.read_timeout)))}
            if token:
                headers["Authorization"] = "Bearer " + token
            conn.request("POST", path, body=json.dumps(payload).encode("utf-8"), headers=headers)
            response = conn.getresponse()
            raw = response.read(MAX_RESPONSE_BYTES + 1)
            if len(raw) > MAX_RESPONSE_BYTES:
                raise IikoError("response_too_large", status=response.status)
            try:
                body = json.loads(raw)
            except (ValueError, UnicodeError):
                body = {}
            if not isinstance(body, dict):
                body = {}
            return Response(response.status, body, response.getheader("Retry-After"))
        except ssl.SSLError:
            raise IikoError("tls_error") from None
        except (TimeoutError, OSError, http.client.HTTPException):
            raise IikoError("network_unavailable") from None
        finally:
            conn.close()


def mask_card(number):
    number = str(number or "")
    return "****" + (number[-4:] if len(number) > 4 else "")


def items(body, key):
    value = body.get(key)
    if not isinstance(value, list) or any(not isinstance(item, dict) for item in value):
        raise IikoError("invalid_response")
    return value


def pick(value, keys):
    return {k: value[k] for k in keys if k in value}


class IikoClient:
    """One immutable connection per instance; tokens and results never share a cache.

    Reads may retry. Mutations are sent exactly once; persistence belongs to the service.
    """
    def __init__(self, config: Connection, *, transport=None, clock=time.time, sleep=time.sleep):
        self._config = config
        self._transport = transport or Transport()
        self._clock = clock
        self._sleep = sleep
        self._token = None
        self._expires_at = 0
        self._lock = threading.RLock()

    @property
    def config(self):
        return self._config

    def _correlation(self, body):
        value = uuid_value(body.get("correlationId"))
        secrets = (self.config.app_id, self.config.api_key, self.config.client_secret, self._token, body.get("token"))
        return value if value and all(not isinstance(s, str) or s.lower() not in value.lower() for s in secrets) else None

    def _delay(self, retry_after, attempt):
        if retry_after:
            try:
                delay = float(retry_after)
            except ValueError:
                try:
                    date = parsedate_to_datetime(retry_after)
                    delay = date.replace(tzinfo=date.tzinfo or timezone.utc).timestamp() - self._clock()
                except (ValueError, TypeError, OverflowError):
                    delay = 2 ** attempt
            # Do not sleep indefinitely or retry before a long server cooldown.
            if not math.isfinite(delay) or delay > 10:
                return None
            return max(0, delay)
        return 2 ** attempt

    def _send(self, operation, payload, token=None):
        # Every member is explicitly reviewed as authorization or read-only POST.
        path = PATHS[operation]
        for attempt in range(self.config.max_retries + 1):
            retry_after = None
            try:
                result = self._transport.post(self.config, path, payload, token)
            except IikoError as exc:
                if exc.code != "network_unavailable":
                    raise
                error = IikoError("network_unavailable")
            else:
                correlation = self._correlation(result.body)
                if result.status == 200:
                    if "error" in result.body or "errorDescription" in result.body:
                        raise IikoError("api_error", status=200, correlation_id=correlation)
                    return result.body
                # Observed RU API envelope, 2026-09-10. Generic 400 is NOT absence.
                if operation == "card" and payload.get("type") == "cardNumber" and result.status == 400 and result.body.get("code") == "Transport_WrongCardNumber" and result.body.get("errorCode") == "Card_CanNotFindByNumber":
                    raise IikoError("card_not_found", status=400, correlation_id=correlation)
                if operation == "card" and payload.get("type") == "cardTrack" and result.status == 400 and result.body.get("code") == "Transport_WrongCarTrack" and result.body.get("errorCode") == "Card_CanNotFindByTrack":
                    raise IikoError("card_not_found", status=400, correlation_id=correlation)
                codes = {400: "bad_request", 401: "authentication_failed", 403: "access_denied",
                         404: "not_found_unconfirmed", 408: "timeout", 429: "rate_limited"}
                error = IikoError(codes.get(result.status, "upstream_error"),
                                  status=result.status, correlation_id=correlation)
                if result.status not in (408, 429, 500, 502, 503, 504):
                    raise error
                retry_after = result.retry_after
            delay = self._delay(retry_after, attempt)
            if attempt == self.config.max_retries or delay is None:
                raise error from None
            self._sleep(delay)

    def authenticate(self):
        with self._lock:
            if self._token and self._clock() < self._expires_at:
                return {"authenticated": True, "cached": True}
            body = self._send("auth", {"appId": self.config.app_id,
                                      "clientSecret": self.config.client_secret, "apiKey": self.config.api_key})
            token = body.get("token")
            try:
                if not isinstance(token, str) or len(token.split(".")) != 3:
                    raise ValueError
                encoded = token.split(".")[1]
                claims = json.loads(base64.urlsafe_b64decode(encoded + "=" * (-len(encoded) % 4)))
                exp = claims["exp"]
                if isinstance(exp, bool) or not isinstance(exp, (int, float)) or not math.isfinite(exp):
                    raise ValueError
                expires = min(exp, self._clock() + 3600) - 60
                if expires <= self._clock():
                    raise ValueError
            except (ValueError, TypeError, KeyError, AttributeError):
                raise IikoError("invalid_token_response", correlation_id=self._correlation(body)) from None
            # exp is only a cache deadline, never used as locally verified authorization.
            self._token, self._expires_at = token, expires
            return {"authenticated": True, "cached": False, "correlationId": self._correlation(body)}

    def _read(self, operation, payload):
        with self._lock:
            self.authenticate()
            for refresh in range(2):
                try:
                    return self._send(operation, payload, self._token)
                except IikoError as exc:
                    if exc.status != 401:
                        raise
                    self._token, self._expires_at = None, 0
                    if refresh:
                        raise
                    self.authenticate()

    def _scope(self, organization_id):
        organization_id = uuid_value(organization_id)
        if not organization_id:
            raise IikoError("invalid_organization_id")
        return organization_id

    def _write(self, operation, payload):
        with self._lock:
            self.authenticate()
            # Never retry a mutation, even on 401, timeout or an invalid response.
            result = self._transport.post(self.config, WRITE_PATHS[operation], payload, self._token)
            if result.status != 200 or any(key in result.body for key in ("error", "errorCode", "errorDescription")):
                diagnostics = self._write_diagnostics(operation, result.body, payload)
                if result.status == 401:
                    self._token, self._expires_at = None, 0
                raise IikoError("write_not_confirmed", status=result.status, correlation_id=self._correlation(result.body),
                                diagnostics=diagnostics)
            return result.body

    def _write_diagnostics(self, operation, body, payload):
        # Only selected error fields; never persist request bodies, headers or profiles.
        sensitive = [self._token, self.config.app_id, self.config.client_secret, self.config.api_key]
        sensitive += [value for key, value in payload.items() if isinstance(value, str) and key not in {"organizationId", "customerId", "categoryId"}]
        def clean(value):
            if not isinstance(value, (str, int)) or isinstance(value, bool):
                return None
            text = str(value)
            for secret in sorted(filter(None, sensitive), key=len, reverse=True):
                text = text.replace(secret, "[скрыто]")
            text = re.sub(r"(?i)Bearer\s+\S+", "Bearer [скрыто]", text)
            return "".join(c for c in text if ord(c) >= 32 or c in "\n\t")[:2000]
        fields = {}
        for key in ("code", "errorCode", "error", "errorDescription", "message", "description"):
            value = clean(body.get(key))
            if value:
                fields[key] = value
        if isinstance(body.get("error"), dict):
            for key in ("code", "message", "description"):
                value = clean(body["error"].get(key))
                if value:
                    fields["error." + key] = value
        return {"endpoint": WRITE_PATHS[operation], "fields": fields}

    def create_customer(self, organization_id, *, number, name, surname, patronymic, comment=""):
        # iiko interprets a supplied id as an EXISTING login, not an allocated new UUID.
        # Number/track have both passed the absence preflight before this upsert.
        body = self._write("create_customer", {
            "organizationId": self._scope(organization_id), "cardNumber": number, "cardTrack": number,
            "name": name, "surName": surname, "middleName": patronymic,
            "comment": comment,
            "shouldReceiveLoyaltyInfo": False, "shouldReceivePromoActionsInfo": False,
        })
        customer_id = uuid_value(body.get("id"))
        if not customer_id:
            raise IikoError("write_not_confirmed", status=200, correlation_id=self._correlation(body))
        return customer_id

    def add_category(self, organization_id, customer_id, category_id):
        self._write("add_category", {"organizationId": self._scope(organization_id),
                                    "customerId": str(customer_id), "categoryId": category_id})

    def add_card(self, organization_id, customer_id, number):
        # Explicit pilot convention verified on the user-approved reference card.
        self._write("add_card", {"organizationId": self._scope(organization_id),
                                "customerId": str(customer_id), "cardNumber": number, "cardTrack": number})

    def customer_by_track(self, organization_id, track):
        body = self._read("card", {"organizationId": self._scope(organization_id), "type": "cardTrack", "cardTrack": track})
        if not uuid_value(body.get("id")):
            raise IikoError("customer_not_returned_unconfirmed")
        return uuid_value(body["id"])

    def registration(self, organization_id, *, number=None, customer_id=None):
        organization_id = self._scope(organization_id)
        query = {"type": "id", "id": str(customer_id)} if customer_id else {"type": "cardNumber", "cardNumber": number}
        body = self._read("card", {"organizationId": organization_id, **query})
        identifier = uuid_value(body.get("id"))
        if not identifier or (customer_id and identifier != str(customer_id)):
            raise IikoError("invalid_response")
        return {"customerId": identifier,
                "isDeleted": body.get("isDeleted") is True,
                "comment": body.get("comment") or "",
                "owner": {key: body.get(source) or "" for key, source in [("name", "name"), ("surname", "surname"), ("patronymic", "middleName")]},
                "cards": [pick(card, ("id", "number", "track")) for card in items(body, "cards")],
                "categories": [pick(item, ("id", "name", "isActive")) for item in items(body, "categories")],
                "walletBalances": [pick(item, ("id", "name", "type", "balance")) for item in items(body, "walletBalances")]}

    def remove_card(self, organization_id, customer_id, track):
        if not isinstance(track, str) or not track:
            raise IikoError("invalid_card_track")
        self._write("remove_card", {"organizationId": self._scope(organization_id), "customerId": str(customer_id), "cardTrack": track})

    def delete_customer(self, organization_id, customer_id):
        identifier = uuid_value(customer_id)
        if not identifier:
            raise IikoError("invalid_customer_id")
        body = self._write("delete_customer", {"organizationId": self._scope(organization_id), "customerIds": [identifier]})
        if any(type(body.get(key)) is not int for key in ("total", "deleted", "notFound")) or (body["total"], body["deleted"], body["notFound"]) != (1, 1, 0):
            raise IikoError("customer_deletion_not_confirmed", status=200,
                            diagnostics=self._write_diagnostics("delete_customer", body, {}))

    def topup_wallet(self, organization_id, customer_id, wallet_id, amount, operation_id):
        customer_id, wallet_id, operation_id = map(uuid_value, (customer_id, wallet_id, operation_id))
        if not all((customer_id, wallet_id, operation_id)):
            raise IikoError("invalid_topup_parameters")
        try:
            if not isinstance(amount, (str, Decimal)):
                raise ValueError
            value = Decimal(amount)
            if not value.is_finite() or value <= 0 or value != value.quantize(Decimal("0.01")) or not math.isfinite(float(value)):
                raise ValueError
        except (InvalidOperation, ValueError, OverflowError):
            raise IikoError("invalid_topup_amount") from None
        # The API has no idempotency key. The comment is a trace, NOT deduplication.
        # Caller must durably reserve the attempt before this non-retrying write.
        self._write("topup_wallet", {"organizationId": self._scope(organization_id),
            "customerId": customer_id, "walletId": wallet_id, "sum": float(value),
            "comment": "AYS Connect operation " + operation_id})

    def organizations(self):
        body = self._read("organizations", {"returnAdditionalInfo": False, "includeDisabled": False})
        return {"connectionId": self.config.connection_id, "correlationId": self._correlation(body),
                "organizations": [pick(i, ("id", "name")) for i in items(body, "organizations")]}

    def categories(self, organization_id):
        organization_id = self._scope(organization_id)
        body = self._read("categories", {"organizationId": organization_id})
        return {"connectionId": self.config.connection_id, "organizationId": organization_id,
                "correlationId": self._correlation(body),
                "guestCategories": [pick(i, ("id", "name", "isActive", "isDefaultForNewGuests"))
                                    for i in items(body, "guestCategories")]}

    def programs(self, organization_id):
        organization_id = self._scope(organization_id)
        body = self._read("programs", {"organizationId": organization_id, "withoutMarketingCampaigns": True})
        return {"connectionId": self.config.connection_id, "organizationId": organization_id,
                "correlationId": self._correlation(body),
                "Programs": [pick(i, ("id", "name", "isActive", "programType", "walletId", "appliedOrganizations"))
                             for i in items(body, "Programs")]}

    def card(self, organization_id, number, *, reveal_numbers=False, include_owner=False):
        organization_id = self._scope(organization_id)
        if not isinstance(number, str) or not number.strip() or len(number) > 256 or any(ord(c) < 32 for c in number):
            raise IikoError("invalid_card_number")
        body = self._read("card", {"organizationId": organization_id, "type": "cardNumber", "cardNumber": number})
        if not uuid_value(body.get("id")):
            # The published contract does not specify a definitive card-not-found code.
            raise IikoError("customer_not_returned_unconfirmed", correlation_id=self._correlation(body))
        display_number = (lambda value: str(value or "")) if reveal_numbers else mask_card
        result = {"connectionId": self.config.connection_id, "organizationId": organization_id,
                "correlationId": self._correlation(body), "card": display_number(number),
                "customerId": uuid_value(body["id"]),
                "cards": [{"id": uuid_value(i.get("id")), "number": display_number(i.get("number"))}
                          for i in items(body, "cards")],
                "categories": [pick(i, ("id", "name", "isActive", "isDefaultForNewGuests"))
                               for i in items(body, "categories")],
                "walletBalances": [pick(i, ("id", "name", "type", "balance"))
                                   for i in items(body, "walletBalances")]}

        if include_owner:
            result["comment"] = body.get("comment") or ""
            result["owner"] = {"surname": body.get("surname") or "", "name": body.get("name") or "", "patronymic": body.get("middleName") or ""}
        return result
