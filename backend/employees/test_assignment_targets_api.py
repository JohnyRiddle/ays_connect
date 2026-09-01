from rest_framework.test import APITestCase

from accounts.models import User
from employees.models import AssignmentTarget, Employee


class AssignmentTargetLookupApiTests(APITestCase):
    def setUp(self):
        self.user = User.objects.create_superuser(username="target-admin", email="target-admin@example.test", password="pass")
        self.employee = Employee.objects.create(first_name="Иван", last_name="Исполнитель", employee_number="TARGET-1")
        self.target = AssignmentTarget.objects.create(target_type=AssignmentTarget.Type.EMPLOYEE, employee=self.employee)
        self.client.force_authenticate(self.user)

    def test_lookup_returns_canonical_id_type_and_display_name(self):
        response = self.client.get("/api/internal/v1/assignment-targets/?search=Исполнитель")
        self.assertEqual(response.status_code, 200)
        item = response.data["results"][0]
        self.assertEqual(item["id"], str(self.target.pk))
        self.assertEqual(item["target_type"], "employee")
        self.assertIn("Исполнитель", item["display_name"])

    def test_lookup_is_read_only(self):
        response = self.client.post("/api/internal/v1/assignment-targets/", {"target_type": "employee", "employee": str(self.employee.pk)})
        self.assertEqual(response.status_code, 405)
