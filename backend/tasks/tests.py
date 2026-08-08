from datetime import timedelta
from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import TestCase
from django.utils import timezone
from rest_framework.test import APIClient
from accounts.models import User
from tasks.models import RecurrenceRule, Task

class TaskLifecycleTests(TestCase):
    def setUp(self):
        self.creator=User.objects.create_user(username="manager",email="manager@test.local",password="pass12345")
        self.worker=User.objects.create_user(username="worker",email="worker@test.local",password="pass12345")
        self.other=User.objects.create_user(username="other",email="other@test.local",password="pass12345")
        deadline=timezone.now()+timedelta(days=1)
        self.task=Task.objects.create(title="Проверка",creator=self.creator,assignee=self.worker,status=Task.Status.ASSIGNED,initial_deadline=deadline,deadline=deadline,requires_comment=True)
        self.client=APIClient()
    def auth(self,user): self.client.force_authenticate(user)
    def test_assignee_can_complete_review_cycle(self):
        self.auth(self.worker)
        self.assertEqual(self.client.post(f"/api/v1/tasks/{self.task.id}/accept/").status_code,200)
        self.assertEqual(self.client.post(f"/api/v1/tasks/{self.task.id}/start/").status_code,200)
        response=self.client.post(f"/api/v1/tasks/{self.task.id}/submit/",{"result_text":"Готово"},format="json")
        self.assertEqual(response.data["status"],Task.Status.REVIEW)
        self.auth(self.creator)
        response=self.client.post(f"/api/v1/tasks/{self.task.id}/approve/")
        self.assertEqual(response.data["status"],Task.Status.CLOSED)
        self.assertEqual(self.task.history.count(),4)
    def test_unrelated_user_cannot_see_task(self):
        self.auth(self.other)
        self.assertEqual(self.client.get(f"/api/v1/tasks/{self.task.id}/").status_code,404)
    def test_result_comment_is_required(self):
        self.task.status=Task.Status.IN_PROGRESS; self.task.save()
        self.auth(self.worker)
        self.assertEqual(self.client.post(f"/api/v1/tasks/{self.task.id}/submit/",{"result_text":""},format="json").status_code,400)
    def test_participant_can_upload_and_download_attachment(self):
        self.auth(self.worker)
        uploaded=SimpleUploadedFile("report.txt",b"task result",content_type="text/plain")
        response=self.client.post(f"/api/v1/tasks/{self.task.id}/attachment/",{"file":uploaded},format="multipart")
        self.assertEqual(response.status_code,201)
        attachment_id=response.data["id"]
        response=self.client.get(f"/api/v1/tasks/{self.task.id}/attachments/{attachment_id}/download/")
        self.assertEqual(response.status_code,200)
        self.assertEqual(b"".join(response.streaming_content),b"task result")
    def test_created_task_is_assigned_even_if_client_sends_draft(self):
        self.auth(self.creator)
        response=self.client.post("/api/v1/tasks/",{
            "title":"Новая задача","assignee":self.worker.id,"deadline":(timezone.now()+timedelta(days=2)).isoformat(),"status":"draft"
        },format="json")
        self.assertEqual(response.status_code,201)
        self.assertEqual(Task.objects.get(title="Новая задача").status,Task.Status.ASSIGNED)
    def test_creator_can_configure_recurrence(self):
        self.auth(self.creator)
        response=self.client.post(f"/api/v1/tasks/{self.task.id}/recurrence/",{
            "frequency":"weekly","interval":2,"next_run_at":(timezone.now()+timedelta(days=1)).isoformat(),"is_active":True
        },format="json")
        self.assertEqual(response.status_code,200)
        self.assertTrue(RecurrenceRule.objects.filter(task_template=self.task,frequency="weekly",interval=2).exists())
