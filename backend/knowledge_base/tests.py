from datetime import date

from django.core.files.uploadedfile import SimpleUploadedFile
from rest_framework.test import APITestCase

from accounts.models import Role, User, UserRole
from employees.models import Employee, EmployeeFacility
from organizations.models import Cluster, Company, Department, Facility, Region
from .models import (KnowledgeCategory, KnowledgeMaterial, MaterialAccessRule,
                     MaterialAcknowledgmentAssignment, MaterialFavorite,
                     MaterialVersion, MaterialView)


class KnowledgeBaseApiTests(APITestCase):
    def setUp(self):
        self.company = Company.objects.create(name="Компания", short_name="Тест")
        self.region = Region.objects.create(company=self.company, name="Сибирь")
        self.cluster = Cluster.objects.create(region=self.region, name="Кластер")
        self.facility = Facility.objects.create(cluster=self.cluster, name="Объект", facility_type=Facility.Type.OFFICE, address="Адрес")
        self.department = Department.objects.create(company=self.company, name="ИТ")
        self.manager = User.objects.create_user(username="manager", email="manager@example.com", password="Pass12345!")
        self.worker = User.objects.create_user(username="worker", email="worker@example.com", password="Pass12345!")
        self.outsider = User.objects.create_user(username="other", email="other@example.com", password="Pass12345!")
        manager_role = Role.objects.create(code=Role.Code.MANAGER, name="Руководитель")
        employee_role = Role.objects.create(code=Role.Code.EMPLOYEE, name="Сотрудник")
        UserRole.objects.create(user=self.manager, role=manager_role, company=self.company)
        UserRole.objects.create(user=self.worker, role=employee_role, company=self.company)
        self.worker_employee = Employee.objects.create(user=self.worker, company=self.company, department=self.department, employee_number="E-1", position="Инженер", hire_date=date(2024, 1, 1))
        self.outsider_employee = Employee.objects.create(user=self.outsider, company=self.company, department=self.department, employee_number="E-2", position="Бухгалтер", hire_date=date(2024, 1, 1))
        EmployeeFacility.objects.create(employee=self.worker_employee, facility=self.facility, is_primary=True)
        self.category = KnowledgeCategory.objects.create(name="Регламенты", slug="regulations")

    def authenticate(self, user):
        self.client.force_authenticate(user)

    def create_material(self, title="Температурный регламент"):
        return KnowledgeMaterial.objects.create(title=title, slug=title.lower().replace(" ", "-"), material_type=KnowledgeMaterial.Type.REGULATION, category=self.category, owner=self.manager)

    def publish(self, material, reack=False):
        self.authenticate(self.manager)
        return self.client.post(f"/api/v1/knowledge/materials/{material.id}/versions/", {"content": "Порядок действий при отклонении температуры", "requires_reacknowledgment": reack}, format="json")

    def test_manager_creates_material_and_employee_cannot(self):
        self.authenticate(self.manager)
        response = self.client.post("/api/v1/knowledge/materials/", {"title": "Инструкция", "slug": "instruction", "description": "Описание", "material_type": "INSTRUCTION", "category": self.category.id})
        self.assertEqual(response.status_code, 201)
        self.authenticate(self.worker)
        denied = self.client.post("/api/v1/knowledge/materials/", {"title": "X", "slug": "x", "material_type": "PDF", "category": self.category.id})
        self.assertEqual(denied.status_code, 403)

    def test_publish_switches_current_version_and_reassigns_acknowledgment(self):
        material = self.create_material()
        first = self.publish(material)
        self.assertEqual(first.status_code, 201)
        v1 = MaterialVersion.objects.get(pk=first.data["id"])
        MaterialAcknowledgmentAssignment.objects.create(version=v1, employee=self.worker_employee, assigned_by=self.manager)
        second = self.publish(material, reack=True)
        self.assertEqual(second.status_code, 201)
        v1.refresh_from_db(); material.refresh_from_db()
        self.assertFalse(v1.is_current)
        self.assertEqual(material.current_version_id, second.data["id"])
        self.assertTrue(MaterialAcknowledgmentAssignment.objects.filter(version_id=second.data["id"], employee=self.worker_employee).exists())

    def test_access_rule_filters_materials(self):
        material = self.create_material(); self.publish(material)
        MaterialAccessRule.objects.create(material=material, position="Инженер", access_level=MaterialAccessRule.Level.VIEW)
        self.authenticate(self.worker)
        self.assertEqual(self.client.get("/api/v1/knowledge/materials/").data["count"], 1)
        self.authenticate(self.outsider)
        self.assertEqual(self.client.get("/api/v1/knowledge/materials/").data["count"], 0)

    def test_search_favorite_and_view_tracking(self):
        material = self.create_material(); self.publish(material)
        self.authenticate(self.worker)
        self.assertEqual(self.client.get("/api/v1/knowledge/materials/?search=температур").data["count"], 1)
        self.assertEqual(self.client.post(f"/api/v1/knowledge/materials/{material.id}/favorite/").data["is_favorite"], True)
        self.client.get(f"/api/v1/knowledge/materials/{material.id}/")
        self.client.get(f"/api/v1/knowledge/materials/{material.id}/")
        self.assertTrue(MaterialFavorite.objects.filter(material=material, employee=self.worker_employee).exists())
        self.assertEqual(MaterialView.objects.get(material=material, employee=self.worker_employee).view_count, 2)

    def test_acknowledgment_is_fixed_to_version(self):
        material = self.create_material(); response = self.publish(material)
        assignment = MaterialAcknowledgmentAssignment.objects.create(version_id=response.data["id"], employee=self.worker_employee, assigned_by=self.manager)
        self.authenticate(self.worker)
        result = self.client.post(f"/api/v1/knowledge/materials/{material.id}/acknowledge/")
        self.assertEqual(result.status_code, 200)
        assignment.refresh_from_db()
        self.assertEqual(assignment.status, MaterialAcknowledgmentAssignment.Status.ACKNOWLEDGED)
        self.assertEqual(assignment.version_id, response.data["id"])

    def test_protected_download_checks_access(self):
        material = self.create_material()
        self.authenticate(self.manager)
        uploaded = SimpleUploadedFile("rules.pdf", b"%PDF test", content_type="application/pdf")
        response = self.client.post(f"/api/v1/knowledge/materials/{material.id}/versions/", {"file": uploaded}, format="multipart")
        version_id = response.data["id"]
        MaterialAccessRule.objects.create(material=material, employee=self.worker_employee, access_level=MaterialAccessRule.Level.DOWNLOAD)
        self.authenticate(self.worker)
        self.assertEqual(self.client.get(f"/api/v1/knowledge/materials/{material.id}/versions/{version_id}/download/").status_code, 200)
        self.authenticate(self.outsider)
        self.assertEqual(self.client.get(f"/api/v1/knowledge/materials/{material.id}/versions/{version_id}/download/").status_code, 404)
