import unicodedata

from django.core import signing
from .client import IikoError
from .models import KnownGuest


def name_digest(data):
    from .creation import digest
    def normalize(value):
        return " ".join(unicodedata.normalize("NFKC", value or "").casefold().replace("ё", "е").split())
    return digest([normalize(data.get("surname")), normalize(data.get("name"))])


def observe(connection_id, organization_id, profile):
    owner = profile.get("owner", {})
    if not owner.get("name") or not owner.get("surname"):
        return
    KnownGuest.objects.update_or_create(connection_id=connection_id, organization_id=organization_id,
        customer_id=profile["customerId"], defaults={"name_digest": name_digest(owner)})


def public_profile(profile):
    return {**profile, "cards": [{"id": card.get("id"), "number": card.get("number")} for card in profile["cards"]]}


def snapshot(profile):
    from .creation import digest
    if profile is None:
        return None
    value = {**profile}
    for key in ("cards", "categories", "walletBalances"):
        value[key] = sorted(profile[key], key=lambda row: str(row.get("id")))
    return digest(value)


def build_review(client, connection_id, organization_id, data):
    try:
        existing = client.registration(organization_id, number=data["cardNumber"])
    except IikoError as exc:
        if exc.code != "card_not_found":
            raise
        existing = None
    if existing:
        observe(connection_id, organization_id, existing)
    candidates = KnownGuest.objects.filter(connection_id=connection_id, organization_id=organization_id,
                                           name_digest=name_digest(data)).order_by("customer_id")
    limited = candidates.count() > 20
    matches = []
    incomplete = False
    for candidate in candidates[:20]:
        try:
            profile = existing if existing and existing["customerId"] == str(candidate.customer_id) else client.registration(organization_id, customer_id=candidate.customer_id)
            if profile.get("isDeleted") is True:
                continue
            observe(connection_id, organization_id, profile)
            if name_digest(profile["owner"]) == name_digest(data):
                matches.append(public_profile(profile))
        except IikoError:
            incomplete = True
    return {"existing": existing, "duplicates": matches, "incomplete": incomplete, "limited": limited}


def signature_data(plan, *, actor, connection_id, organization_id, operation_id, data):
    from .creation import digest
    return {"replacementMode": "delete_guest_v1", "actor": str(actor.pk), "connection": connection_id, "organization": organization_id,
            "operation": str(operation_id), "form": digest(data), "existing": snapshot(plan["existing"]),
            "duplicates": digest(plan["duplicates"]), "incomplete": plan["incomplete"], "limited": plan["limited"]}


def present_review(plan, **scope):
    return {"confirmationToken": signing.dumps(signature_data(plan, **scope), salt="iiko-card-review"),
            "existingCard": public_profile(plan["existing"]) if plan["existing"] else None,
            "duplicates": plan["duplicates"], "incomplete": plan["incomplete"], "limited": plan["limited"],
            "coverage": "Проверены только гости, ранее встречавшиеся в AYS Connect. Это не полный поиск по кабинету iiko."}


def validate_review(plan, approvals, **scope):
    try:
        signed = signing.loads(approvals.get("confirmationToken", ""), salt="iiko-card-review", max_age=900)
    except signing.BadSignature:
        raise IikoError("confirmation_expired") from None
    if signed != signature_data(plan, **scope):
        raise IikoError("confirmation_changed")
    if plan["existing"] and approvals.get("confirmReplacement") != "yes":
        raise IikoError("replacement_confirmation_required")
    if (plan["duplicates"] or plan["incomplete"] or plan["limited"]) and approvals.get("confirmDuplicates") != "yes":
        raise IikoError("duplicate_confirmation_required")


def remove_confirmed(client, operation, data, plan):
    from .creation import record
    organization_id = str(operation.organization_id)
    current = client.registration(organization_id, number=data["cardNumber"])
    if snapshot(current) != snapshot(plan["existing"]):
        raise IikoError("confirmation_changed")
    cards = [card for card in current["cards"] if card.get("number") == data["cardNumber"]]
    if len(cards) != 1 or not cards[0].get("track") or not cards[0].get("id"):
        raise IikoError("ambiguous_card_registration")
    target = cards[0]
    if sum(card.get("track") == target["track"] for card in current["cards"]) != 1:
        raise IikoError("ambiguous_card_registration")
    # The new track is the printed number; never steal that track from another card.
    try:
        owner = client.customer_by_track(organization_id, data["cardNumber"])
    except IikoError as exc:
        if exc.code != "card_not_found":
            raise
    else:
        if owner != current["customerId"] or target["track"] != data["cardNumber"]:
            raise IikoError("card_occupied")
    operation.previous_customer_id = current["customerId"]
    operation.stage = "delete_customer"
    operation.save(update_fields=["previous_customer_id", "stage", "updated_at"])
    record(operation, "iiko.card.guest.deletion_confirmed")
    client.delete_customer(organization_id, current["customerId"])
    operation.stage = "verify_removal"
    operation.save(update_fields=["stage", "updated_at"])
    remaining = client.registration(organization_id, customer_id=current["customerId"])
    if remaining.get("isDeleted") is not True:
        raise IikoError("customer_deletion_not_confirmed")
    for lookup, value in [(client.card, data["cardNumber"]), (client.customer_by_track, target["track"]),
                          (client.customer_by_track, data["cardNumber"])]:
        try:
            lookup(organization_id, value)
        except IikoError as exc:
            if exc.code != "card_not_found":
                raise
        else:
            raise IikoError("removal_not_confirmed")
    record(operation, "iiko.card.guest.deleted")
