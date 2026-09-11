import json
from decimal import Decimal, InvalidOperation

from django.db import IntegrityError, transaction
from django.utils.crypto import salted_hmac
from audit.services import AuditService
from events.services import DomainEventService
from .client import IikoError, anonymous_card_rejection, ANONYMOUS_CARD_HINT
from .models import CardCreation, CardCategory, KnownGuest
from .reviews import build_review, validate_review, remove_confirmed, observe, name_digest


PILOT_ORGANIZATION = "07727ae8-4b93-4529-ac85-9232fae45be3"
TOPUP_WALLET = "03bf0000-6bec-ac1f-5d42-08de178c0e2a"
REFERENCE_CATEGORIES = {
    "legalEntity": "f35f4f62-e37f-4b5f-a9bf-73eac924d12b",
    "department": "43d6f832-f4e0-4659-877f-5724c5727d60",
    "cardType": "12db95b7-3f4d-4ba7-9776-0577ad788986",
    "approval": "df9c9d05-e1e5-412e-9666-03f371e49d76",
}


def digest(value):
    return salted_hmac("iiko.card.creation.v1", json.dumps(value, sort_keys=True, ensure_ascii=False), algorithm="sha256").hexdigest()


def receipt(operation):
    return {"operationId": str(operation.pk), "connectionId": operation.connection_id,
            "organizationId": str(operation.organization_id), "status": operation.status,
            "stage": operation.stage, "customerId": str(operation.customer_id) if operation.stage.startswith("category_") or operation.stage in {"verify", "topup_wallet", "verify_topup", "complete"} else None,
            "topupAmount": str(operation.topup_amount) if operation.topup_amount is not None else None,
            "topupConfirmed": operation.topup_confirmed,
            "previousCustomerId": str(operation.previous_customer_id) if operation.previous_customer_id else None,
            "completedCategories": operation.completed_categories, "errorCode": operation.error_code, "httpStatus": operation.error_status,
            "diagnostics": operation.error_diagnostics, "updatedAt": operation.updated_at.isoformat(),
            "errorHint": ANONYMOUS_CARD_HINT if anonymous_card_rejection(operation.error_diagnostics) else "",
            "correlationId": str(operation.error_correlation_id) if operation.error_correlation_id else None}


def record(operation, action):
    # Audit and Outbox are local facts only; no consumer is allowed to replay iiko writes.
    data = receipt(operation)
    data.pop("diagnostics", None)  # Upstream text stays in the access-controlled operation only.
    AuditService.record(action=action, entity=operation, actor_user=operation.actor, new_value=data)
    DomainEventService.publish(event_type=action, entity=operation, actor=operation.actor, payload=data)


def create_card(*, client, connection_id, organization_id, actor, operation_id, data, approvals=None):
    selected = {field: data[field] for field in REFERENCE_CATEGORIES}
    allowed = {(item.field, str(item.external_id)) for item in CardCategory.objects.filter(
        connection_id=connection_id, organization_id=organization_id)}
    if any((field, value) not in allowed for field, value in selected.items()):
        return {"error": {"code": "invalid_categories"}}, 400
    fingerprint = digest(data)
    previous = CardCreation.objects.filter(pk=operation_id).first()
    if previous:
        if (previous.actor_id != actor.pk or previous.connection_id != connection_id or
            str(previous.organization_id) != organization_id or previous.request_digest != fingerprint):
            return {"error": {"code": "idempotency_conflict"}}, 409
        return receipt(previous), 200
    plan = None
    if approvals or KnownGuest.objects.filter(connection_id=connection_id, organization_id=organization_id,
                                               name_digest=name_digest(data)).exists():
        if not approvals or not approvals.get("confirmationToken"):
            return {"error": {"code": "duplicate_confirmation_required"}}, 409
        try:
            plan = build_review(client, connection_id, organization_id, data)
            validate_review(plan, approvals, actor=actor, connection_id=connection_id, organization_id=organization_id,
                            operation_id=operation_id, data=data)
        except IikoError as exc:
            return {"error": {"code": exc.code}}, 409
    try:
        with transaction.atomic():
            if plan and plan["existing"]:
                # Retire only a completed reservation belonging to the reviewed owner.
                # Running/uncertain attempts can never be superseded by this flow.
                CardCreation.objects.filter(connection_id=connection_id, organization_id=organization_id,
                    card_digest=digest(data["cardNumber"]), reservation_active=True, status="succeeded",
                    customer_id=plan["existing"]["customerId"]).update(reservation_active=False)
            operation, created = CardCreation.objects.get_or_create(pk=operation_id, defaults={
                "connection_id": connection_id, "organization_id": organization_id,
                "actor": actor, "card_digest": digest(data["cardNumber"]), "request_digest": fingerprint,
                "topup_amount": Decimal(data["topupAmount"]), "topup_wallet_id": TOPUP_WALLET,
            })
            if not created:
                if (operation.actor_id != actor.pk or operation.connection_id != connection_id or
                    str(operation.organization_id) != organization_id or operation.request_digest != fingerprint):
                    return {"error": {"code": "idempotency_conflict"}}, 409
                return receipt(operation), 200
            # Verify local persistence (including Outbox) BEFORE any external side effect.
            record(operation, "iiko.card.creation.requested")
    except IntegrityError:
        if CardCreation.objects.filter(connection_id=connection_id, organization_id=organization_id,
                                       card_digest=digest(data["cardNumber"]),
                                       status__in=["running", "succeeded", "needs_review"], reservation_active=True).exists():
            return {"error": {"code": "card_reserved"}}, 409
        raise

    return execute_creation(client=client, operation=operation, data=data, plan=plan)


def execute_creation(*, client, operation, data, plan=None):
    """Execute a reserved attempt. Recovery requires an explicit, verified operator decision."""
    organization_id = str(operation.organization_id)
    selected = {field: data[field] for field in REFERENCE_CATEGORIES}

    try:
        programs = client.programs(organization_id)["Programs"]
        if not any(p.get("walletId") == TOPUP_WALLET and p.get("isActive") is True for p in programs):
            raise IikoError("topup_wallet_unavailable")
        catalogue = client.categories(organization_id)["guestCategories"]
        active = {item.get("id") for item in catalogue if item.get("isActive") is True}
        if not set(selected.values()).issubset(active):
            raise IikoError("reference_unavailable")
        # A default category could change the approved benefit/approval rules.
        if any(item.get("isDefaultForNewGuests") is True and item.get("id") not in selected.values() for item in catalogue):
            raise IikoError("unexpected_default_categories")
        try:
            client.card(organization_id, data["cardNumber"])
        except IikoError as exc:
            if exc.code != "card_not_found":
                raise
        else:
            if not plan or not plan["existing"]:
                raise IikoError("card_occupied")
            remove_confirmed(client, operation, data, plan)
        if plan and plan["existing"] and operation.stage != "verify_removal":
            raise IikoError("confirmation_changed")
        try:
            client.customer_by_track(organization_id, data["cardNumber"])
        except IikoError as exc:
            if exc.code != "card_not_found":
                raise
        else:
            raise IikoError("card_occupied")

        operation.stage = "create_customer"
        operation.save(update_fields=["stage", "updated_at"])
        actual_customer_id = client.create_customer(organization_id, number=data["cardNumber"], name=data["name"],
                                                    surname=data["surname"], patronymic=data["patronymic"], comment=data.get("comment", ""))
        # The card is registered by create_or_update itself. Store the authoritative
        # ID immediately, before any subsequent remote step; never add the card twice.
        operation.customer_id = actual_customer_id
        operation.save(update_fields=["customer_id", "updated_at"])
        for field, category_id in selected.items():
            operation.stage = "category_" + field
            operation.save(update_fields=["stage", "updated_at"])
            client.add_category(organization_id, operation.customer_id, category_id)
            operation.completed_categories.append(category_id)
            operation.save(update_fields=["completed_categories", "updated_at"])
        operation.stage = "verify"
        operation.save(update_fields=["stage", "updated_at"])
        result = client.card(organization_id, data["cardNumber"], reveal_numbers=True)
        if (result["customerId"] != str(operation.customer_id) or
            not any(card["number"] == data["cardNumber"] for card in result["cards"]) or
            {item["id"] for item in result["categories"]} != set(selected.values()) or
            any(item.get("isActive") is not True for item in result["categories"])):
            raise IikoError("verification_mismatch")
        operation.topup_balance_before = wallet_balance(result, TOPUP_WALLET)
        operation.stage = "topup_wallet"
        operation.save(update_fields=["topup_balance_before", "stage", "updated_at"])
        record(operation, "iiko.card.topup.requested")
        client.topup_wallet(organization_id, operation.customer_id, TOPUP_WALLET, operation.topup_amount, operation.pk)
        operation.stage = "verify_topup"
        operation.save(update_fields=["stage", "updated_at"])
        funded = client.card(organization_id, data["cardNumber"], reveal_numbers=True)
        if (funded["customerId"] != str(operation.customer_id) or
            wallet_balance(funded, TOPUP_WALLET) != operation.topup_balance_before + operation.topup_amount):
            raise IikoError("topup_not_confirmed")
        operation.topup_confirmed = True
        operation.status = "succeeded"
        operation.stage = "complete"
    except Exception as exc:
        operation.status = "failed" if operation.stage == "preflight" else "needs_review"
        operation.error_code = exc.code if isinstance(exc, IikoError) else "creation_unavailable"
        operation.error_status = exc.status if isinstance(exc, IikoError) else None
        operation.error_diagnostics = exc.diagnostics if isinstance(exc, IikoError) else {}
        operation.error_correlation_id = exc.correlation_id if isinstance(exc, IikoError) else None
    # If this commit fails, durable running state still blocks every replay.
    with transaction.atomic():
        operation.save()
        if operation.status == "succeeded":
            observe(operation.connection_id, organization_id, {"customerId": str(operation.customer_id), "owner": data})
        record(operation, "iiko.card.creation." + operation.status)
    return receipt(operation), 201 if operation.status == "succeeded" else 200


def wallet_balance(profile, wallet_id):
    wallets = [w for w in profile.get("walletBalances", []) if w.get("id") == wallet_id]
    if len(wallets) != 1 or isinstance(wallets[0].get("balance"), bool):
        raise IikoError("topup_wallet_unavailable")
    try:
        value = Decimal(str(wallets[0].get("balance")))
        if not value.is_finite() or value != value.quantize(Decimal("0.01")):
            raise ValueError
        return value
    except (ValueError, InvalidOperation):
        raise IikoError("invalid_wallet_balance") from None
