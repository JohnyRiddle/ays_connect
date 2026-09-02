from concurrent.futures import ThreadPoolExecutor
from datetime import timedelta
from unittest.mock import patch

from django.contrib.auth import get_user_model
from django.core.exceptions import ValidationError
from django.db import IntegrityError, close_old_connections, connection, connections, transaction
from django.test import TestCase, TransactionTestCase
from django.utils import timezone
from rest_framework.test import APIClient

from audit.models import AuditEvent
from events.models import OutboxEvent
from organizations.models import LegalEntity, OrgUnit
from organizations.services import OrgUnitService
from access_control.models import EmployeeRole, Permission, Role, RolePermission, Scope
from .assignment import AssignmentResolver, AssignmentTargetUnresolved
from .models import AssignmentTarget, Employee, FunctionalGroup, FunctionalGroupMembership, Team, TeamMembership
from .services import EmployeeService
from .teams import TeamConflict, TeamMembershipService, TeamService


class TeamDomainTests(TestCase):
    def setUp(self):
        self.user=get_user_model().objects.create_superuser(username="team-admin",email="team-admin@example.test",password="x")
        self.employee=Employee.objects.create(first_name="Иван")
    def team(self,active=True,**data):
        team=TeamService.create(actor_user=self.user,name=data.pop("name","Команда"),**data)
        return TeamService.transition(team=team,target=Team.Status.ACTIVE,expected_version=team.version,actor_user=self.user) if active else team
    def test_number_lifecycle_and_optimistic_lock(self):
        first=self.team(False); second=self.team(False,name="Вторая")
        self.assertRegex(first.code,r"^TEAM-\d{6}$"); self.assertNotEqual(first.code,second.code)
        active=TeamService.transition(team=first,target="active",expected_version=1,actor_user=self.user)
        with self.assertRaises(TeamConflict): TeamService.update(team=active,expected_version=1,actor_user=self.user,name="Старая версия")
        suspended=TeamService.transition(team=active,target="suspended",expected_version=2,actor_user=self.user)
        closed=TeamService.transition(team=suspended,target="closed",expected_version=3,actor_user=self.user)
        self.assertFalse(closed.is_assignable)
        with self.assertRaises(ValidationError): TeamService.transition(team=closed,target="active",expected_version=4)
    def test_cycle_and_org_unit_cycle(self):
        root=self.team(False); child=self.team(False,parent_team=root,name="Child")
        with self.assertRaises(ValidationError): TeamService.move(team=root,parent=child,expected_version=1)
        a=OrgUnit.objects.create(name="A"); b=OrgUnit.objects.create(name="B",parent=a)
        with self.assertRaises(ValidationError): OrgUnitService.move(unit=a,parent=b)
    def test_membership_history_role_and_as_of(self):
        team=self.team(); member=TeamMembershipService.add(team=team,employee=self.employee,actor_user=self.user,role="member")
        same=TeamMembershipService.add(team=team,employee=self.employee,actor_user=self.user,role="member")
        self.assertEqual(member.pk,same.pk)
        changed=TeamMembershipService.change_role(membership=member,role="deputy",actor_user=self.user)
        self.assertEqual(TeamMembership.objects.filter(team=team,employee=self.employee).count(),2)
        self.assertEqual(list(TeamMembershipService.as_of(team).values_list("role",flat=True)),["deputy"])
        TeamMembershipService.end(membership=changed,actor_user=self.user)
    def test_lead_must_be_member_and_resolver_preserves_functional_group(self):
        team=self.team()
        with self.assertRaises(ValidationError): TeamService.assign_leadership(team=team,employee=self.employee,field="lead_employee",expected_version=team.version)
        TeamMembershipService.add(team=team,employee=self.employee)
        team=TeamService.assign_leadership(team=team,employee=self.employee,field="lead_employee",expected_version=team.version)
        target=AssignmentTarget.objects.create(target_type="team",team=team,strategy="team_lead")
        self.assertEqual(AssignmentResolver.resolve(target),[self.employee])
        group=FunctionalGroup.objects.create(name="Legacy"); FunctionalGroupMembership.objects.create(group=group,employee=self.employee)
        legacy=AssignmentTarget.objects.create(target_type="functional_group",functional_group=group)
        self.assertEqual(AssignmentResolver.resolve(legacy),[self.employee])
    def test_termination_ends_membership_and_vacates_leadership_without_reactivation(self):
        team=self.team(); membership=TeamMembershipService.add(team=team,employee=self.employee)
        team=TeamService.assign_leadership(team=team,employee=self.employee,field="lead_employee",expected_version=team.version)
        EmployeeService.terminate(employee=self.employee,actor_user=self.user); membership.refresh_from_db(); team.refresh_from_db()
        self.assertIsNotNone(membership.valid_to); self.assertIsNone(team.lead_employee)
        EmployeeService.reactivate(employee=self.employee); self.assertFalse(TeamMembership.objects.filter(employee=self.employee,valid_to__isnull=True).exists())
    def test_api_idor_shape_preview_and_audit_outbox(self):
        client=APIClient();client.force_authenticate(self.user)
        created=client.post("/api/internal/v1/teams/",{"name":"API"},format="json");self.assertEqual(created.status_code,201,created.data)
        team=Team.objects.get(pk=created.data["id"]); activated=client.post(f"/api/internal/v1/teams/{team.pk}/activate/",{"version":team.version},format="json");self.assertEqual(activated.status_code,200)
        added=client.post(f"/api/internal/v1/teams/{team.pk}/members/",{"employee":str(self.employee.pk),"role":"member"},format="json");self.assertEqual(added.status_code,201,added.data)
        preview=client.post(f"/api/internal/v1/teams/{team.pk}/resolve/",{"strategy":"all_active_members"},format="json");self.assertTrue(preview.data["assignable"])
        self.assertTrue(AuditEvent.objects.filter(entity_id=str(team.pk)).exists());self.assertTrue(OutboxEvent.objects.filter(entity_id=str(team.pk)).exists())
        self.assertEqual(client.get("/api/internal/v1/teams/00000000-0000-0000-0000-000000000000/").status_code,404)
    def test_audit_failure_rolls_back(self):
        with patch("employees.teams.AuditService.record",side_effect=RuntimeError("audit")),self.assertRaises(RuntimeError): TeamService.create(name="Rollback")
        self.assertFalse(Team.objects.filter(name="Rollback").exists())
    def test_scoped_list_and_detail_prevent_idor(self):
        own=LegalEntity.objects.create(name="Own"); foreign=LegalEntity.objects.create(name="Foreign")
        actor_user=get_user_model().objects.create_user(username="scoped",email="scoped@example.test")
        actor=Employee.objects.create(first_name="Scoped",user=actor_user,legal_entity=own)
        permission=Permission.objects.create(code="people.team.view",name="View teams"); role=Role.objects.create(code="team-view",name="Team view")
        RolePermission.objects.create(role=role,permission=permission,scope=Scope.LEGAL_ENTITY); EmployeeRole.objects.create(employee=actor,role=role,legal_entity=own)
        own_team=TeamService.create(name="Own team",legal_entity=own); foreign_team=TeamService.create(name="Foreign team",legal_entity=foreign)
        client=APIClient();client.force_authenticate(actor_user); response=client.get("/api/internal/v1/teams/")
        self.assertEqual([x["id"] for x in response.data["results"]],[str(own_team.pk)])
        self.assertEqual(client.get(f"/api/internal/v1/teams/{foreign_team.pk}/").status_code,404)

    def test_patch_cannot_bypass_lifecycle_hierarchy_or_leadership(self):
        team=self.team(False); parent=self.team(False,name="Parent")
        client=APIClient(); client.force_authenticate(self.user)
        response=client.patch(f"/api/internal/v1/teams/{team.pk}/",{
            "version":team.version,"status":"active","parent_team":str(parent.pk),
            "lead_employee":str(self.employee.pk),"is_assignable":False,"name":"Renamed",
        },format="json")
        self.assertEqual(response.status_code,200,response.data)
        team.refresh_from_db()
        self.assertEqual(team.name,"Renamed"); self.assertEqual(team.status,Team.Status.DRAFT)
        self.assertIsNone(team.parent_team_id); self.assertIsNone(team.lead_employee_id); self.assertTrue(team.is_assignable)

    def test_historical_membership_overlap_and_ended_role_change_are_rejected(self):
        now=timezone.now(); team=self.team(valid_from=now-timedelta(days=20))
        old=TeamMembershipService.add(team=team,employee=self.employee,valid_from=now-timedelta(days=10),valid_to=now-timedelta(days=5))
        with self.assertRaises(TeamConflict):
            TeamMembershipService.add(team=team,employee=self.employee,valid_from=now-timedelta(days=7),valid_to=now-timedelta(days=3))
        with self.assertRaises(TeamConflict): TeamMembershipService.change_role(membership=old,role=TeamMembership.Role.DEPUTY)

    def test_database_exclusion_constraint_blocks_direct_overlap(self):
        team=self.team(); now=timezone.now()
        TeamMembership.objects.create(team=team,employee=self.employee,valid_from=now-timedelta(days=4),valid_to=now-timedelta(days=2))
        with self.assertRaises(IntegrityError), transaction.atomic():
            TeamMembership.objects.create(team=team,employee=self.employee,valid_from=now-timedelta(days=3),valid_to=now-timedelta(days=1))

    def test_team_resolver_validates_strategy_and_resolves_owner_without_membership(self):
        owner=Employee.objects.create(first_name="Owner"); team=self.team()
        team=TeamService.assign_leadership(team=team,employee=owner,field="owner_employee",expected_version=team.version)
        owner_target=AssignmentTarget(target_type="team",team=team,strategy="team_owner")
        self.assertEqual(AssignmentResolver.resolve_team(owner_target)[0],[owner])
        invalid=AssignmentTarget(target_type="team",team=team,strategy="unknown")
        with self.assertRaises(AssignmentTargetUnresolved): AssignmentResolver.resolve_team(invalid)

    def test_granular_permissions_separate_view_create_and_membership_access(self):
        actor_user=get_user_model().objects.create_user(username="team-reader",email="reader@example.test")
        actor=Employee.objects.create(first_name="Reader",user=actor_user)
        role=Role.objects.create(code="team-reader",name="Team reader")
        view=Permission.objects.create(code="people.team.view",name="View teams")
        RolePermission.objects.create(role=role,permission=view,scope=Scope.GLOBAL)
        EmployeeRole.objects.create(employee=actor,role=role)
        team=self.team(); client=APIClient(); client.force_authenticate(actor_user)
        detail=client.get(f"/api/internal/v1/teams/{team.pk}/")
        self.assertEqual(detail.status_code,200); self.assertEqual(detail.data["available_actions"],[])
        self.assertEqual(client.post("/api/internal/v1/teams/",{"name":"Forbidden"},format="json").status_code,403)
        self.assertEqual(client.get(f"/api/internal/v1/teams/{team.pk}/members/").status_code,403)


class TeamPostgreSQLConcurrencyTests(TransactionTestCase):
    reset_sequences=True
    def setUp(self):
        if connection.vendor!="postgresql": self.skipTest("PostgreSQL concurrency gate")
        self.employee=Employee.objects.create(first_name="Concurrent"); self.team=TeamService.create(name="Concurrent"); self.team=TeamService.transition(team=self.team,target="active",expected_version=1)
    @staticmethod
    def _run(fn,*args,**kwargs):
        close_old_connections()
        try:
            try: return fn(*args,**kwargs)
            except (ValidationError,TeamConflict,IntegrityError): return "conflict"
        finally: connections.close_all()
    def test_parallel_team_numbers(self):
        with ThreadPoolExecutor(max_workers=8) as pool: values=list(pool.map(lambda i:self._run(lambda:TeamService.create(name=f"T{i}").code),range(16)))
        self.assertEqual(len(values),len(set(values)))
    def test_parallel_add_is_single(self):
        with ThreadPoolExecutor(max_workers=2) as pool: list(pool.map(lambda _:self._run(TeamMembershipService.add,team=self.team,employee=self.employee),range(2)))
        self.assertEqual(TeamMembership.objects.filter(team=self.team,employee=self.employee,valid_to__isnull=True).count(),1)
    def test_close_vs_add_leaves_no_open_member(self):
        def close(): return TeamService.transition(team=self.team,target="closed",expected_version=2)
        def add(): return TeamMembershipService.add(team=self.team,employee=self.employee)
        with ThreadPoolExecutor(max_workers=2) as pool: list(pool.map(lambda f:self._run(f),[close,add]))
        self.assertFalse(TeamMembership.objects.filter(team=self.team,valid_to__isnull=True).exists())
    def test_parallel_lead_assignment_has_one_winner(self):
        people=[Employee.objects.create(first_name=f"Lead{i}") for i in range(2)]
        for person in people: TeamMembershipService.add(team=self.team,employee=person)
        version=self.team.version
        with ThreadPoolExecutor(max_workers=2) as pool: results=list(pool.map(lambda person:self._run(TeamService.assign_leadership,team=self.team,employee=person,field="lead_employee",expected_version=version),people))
        self.assertEqual(sum(isinstance(x,Team) for x in results),1)
    def test_parallel_role_change_keeps_one_open_period(self):
        membership=TeamMembershipService.add(team=self.team,employee=self.employee)
        with ThreadPoolExecutor(max_workers=2) as pool: list(pool.map(lambda role:self._run(TeamMembershipService.change_role,membership=membership,role=role),["deputy","coordinator"]))
        self.assertEqual(TeamMembership.objects.filter(team=self.team,employee=self.employee,valid_to__isnull=True).count(),1)
    def test_parallel_end_is_idempotent(self):
        membership=TeamMembershipService.add(team=self.team,employee=self.employee)
        with ThreadPoolExecutor(max_workers=2) as pool: list(pool.map(lambda _:self._run(TeamMembershipService.end,membership=membership),range(2)))
        self.assertFalse(TeamMembership.objects.filter(pk=membership.pk,valid_to__isnull=True).exists())
    def test_termination_vs_add_has_no_open_member(self):
        with ThreadPoolExecutor(max_workers=2) as pool: list(pool.map(lambda fn:self._run(fn),[lambda:EmployeeService.terminate(employee=self.employee),lambda:TeamMembershipService.add(team=self.team,employee=self.employee)]))
        self.assertFalse(TeamMembership.objects.filter(team=self.team,employee=self.employee,valid_to__isnull=True).exists())
    def test_parallel_cycle_move_is_rejected(self):
        other=TeamService.create(name="Other"); version_a=self.team.version; version_b=other.version
        with ThreadPoolExecutor(max_workers=2) as pool: list(pool.map(lambda item:self._run(TeamService.move,team=item[0],parent=item[1],expected_version=item[2]),[(self.team,other,version_a),(other,self.team,version_b)]))
        self.team.refresh_from_db();other.refresh_from_db()
        self.assertFalse(self.team.parent_team_id==other.pk and other.parent_team_id==self.team.pk)
    def test_parallel_optimistic_update_has_one_winner(self):
        version=self.team.version
        with ThreadPoolExecutor(max_workers=2) as pool: results=list(pool.map(lambda name:self._run(TeamService.update,team=self.team,expected_version=version,name=name),["A","B"]))
        self.assertEqual(sum(isinstance(x,Team) for x in results),1)
    def test_outbox_failure_rolls_back(self):
        with patch("employees.teams.DomainEventService.publish",side_effect=RuntimeError("outbox")),self.assertRaises(RuntimeError): TeamService.create(name="Outbox rollback")
        self.assertFalse(Team.objects.filter(name="Outbox rollback").exists())
