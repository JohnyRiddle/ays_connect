import copy
import threading
from uuid import uuid4
from unittest import mock
from django.contrib.auth import get_user_model
from django.core.cache import cache
from django.test import TestCase, override_settings
from rest_framework.test import APIClient
from .client import IikoError
from .creation import PILOT_ORGANIZATION, REFERENCE_CATEGORIES, TOPUP_WALLET, digest
from .models import CardCreation, KnownGuest
from .reviews import observe, name_digest
from .tests import connection

URL = "/api/v1/iiko/connections/sheregesh/card/"
OLD = "11111111-1111-4111-8111-111111111111"
NEW = "22222222-2222-4222-8222-222222222222"
TARGET = "33333333-3333-4333-8333-333333333333"
OTHER = "44444444-4444-4444-8444-444444444444"


@override_settings(IIKO_CONNECTIONS={"sheregesh": {"organization_id": PILOT_ORGANIZATION}})
class ReviewTests(TestCase):
    def setUp(self):
        cache.clear()
        self.user = get_user_model().objects.create_user(username="reviewer", email="reviewer@example.invalid", is_superuser=True)
        self.api = APIClient(); self.api.force_authenticate(self.user)
        self.data = {"operationId": str(uuid4()), "cardNumber": "00001234", "surname": "Новый", "name": "Владелец", "patronymic": "", "topupAmount": "10000.00", **REFERENCE_CATEGORIES}
        self.old = {"customerId": OLD, "owner": {"surname": "Иванов", "name": "Иван", "patronymic": "Иванович"},
                    "cards": [{"id": TARGET, "number": "00001234", "track": "PRIVATE_TRACK"}, {"id": OTHER, "number": "other-card", "track": "OTHER_TRACK"}],
                    "categories": [{"id": value, "name": field, "isActive": True} for field,value in REFERENCE_CATEGORIES.items()],
                    "walletBalances": [{"id": "wallet", "name": "Bonus", "type": 1, "balance": 5000}]}
        self.new = None
        self.client = mock.Mock()
        self.client.programs.return_value = {"Programs": [{"walletId": TOPUP_WALLET, "isActive": True}]}
        def registration(org, *, number=None, customer_id=None):
            if customer_id == OLD or str(customer_id) == OLD: return copy.deepcopy(self.old)
            if customer_id and self.new and str(customer_id) == NEW: return copy.deepcopy(self.new)
            for profile in [self.new, self.old]:
                if profile and any(card["number"] == number for card in profile["cards"]): return copy.deepcopy(profile)
            raise IikoError("card_not_found")
        def card(org, number, **kwargs): return registration(org,number=number)
        def track(org, value):
            for profile in [self.new,self.old]:
                if profile and any(card["track"] == value for card in profile["cards"]): return profile["customerId"]
            raise IikoError("card_not_found")
        def remove(org, customer):
            self.assertEqual(customer, OLD)
            self.old["cards"] = []
            self.old["isDeleted"] = True
        def create(org, **data):
            self.assertFalse(any(card["number"] == data["number"] for card in self.old["cards"]))
            self.new = {"customerId": NEW,"owner": {"surname": data["surname"],"name":data["name"],"patronymic":data["patronymic"]},
                        "cards": [{"id":TARGET,"number":data["number"],"track":data["number"]}],"categories": [],"walletBalances": [{"id": TOPUP_WALLET, "balance": 0}]}
            return NEW
        def add(org, customer, value):
            self.new["categories"].append({"id":value,"isActive":True})
        def topup(org, customer, wallet, amount, operation): self.new["walletBalances"][0]["balance"] += float(amount)
        self.client.topup_wallet.side_effect = topup
        self.client.registration.side_effect = registration
        self.client.card.side_effect = card
        self.client.customer_by_track.side_effect = track
        self.client.delete_customer.side_effect = remove
        self.client.create_customer.side_effect = create
        self.client.add_category.side_effect = add
        self.client.categories.return_value = {"guestCategories": self.old["categories"]}
        mock.patch("iiko.views.client_for", return_value=(self.client, threading.BoundedSemaphore(1))).start()
        mock.patch("iiko.create_views.Connection.from_env", return_value=connection()).start()
        self.addCleanup(mock.patch.stopall)
        self.previous = CardCreation.objects.create(id=uuid4(), connection_id="sheregesh", organization_id=PILOT_ORGANIZATION,
            card_digest=digest("00001234"), request_digest=digest({}), actor=self.user, customer_id=OLD, status="succeeded", stage="complete")

    def prepare(self):
        result = self.api.post(URL+"prepare/",self.data,format="json")
        self.assertEqual(result.status_code,200)
        self.token = result.data["confirmationToken"]
        return result.data

    def submit(self, **changes):
        return self.api.post(URL+"create/", {**self.data,"confirmationToken":self.token,"confirmReplacement":"yes",**changes},format="json")

    def test_preview_is_read_only_and_shows_owner_balances_without_track(self):
        self.old["comment"] = "Комментарий прежнего владельца"
        result = self.prepare()
        self.assertEqual(result["existingCard"]["comment"], self.old["comment"])
        self.assertEqual(result["existingCard"]["owner"],self.old["owner"])
        self.assertEqual(result["existingCard"]["walletBalances"][0]["balance"],5000)
        self.assertNotIn("PRIVATE_TRACK", str(result))
        self.client.delete_customer.assert_not_called(); self.client.create_customer.assert_not_called()
        self.assertEqual(CardCreation.objects.count(),1)


    def test_edited_new_comment_invalidates_confirmation(self):
        self.data["comment"] = "Первый текст"
        self.prepare()
        self.assertEqual(self.submit(comment="Новый текст").status_code, 409)
        self.client.delete_customer.assert_not_called()
        self.client.create_customer.assert_not_called()

    def test_changed_old_comment_invalidates_confirmation(self):
        self.old["comment"] = "Первый текст"
        self.prepare()
        self.old["comment"] = "Изменено в iiko"
        self.assertEqual(self.submit().status_code, 409)
        self.client.delete_customer.assert_not_called()
        self.client.create_customer.assert_not_called()

    def test_confirmed_replacement_deletes_old_guest_without_transferring_balance(self):
        self.prepare(); result=self.submit()
        self.assertEqual(result.status_code,201)
        self.assertEqual(result.data["status"],"succeeded")
        self.client.delete_customer.assert_called_once_with(PILOT_ORGANIZATION, OLD)
        self.assertEqual([card["id"] for card in self.old["cards"]],[])
        self.assertEqual(self.old["walletBalances"][0]["balance"],5000)
        self.assertEqual(result.data["previousCustomerId"],OLD)
        self.assertEqual(result.data["customerId"],NEW)
        self.previous.refresh_from_db()
        self.assertFalse(self.previous.reservation_active)
        self.assertEqual(self.previous.status,"succeeded")
        self.client.reset_mock()
        self.assertEqual(self.submit().data,result.data)
        self.assertEqual(self.client.method_calls,[])

    def test_without_confirmation_no_removal_or_reservation_changes(self):
        self.prepare()
        self.assertEqual(self.submit(confirmReplacement="").status_code,409)
        self.client.delete_customer.assert_not_called()
        self.previous.refresh_from_db();self.assertTrue(self.previous.reservation_active)

    def test_duplicate_warning_ignores_missing_patronymic_and_requires_ack(self):
        self.data.update(surname="Иванов",name="Иван",patronymic="")
        result=self.prepare()
        self.assertEqual(len(result["duplicates"]),1)
        self.assertEqual(result["duplicates"][0]["owner"]["patronymic"],"Иванович")
        self.assertEqual(self.submit().data["error"]["code"],"duplicate_confirmation_required")
        self.client.delete_customer.assert_not_called()
        self.assertEqual(self.submit(confirmDuplicates="yes").data["status"],"succeeded")

    def test_free_number_still_warns_for_known_name(self):
        observe("sheregesh",PILOT_ORGANIZATION,self.old)
        self.data.update(cardNumber="free",surname="Иванов",name="Иван")
        result=self.prepare();self.assertIsNone(result["existingCard"])
        self.assertEqual(len(result["duplicates"]),1)
        response=self.api.post(URL+"create/",self.data,format="json")
        self.assertEqual(response.status_code,409)
        self.assertEqual(self.submit(confirmReplacement="",confirmDuplicates="yes").status_code,201)
        self.client.delete_customer.assert_not_called()

    def test_stale_snapshot_or_changed_form_requires_new_review(self):
        self.prepare(); self.old["walletBalances"][0]["balance"]=4000
        self.assertEqual(self.submit().data["error"]["code"],"confirmation_changed")
        self.old["walletBalances"][0]["balance"]=5000
        self.assertEqual(self.submit(surname="Изменён").data["error"]["code"],"confirmation_changed")
        self.client.delete_customer.assert_not_called()

    def test_second_read_immediately_before_removal_detects_change(self):
        self.prepare()
        def categories(org):
            self.old["owner"]["surname"]="Изменён"
            return {"guestCategories":self.old["categories"]}
        self.client.categories.side_effect=categories
        result=self.submit().data
        self.assertEqual(result["status"],"failed")
        self.assertEqual(result["errorCode"],"confirmation_changed")
        self.client.delete_customer.assert_not_called()

    def test_permission_revocation_blocks_confirmed_removal(self):
        self.prepare()
        with mock.patch("iiko.create_views.CanReassignIikoCard.has_permission",return_value=False):
            self.assertEqual(self.submit().status_code,403)
        self.client.delete_customer.assert_not_called()

    def test_confirmation_is_bound_to_actor_and_expires(self):
        self.prepare()
        other=get_user_model().objects.create_user(username="other",email="other@example.invalid",is_superuser=True)
        self.api.force_authenticate(other)
        self.assertEqual(self.submit().data["error"]["code"],"confirmation_changed")
        self.api.force_authenticate(self.user)
        with mock.patch("django.core.signing.TimestampSigner.unsign",side_effect=__import__('django.core.signing',fromlist=['SignatureExpired']).SignatureExpired()):
            self.assertEqual(self.submit().data["error"]["code"],"confirmation_expired")
        self.client.delete_customer.assert_not_called()

    def test_old_card_only_confirmation_cannot_delete_guest(self):
        from django.core import signing
        self.prepare()
        payload = signing.loads(self.token, salt="iiko-card-review")
        payload.pop("replacementMode")
        self.token = signing.dumps(payload, salt="iiko-card-review")
        self.assertEqual(self.submit().data["error"]["code"], "confirmation_changed")
        self.client.delete_customer.assert_not_called()

    def test_changed_topup_amount_invalidates_deletion_confirmation(self):
        self.prepare()
        self.assertEqual(self.submit(topupAmount="500").data["error"]["code"], "confirmation_changed")
        self.client.delete_customer.assert_not_called()
        self.client.topup_wallet.assert_not_called()

    def test_deleted_guest_with_occupied_number_does_not_create(self):
        self.prepare()
        self.client.delete_customer.side_effect = lambda *args: self.old.update(isDeleted=True)
        result = self.submit().data
        self.assertEqual(result["status"], "needs_review")
        self.assertEqual(result["stage"], "verify_removal")
        self.client.create_customer.assert_not_called()

    def test_uncertain_removal_never_creates_or_retries(self):
        self.prepare();self.client.delete_customer.side_effect=IikoError("network_unavailable")
        result=self.submit().data
        self.assertEqual(result["status"],"needs_review")
        self.assertEqual(result["stage"],"delete_customer")
        self.assertIsNone(result["customerId"])
        self.client.create_customer.assert_not_called()
        self.assertEqual(self.submit().data,result)
        self.client.delete_customer.assert_called_once()

    def test_unconfirmed_removal_never_creates(self):
        self.prepare();self.client.delete_customer.side_effect=lambda *args: None
        result=self.submit().data
        self.assertEqual(result["stage"],"verify_removal")
        self.assertEqual(result["status"],"needs_review")
        self.client.create_customer.assert_not_called()

    def test_failure_after_removal_is_explicit_partial_state(self):
        self.prepare();self.client.create_customer.side_effect=IikoError("write_not_confirmed",status=500)
        result=self.submit().data
        self.assertEqual(result["status"],"needs_review")
        self.assertEqual(result["previousCustomerId"],OLD)
        self.assertEqual([card["id"] for card in self.old["cards"]],[])
        self.submit();self.client.delete_customer.assert_called_once();self.client.create_customer.assert_called_once()

    def test_running_reservation_cannot_be_superseded(self):
        self.previous.status="needs_review";self.previous.save()
        self.prepare();self.assertEqual(self.submit().status_code,409)
        self.client.delete_customer.assert_not_called()

    def test_normalized_name_index_is_scoped_and_has_no_plain_names(self):
        observe("other",PILOT_ORGANIZATION,self.old)
        self.data.update(cardNumber="free",surname="Иванов",name="Иван")
        self.assertEqual(self.prepare()["duplicates"],[])
        self.assertNotIn("Иван", str(list(KnownGuest.objects.values())))
        self.assertEqual(name_digest({"surname":"  СЕМЁНОВ  ","name":"ИВАН"}),name_digest({"surname":"семенов","name":"иван","patronymic":"Другое"}))
