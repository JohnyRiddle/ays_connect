from django.test import TestCase
from rest_framework.test import APIClient
from accounts.models import User
from notifications.models import Notification
class NotificationTests(TestCase):
    def test_user_reads_only_own_notifications(self):
        user=User.objects.create_user(username="u",email="u@n.test",password="pass12345");other=User.objects.create_user(username="o",email="o@n.test",password="pass12345")
        item=Notification.objects.create(recipient=user,notification_type="system",title="Тест",message="Тест");Notification.objects.create(recipient=other,notification_type="system",title="Чужое",message="Чужое")
        client=APIClient();client.force_authenticate(user);response=client.get("/api/v1/notifications/");self.assertEqual(response.data["count"],1)
        response=client.post(f"/api/v1/notifications/{item.id}/read/");self.assertTrue(response.data["is_read"])
