from django.contrib.auth import get_user_model
from django.db import IntegrityError, transaction
from django.test import TestCase
from django.test import TransactionTestCase
from concurrent.futures import ThreadPoolExecutor
from threading import Barrier
from datetime import timedelta
import uuid
from django.db import close_old_connections, connections
from django.utils import timezone
from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import override_settings
from tempfile import TemporaryDirectory
from rest_framework.test import APIClient

from access_control.models import EmployeeRole, Permission, Role, RolePermission
from employees.models import Employee
from work_tasks.models import Task, TaskTemplate
from employees.models import AssignmentTarget
from organizations.models import OrgUnit
from work_tasks.services import TaskService
from work_tasks.exceptions import TaskValidationError
from audit.models import AuditEvent
from events.models import OutboxEvent

from .models import Project, ProjectComment, ProjectCreateRequest, ProjectMember, ProjectMilestone, ProjectMilestoneDueNotice, ProjectMilestoneHistory, ProjectStage, ProjectTaskLink, ProjectTaskLinkHistory
from .services import ProjectBusinessError, ProjectService, ProjectTaskService
from .collaboration import ProjectCollaborationService
from .management.commands.process_milestone_due import process_due_milestones


class ProjectsCoreTests(TestCase):
    def setUp(self):
        self.media=TemporaryDirectory()
        self.addCleanup(self.media.cleanup)
        self.media_settings=override_settings(MEDIA_ROOT=self.media.name)
        self.media_settings.enable()
        self.addCleanup(self.media_settings.disable)
        self.user=get_user_model().objects.create_user(username="project-manager",email="project-manager@example.test")
        self.actor=Employee.objects.create(user=self.user,first_name="Synthetic manager")
        role=Role.objects.create(code="synthetic-project-manager",name="Synthetic project manager")
        for code in ("project.view","project.create","project.edit","project.members_manage","project.structure_manage",
                     "project.task_link_manage","project.lifecycle","project.comment","project.attachment_add",
                     "project.attachment_delete","task.view","task.edit","task.create","task.reopen","task_template.use"):
            permission=Permission.objects.create(code=code,name=code)
            RolePermission.objects.create(role=role,permission=permission,scope="global")
        EmployeeRole.objects.create(employee=self.actor,role=role)
        self.project=ProjectService.create(actor=self.actor,actor_user=self.user,name="Synthetic project",manager=self.actor)
        self.task=Task.objects.create(number="TASK-PROJECT-SYNTHETIC",title="Synthetic linked task",author=self.actor,
                                      created_by=self.user,updated_by=self.user)

    def test_stage_and_milestone_edit_preserve_version_and_history(self):
        client=APIClient();client.force_authenticate(self.user)
        stage=ProjectService.create_stage(project=self.project,actor=self.actor,actor_user=self.user,
                                          version=self.project.version,name="Initial stage")
        self.project.refresh_from_db()
        response=client.patch(f"/api/internal/v1/projects/{self.project.pk}/stages/{stage.pk}/",
                              {"version":self.project.version,"name":"Edited stage"},format="json")
        self.assertEqual(response.status_code,200,response.data)
        self.project.refresh_from_db();stage.refresh_from_db()
        self.assertEqual(stage.name,"Edited stage")
        self.assertEqual(client.patch(f"/api/internal/v1/projects/{self.project.pk}/stages/{stage.pk}/",
                                      {"version":self.project.version-1,"name":"Stale"},format="json").status_code,409)
        milestone=ProjectService.create_milestone(project=self.project,actor=self.actor,actor_user=self.user,
                                                  version=self.project.version,name="Initial point",stage=stage)
        self.project.refresh_from_db()
        response=client.patch(f"/api/internal/v1/projects/{self.project.pk}/milestones/{milestone.pk}/",
                              {"version":self.project.version,"name":"Edited point","required":True},format="json")
        self.assertEqual(response.status_code,200,response.data)
        milestone.refresh_from_db();self.project.refresh_from_db()
        self.assertEqual((milestone.name,milestone.required),("Edited point",True))
        self.assertEqual(AuditEvent.objects.filter(action="project.stage_edited").count(),1)
        self.assertEqual(AuditEvent.objects.filter(action="project.milestone_edited").count(),1)
        self.assertEqual(OutboxEvent.objects.filter(event_type="project.milestone_edited").count(),1)
        ProjectService.milestone_action(milestone=milestone,actor=self.actor,actor_user=self.user,
                                        project_version=self.project.version,action="confirm")
        self.project.refresh_from_db()
        response=client.patch(f"/api/internal/v1/projects/{self.project.pk}/milestones/{milestone.pk}/",
                              {"version":self.project.version,"name":"Forbidden"},format="json")
        self.assertEqual(response.status_code,400,response.data)

    def test_stage_and_milestone_creation_reject_unavailable_responsible_and_bad_dates(self):
        unavailable_user=get_user_model().objects.create_user(username="project-unavailable",email="project-unavailable@example.test")
        unavailable=Employee.objects.create(user=unavailable_user,first_name="Unavailable",status=Employee.Status.SUSPENDED)
        original_version=self.project.version
        audit_count=AuditEvent.objects.count();outbox_count=OutboxEvent.objects.count()
        with self.assertRaises(ProjectBusinessError):
            ProjectService.create_stage(project=self.project,actor=self.actor,actor_user=self.user,
                version=original_version,name="Bad owner",responsible=unavailable)
        self.project.refresh_from_db()
        self.assertEqual(self.project.version,original_version)
        self.assertFalse(ProjectStage.objects.filter(project=self.project,name="Bad owner").exists())
        with self.assertRaises(ProjectBusinessError):
            ProjectService.create_stage(project=self.project,actor=self.actor,actor_user=self.user,
                version=original_version,name="Bad dates",planned_start_at=timezone.now(),
                planned_end_at=timezone.now()-timedelta(days=1))
        self.project.refresh_from_db()
        self.assertEqual(self.project.version,original_version)
        with self.assertRaises(ProjectBusinessError):
            ProjectService.create_milestone(project=self.project,actor=self.actor,actor_user=self.user,
                version=original_version,name="Bad milestone owner",responsible=unavailable)
        self.project.refresh_from_db()
        self.assertEqual(self.project.version,original_version)
        self.assertFalse(ProjectMilestone.objects.filter(project=self.project,name="Bad milestone owner").exists())
        self.assertEqual(AuditEvent.objects.count(),audit_count)
        self.assertEqual(OutboxEvent.objects.count(),outbox_count)

    def test_all_project_commands_reject_unknown_write_fields(self):
        client=APIClient();client.force_authenticate(self.user)
        response=client.post(f"/api/internal/v1/projects/{self.project.pk}/start/",
                             {"version":self.project.version,"unexpected":"ignored before review"},format="json")
        self.assertEqual(response.status_code,400,response.data)
        self.project.refresh_from_db()
        self.assertEqual(self.project.status,"draft")
        response=client.post(f"/api/internal/v1/projects/{self.project.pk}/comments/",
                             {"body":"Must not be created","unexpected":True},format="json")
        self.assertEqual(response.status_code,400,response.data)
        self.assertFalse(ProjectComment.objects.filter(project=self.project,body="Must not be created").exists())

    def test_one_work_task_is_linked_and_completion_waits_for_acceptance(self):
        stage=ProjectService.create_stage(project=self.project,actor=self.actor,actor_user=self.user,
                                          version=self.project.version,name="Первый этап")
        self.project.refresh_from_db()
        ProjectTaskService.link(project=self.project,task=self.task,actor=self.actor,actor_user=self.user,
                                project_version=self.project.version,task_version=self.task.version,stage=stage)
        self.project.refresh_from_db()
        self.assertEqual(ProjectTaskLink.objects.filter(task=self.task).count(),1)
        self.assertEqual(ProjectTaskLink.objects.get(task=self.task).project_id,self.project.pk)
        with self.assertRaises(ProjectBusinessError):
            ProjectTaskService.link(project=self.project,task=self.task,actor=self.actor,actor_user=self.user,
                                    project_version=self.project.version,task_version=self.task.version)
        self.project=ProjectService.transition(project=self.project,actor=self.actor,actor_user=self.user,
                                               version=self.project.version,action="start")
        with self.assertRaises(ProjectBusinessError) as blocked:
            ProjectService.transition(project=self.project,actor=self.actor,actor_user=self.user,
                                      version=self.project.version,action="complete")
        self.assertEqual(blocked.exception.code,"project_tasks_incomplete")
        self.task.status="review";self.task.save(update_fields=["status"])
        with self.assertRaises(ProjectBusinessError):
            ProjectService.transition(project=self.project,actor=self.actor,actor_user=self.user,
                                      version=self.project.version,action="complete")
        self.task.status="completed";self.task.completed_at=timezone.now();self.task.save(update_fields=["status","completed_at"])
        final=ProjectService.transition(project=self.project,actor=self.actor,actor_user=self.user,
                                        version=self.project.version,action="complete")
        self.assertEqual(final.status,"completed")

    def test_stage_from_another_project_rejected_by_service_and_postgres(self):
        other=ProjectService.create(actor=self.actor,actor_user=self.user,name="Other")
        stage=ProjectService.create_stage(project=other,actor=self.actor,actor_user=self.user,version=other.version,name="Wrong")
        with self.assertRaises(ProjectBusinessError) as result:
            ProjectTaskService.link(project=self.project,task=self.task,actor=self.actor,actor_user=self.user,
                                    project_version=self.project.version,task_version=self.task.version,stage=stage)
        self.assertEqual(result.exception.code,"project_stage_mismatch")
        with self.assertRaises(IntegrityError):
            with transaction.atomic():
                ProjectTaskLink.objects.create(project=self.project,stage=stage,task=self.task,linked_by=self.user)
        self.assertFalse(ProjectTaskLink.objects.filter(task=self.task).exists())

    def test_project_visibility_does_not_expose_closed_task_in_aggregate(self):
        outsider_user=get_user_model().objects.create_user(username="project-outsider",email="project-outsider@example.test")
        outsider=Employee.objects.create(user=outsider_user,first_name="Synthetic outsider")
        role=Role.objects.create(code="synthetic-project-reader",name="Synthetic reader")
        RolePermission.objects.create(role=role,permission=Permission.objects.get(code="project.view"),scope="global")
        RolePermission.objects.create(role=role,permission=Permission.objects.get(code="task.view"),scope="own")
        EmployeeRole.objects.create(employee=outsider,role=role)
        ProjectTaskService.link(project=self.project,task=self.task,actor=self.actor,actor_user=self.user,
                                project_version=self.project.version,task_version=self.task.version)
        client=APIClient();client.force_authenticate(user=outsider_user)
        response=client.get(f"/api/internal/v1/projects/{self.project.pk}/counters/")
        self.assertEqual(response.status_code,200)
        self.assertEqual(response.data["available"],0)
        self.assertEqual(response.data["label"],"Нет задач")
        self.assertEqual(response.data["by_responsible"],[])
        self.assertEqual(client.get(f"/api/internal/v1/projects/{self.project.pk}/tasks/").data["count"],0)
        history=client.get(f"/api/internal/v1/projects/{self.project.pk}/history/").data
        self.assertEqual(history["links"],[])
        self.assertNotIn(str(self.task.pk),str(history))

    def test_edit_manager_and_archive_are_versioned_and_audited(self):
        other_user=get_user_model().objects.create_user(username="synthetic-new-manager",email="synthetic-new-manager@example.test")
        other=Employee.objects.create(user=other_user,first_name="Synthetic new manager")
        client=APIClient();client.force_authenticate(user=self.user)
        response=client.patch(f"/api/internal/v1/projects/{self.project.pk}/",
            {"version":self.project.version,"manager":str(other.pk),"goal":"Synthetic result"},format="json")
        self.assertEqual(response.status_code,200,response.data)
        self.project.refresh_from_db()
        self.assertEqual(self.project.manager_id,other.pk)
        self.assertEqual(ProjectMember.objects.get(project=self.project,employee=self.actor).left_at is not None,True)
        self.assertEqual(ProjectMember.objects.get(project=self.project,employee=other).role,"manager")
        self.assertEqual(AuditEvent.objects.filter(action="project.edited").count(),1)
        self.assertEqual(OutboxEvent.objects.filter(event_type="project.edited").count(),1)
        self.assertEqual(client.patch(f"/api/internal/v1/projects/{self.project.pk}/",
            {"version":1,"goal":"Stale"},format="json").status_code,409)
        self.project=ProjectService.transition(project=self.project,actor=self.actor,actor_user=self.user,
            version=self.project.version,action="start")
        self.project=ProjectService.transition(project=self.project,actor=self.actor,actor_user=self.user,
            version=self.project.version,action="complete")
        archived=ProjectService.archive(project=self.project,actor=self.actor,actor_user=self.user,
            version=self.project.version,archive=True,reason="Synthetic archive")
        self.assertTrue(archived.is_archived)
        with self.assertRaises(ProjectBusinessError):
            ProjectService.transition(project=archived,actor=self.actor,actor_user=self.user,
                version=archived.version,action="reopen",reason="Blocked")
        unarchived=ProjectService.archive(project=archived,actor=self.actor,actor_user=self.user,
            version=archived.version,archive=False,reason="Synthetic return")
        self.assertFalse(unarchived.is_archived)

    def test_create_http_retry_reuses_project_and_work_task_without_duplicate_events(self):
        client=APIClient();client.force_authenticate(user=self.user)
        key=str(uuid.uuid4())
        url="/api/internal/v1/projects/"
        first=client.post(url,{"name":"Idempotent synthetic"},format="json",HTTP_IDEMPOTENCY_KEY=key)
        self.assertEqual(first.status_code,201,first.data)
        projects=Project.objects.count();events=OutboxEvent.objects.count()
        repeat=client.post(url,{"name":"Idempotent synthetic"},format="json",HTTP_IDEMPOTENCY_KEY=key)
        self.assertEqual(repeat.status_code,200,repeat.data)
        self.assertEqual(first.data["id"],repeat.data["id"])
        self.assertEqual(Project.objects.count(),projects)
        self.assertEqual(OutboxEvent.objects.count(),events)
        changed=client.post(url,{"name":"Changed"},format="json",HTTP_IDEMPOTENCY_KEY=key)
        self.assertEqual(changed.status_code,409)
        task_url=f"/api/internal/v1/projects/{self.project.pk}/create-task/"
        task_key=str(uuid.uuid4());payload={"project_version":self.project.version,"title":"Synthetic inside"}
        one=client.post(task_url,payload,format="json",HTTP_IDEMPOTENCY_KEY=task_key)
        self.assertEqual(one.status_code,201,one.data)
        tasks=Task.objects.count();events=OutboxEvent.objects.count()
        two=client.post(task_url,payload,format="json",HTTP_IDEMPOTENCY_KEY=task_key)
        self.assertEqual(two.status_code,200,two.data)
        self.assertEqual(one.data["id"],two.data["id"])
        self.assertEqual(Task.objects.count(),tasks)
        self.assertEqual(OutboxEvent.objects.count(),events)
        self.assertEqual(ProjectCreateRequest.objects.filter(actor=self.user).count(),2)

    def test_project_api_rejects_mass_assignment_and_preserves_state(self):
        client=APIClient();client.force_authenticate(user=self.user)
        original=self.project.status
        response=client.patch(f"/api/internal/v1/projects/{self.project.pk}/",
            {"version":self.project.version,"status":"completed"},format="json")
        self.assertEqual(response.status_code,400)
        self.project.refresh_from_db();self.assertEqual(self.project.status,original)
        response=client.post("/api/internal/v1/projects/",{"name":"Synthetic injection","is_archived":True},
            format="json",HTTP_IDEMPOTENCY_KEY=str(uuid.uuid4()))
        self.assertEqual(response.status_code,400)
        self.assertFalse(Project.objects.filter(name="Synthetic injection").exists())

    def test_project_number_cannot_change_through_bulk_orm_path(self):
        original=self.project.number
        with self.assertRaises(IntegrityError):
            with transaction.atomic():
                Project.objects.filter(pk=self.project.pk).update(number="PRJ-BYPASS")
        self.project.refresh_from_db()
        self.assertEqual(self.project.number,original)

    def test_org_unit_scope_and_observer_membership_do_not_grant_management(self):
        first_unit=OrgUnit.objects.create(name="Synthetic first unit")
        second_unit=OrgUnit.objects.create(name="Synthetic second unit")
        scoped=ProjectService.create(actor=self.actor,actor_user=self.user,name="Scoped project",
            manager=self.actor,org_unit=first_unit)
        outside_user=get_user_model().objects.create_user(username="synthetic-scope-outside",email="scope-outside@example.test")
        outside=Employee.objects.create(user=outside_user,first_name="Synthetic outsider",org_unit=second_unit)
        role=Role.objects.create(code="synthetic-scope-reader",name="Synthetic unit reader")
        RolePermission.objects.create(role=role,permission=Permission.objects.get(code="project.view"),scope="org_unit")
        EmployeeRole.objects.create(employee=outside,role=role)
        client=APIClient();client.force_authenticate(user=outside_user)
        self.assertEqual(client.get(f"/api/internal/v1/projects/{scoped.pk}/").status_code,404)
        outside.org_unit=first_unit;outside.save(update_fields=["org_unit"])
        self.assertEqual(client.get(f"/api/internal/v1/projects/{scoped.pk}/").status_code,200)
        observer=ProjectService.add_member(project=scoped,actor=self.actor,actor_user=self.user,
            version=scoped.version,employee=outside,role="observer")
        self.assertEqual(observer.role,"observer")
        scoped.refresh_from_db()
        response=client.post(f"/api/internal/v1/projects/{scoped.pk}/stages/",
            {"version":scoped.version,"name":"Forbidden"},format="json")
        self.assertEqual(response.status_code,403)
        self.assertFalse(ProjectStage.objects.filter(project=scoped,name="Forbidden").exists())

    def test_remove_member_and_stage_delete_guard_with_rollback(self):
        user=get_user_model().objects.create_user(username="synthetic-member",email="synthetic-member@example.test")
        employee=Employee.objects.create(user=user,first_name="Synthetic member")
        member=ProjectService.add_member(project=self.project,actor=self.actor,actor_user=self.user,
            version=self.project.version,employee=employee)
        self.project.refresh_from_db()
        ProjectService.remove_member(project=self.project,member=member,actor=self.actor,actor_user=self.user,
            version=self.project.version)
        member.refresh_from_db();self.assertIsNotNone(member.left_at)
        self.project.refresh_from_db()
        stage=ProjectService.create_stage(project=self.project,actor=self.actor,actor_user=self.user,
            version=self.project.version,name="Synthetic stage")
        self.project.refresh_from_db()
        ProjectTaskService.link(project=self.project,task=self.task,actor=self.actor,actor_user=self.user,
            project_version=self.project.version,task_version=self.task.version,stage=stage)
        self.project.refresh_from_db()
        audits=AuditEvent.objects.count();events=OutboxEvent.objects.count()
        with self.assertRaises(ProjectBusinessError) as error:
            ProjectService.delete_stage(project=self.project,stage=stage,actor=self.actor,actor_user=self.user,
                version=self.project.version)
        self.assertEqual(error.exception.code,"project_stage_not_empty")
        self.assertEqual(AuditEvent.objects.count(),audits)
        self.assertEqual(OutboxEvent.objects.count(),events)
        self.assertTrue(ProjectStage.objects.filter(pk=stage.pk).exists())

    def test_promoting_existing_member_preserves_membership_role_history(self):
        user=get_user_model().objects.create_user(username="synthetic-promotion",email="promotion@example.test")
        employee=Employee.objects.create(user=user,first_name="Synthetic promotion")
        old=ProjectService.add_member(project=self.project,actor=self.actor,actor_user=self.user,
            version=self.project.version,employee=employee)
        self.project.refresh_from_db()
        ProjectService.edit(project=self.project,actor=self.actor,actor_user=self.user,
            version=self.project.version,changes={"manager":employee})
        old.refresh_from_db()
        self.assertEqual(old.role,"member")
        self.assertIsNotNone(old.left_at)
        self.assertEqual(ProjectMember.objects.filter(project=self.project,employee=employee,left_at__isnull=True,
            role="manager").count(),1)

    def test_work_reopen_atomically_reactivates_completed_project(self):
        self.task.status="completed";self.task.completed_at=timezone.now();self.task.save(update_fields=["status","completed_at"])
        ProjectTaskService.link(project=self.project,task=self.task,actor=self.actor,actor_user=self.user,
                                project_version=self.project.version,task_version=self.task.version)
        self.project.refresh_from_db()
        self.project=ProjectService.transition(project=self.project,actor=self.actor,actor_user=self.user,
                                               version=self.project.version,action="start")
        self.project=ProjectService.transition(project=self.project,actor=self.actor,actor_user=self.user,
                                               version=self.project.version,action="complete")
        old_end=self.project.actual_end_at
        task=TaskService.reopen(task=self.task,actor=self.actor,actor_user=self.user,version=self.task.version,reason="Synthetic return")
        self.project.refresh_from_db()
        self.assertEqual(task.status,"in_progress")
        self.assertIsNone(task.completed_at)
        self.assertEqual(self.project.status,"active")
        self.assertIsNone(self.project.actual_end_at)
        self.assertEqual(AuditEvent.objects.filter(action="project.reopened_by_task").count(),1)
        self.assertEqual(OutboxEvent.objects.filter(event_type="notification.requested",payload__reason="PROJECT_TASK_REOPENED").count(),1)
        self.assertTrue(old_end)

    def test_archived_project_blocks_work_reopen_without_mutating_task(self):
        self.task.status="completed";self.task.completed_at=timezone.now();self.task.save(update_fields=["status","completed_at"])
        ProjectTaskService.link(project=self.project,task=self.task,actor=self.actor,actor_user=self.user,
                                project_version=self.project.version,task_version=self.task.version)
        Project.objects.filter(pk=self.project.pk).update(is_archived=True)
        with self.assertRaises(TaskValidationError) as error:
            TaskService.reopen(task=self.task,actor=self.actor,actor_user=self.user,version=self.task.version,reason="Synthetic return")
        self.assertEqual(error.exception.code,"task_project_reopen_blocked")
        self.task.refresh_from_db();self.assertEqual(self.task.status,"completed")

    def test_create_inside_project_and_template_keep_one_work_task(self):
        direct=ProjectTaskService.create_task(project=self.project,actor=self.actor,actor_user=self.user,
            project_version=self.project.version,task_data={"title":"Inside project"})
        self.project.refresh_from_db()
        self.assertEqual(direct.project_link.project_id,self.project.pk)
        target=AssignmentTarget.objects.create(target_type="employee",employee=self.actor)
        template=TaskTemplate.objects.create(name="Project template",task_title="From template",
            responsible_target=target,created_by=self.actor)
        generated=ProjectTaskService.create_task(project=self.project,actor=self.actor,actor_user=self.user,
            project_version=self.project.version,template=template)
        self.assertEqual(generated.source_template_id,template.pk)
        self.assertEqual(generated.project_link.project_id,self.project.pk)
        self.assertEqual(Task.objects.filter(pk__in=[direct.pk,generated.pk]).count(),2)

    def test_create_rollback_does_not_leave_unlinked_work_task_or_events(self):
        self.project=ProjectService.transition(project=self.project,actor=self.actor,actor_user=self.user,
            version=self.project.version,action="start")
        self.project=ProjectService.transition(project=self.project,actor=self.actor,actor_user=self.user,
            version=self.project.version,action="complete")
        tasks_before=Task.objects.count();audits_before=AuditEvent.objects.count();events_before=OutboxEvent.objects.count()
        with self.assertRaises(ProjectBusinessError):
            ProjectTaskService.create_task(project=self.project,actor=self.actor,actor_user=self.user,
                project_version=self.project.version,task_data={"title":"Must rollback"})
        self.assertEqual(Task.objects.count(),tasks_before)
        self.assertEqual(AuditEvent.objects.count(),audits_before)
        self.assertEqual(OutboxEvent.objects.count(),events_before)

    def test_move_stage_unlink_and_relink_preserve_work_and_link_history(self):
        first=ProjectService.create_stage(project=self.project,actor=self.actor,actor_user=self.user,
            version=self.project.version,name="First")
        self.project.refresh_from_db()
        second=ProjectService.create_stage(project=self.project,actor=self.actor,actor_user=self.user,
            version=self.project.version,name="Second")
        self.project.refresh_from_db()
        ProjectTaskService.link(project=self.project,task=self.task,actor=self.actor,actor_user=self.user,
            project_version=self.project.version,task_version=self.task.version,stage=first)
        self.project.refresh_from_db()
        ProjectTaskService.move_stage(task=self.task,stage=second,actor=self.actor,actor_user=self.user,
            task_version=self.task.version,project_version=self.project.version)
        self.project.refresh_from_db()
        ProjectTaskService.unlink(task=self.task,actor=self.actor,actor_user=self.user,
            task_version=self.task.version,project_version=self.project.version,reason="Synthetic unlink")
        self.project.refresh_from_db()
        self.assertEqual(Task.objects.filter(pk=self.task.pk).count(),1)
        self.assertFalse(ProjectTaskLink.objects.get(task=self.task).is_active)
        ProjectTaskService.link(project=self.project,task=self.task,actor=self.actor,actor_user=self.user,
            project_version=self.project.version,task_version=self.task.version)
        self.assertEqual(ProjectTaskLinkHistory.objects.filter(task=self.task).count(),4)
        self.assertEqual(ProjectTaskLinkHistory.objects.filter(task=self.task).values_list("action",flat=True).count(),4)
        self.assertEqual(ProjectTaskLink.objects.get(task=self.task).stage_id,None)

    def test_explicit_move_between_projects_keeps_same_work_task(self):
        target=ProjectService.create(actor=self.actor,actor_user=self.user,name="Target project",manager=self.actor)
        stage=ProjectService.create_stage(project=target,actor=self.actor,actor_user=self.user,
            version=target.version,name="Target stage")
        target.refresh_from_db()
        ProjectTaskService.link(project=self.project,task=self.task,actor=self.actor,actor_user=self.user,
            project_version=self.project.version,task_version=self.task.version)
        self.project.refresh_from_db()
        moved=ProjectTaskService.move_project(task=self.task,target_project=target,target_stage=stage,
            actor=self.actor,actor_user=self.user,task_version=self.task.version,
            source_version=self.project.version,target_version=target.version,reason="Synthetic transfer")
        self.assertEqual(moved.project_id,target.pk)
        self.assertEqual(moved.stage_id,stage.pk)
        self.assertEqual(Task.objects.filter(pk=self.task.pk).count(),1)
        history=ProjectTaskLinkHistory.objects.get(task=self.task,action="project")
        self.assertEqual(history.old_project_id,self.project.pk)
        self.assertEqual(history.new_project_id,target.pk)

    def test_required_milestone_blocks_completion_until_confirmed(self):
        milestone=ProjectService.create_milestone(project=self.project,actor=self.actor,actor_user=self.user,
            version=self.project.version,name="Контрольная точка",required=True,responsible=self.actor)
        self.project.refresh_from_db()
        self.project=ProjectService.transition(project=self.project,actor=self.actor,actor_user=self.user,
            version=self.project.version,action="start")
        with self.assertRaises(ProjectBusinessError) as result:
            ProjectService.transition(project=self.project,actor=self.actor,actor_user=self.user,
                version=self.project.version,action="complete")
        self.assertEqual(result.exception.code,"project_milestones_incomplete")
        ProjectService.milestone_action(milestone=milestone,actor=self.actor,actor_user=self.user,
            project_version=self.project.version,action="confirm",comment="Synthetic criteria met")
        self.project.refresh_from_db()
        self.assertEqual(ProjectMilestoneHistory.objects.filter(milestone=milestone).count(),1)
        ProjectService.milestone_action(milestone=milestone,actor=self.actor,actor_user=self.user,
            project_version=self.project.version,action="reopen",comment="Synthetic review")
        self.project.refresh_from_db()
        self.assertEqual(ProjectMilestoneHistory.objects.filter(milestone=milestone).count(),2)
        with self.assertRaises(ProjectBusinessError):
            ProjectService.transition(project=self.project,actor=self.actor,actor_user=self.user,
                version=self.project.version,action="complete")
        ProjectService.milestone_action(milestone=milestone,actor=self.actor,actor_user=self.user,
            project_version=self.project.version,action="confirm",comment="Synthetic criteria met")
        self.project.refresh_from_db()
        completed=ProjectService.transition(project=self.project,actor=self.actor,actor_user=self.user,
            version=self.project.version,action="complete")
        self.assertEqual(completed.status,"completed")

    def test_due_milestone_worker_is_idempotent_with_notification_core(self):
        from notifications.services import ingest_event
        from notifications.models import Notification
        milestone=ProjectService.create_milestone(project=self.project,actor=self.actor,actor_user=self.user,
            version=self.project.version,name="Synthetic due",responsible=self.actor,due_at=timezone.now()-timedelta(minutes=1))
        self.assertEqual(process_due_milestones(),1)
        self.assertEqual(process_due_milestones(),0)
        self.assertEqual(ProjectMilestoneDueNotice.objects.filter(milestone=milestone).count(),1)
        source=OutboxEvent.objects.get(event_type="notification.requested",payload__reason="PROJECT_MILESTONE_DUE")
        ingest_event(source);ingest_event(source)
        self.assertEqual(Notification.objects.filter(recipient=self.user,entity_type="Project",entity_id=str(self.project.pk),
            intent__reason="PROJECT_MILESTONE_DUE").count(),1)

    def test_milestone_stage_must_belong_to_its_project_in_sql(self):
        other=ProjectService.create(actor=self.actor,actor_user=self.user,name="Other")
        stage=ProjectService.create_stage(project=other,actor=self.actor,actor_user=self.user,
            version=other.version,name="Other stage")
        with self.assertRaises(ProjectBusinessError):
            ProjectService.create_milestone(project=self.project,actor=self.actor,actor_user=self.user,
                version=self.project.version,name="Wrong",stage=stage)
        with self.assertRaises(IntegrityError):
            with transaction.atomic():
                ProjectMilestone.objects.create(project=self.project,stage=stage,name="SQL wrong")

    def test_comment_and_protected_attachment_follow_current_project_access(self):
        comment=ProjectCollaborationService.comment(project=self.project,actor=self.actor,actor_user=self.user,
            body="Synthetic discussion")
        self.assertEqual(comment.project_id,self.project.pk)
        uploaded=SimpleUploadedFile("synthetic.txt",b"Synthetic file",content_type="text/plain")
        item=ProjectCollaborationService.add_attachment(project=self.project,actor=self.actor,actor_user=self.user,
            uploaded_file=uploaded)
        self.assertEqual(item.file.open("rb").read(),b"Synthetic file")
        client=APIClient();client.force_authenticate(user=self.user)
        url=f"/api/internal/v1/projects/{self.project.pk}/attachments/{item.pk}/download/"
        self.assertEqual(client.get(url).status_code,200)
        RolePermission.objects.filter(role__code="synthetic-project-manager",permission__code="project.view").delete()
        self.assertEqual(client.get(url).status_code,404)

    def test_project_mention_notification_is_hidden_and_suppressed_after_access_revocation(self):
        from notifications.services import ingest_event,process_deliveries
        from notifications.models import Notification,NotificationDeliveryAttempt
        user=get_user_model().objects.create_user(username="synthetic-mention",email="synthetic-mention@example.test")
        mentioned=Employee.objects.create(user=user,first_name="Mentioned")
        role=Role.objects.create(code="synthetic-mention-role",name="Mention project")
        grant=RolePermission.objects.create(role=role,permission=Permission.objects.get(code="project.view"),scope="global")
        EmployeeRole.objects.create(employee=mentioned,role=role)
        ProjectCollaborationService.comment(project=self.project,actor=self.actor,actor_user=self.user,
            body="Synthetic mention",mentions=[mentioned])
        source=OutboxEvent.objects.get(event_type="notification.requested",payload__reason="PROJECT_COMMENT_MENTIONED")
        ingest_event(source);ingest_event(source)
        self.assertEqual(Notification.objects.filter(recipient=user,entity_type="Project").count(),1)
        grant.delete()
        client=APIClient();client.force_authenticate(user=user)
        self.assertEqual(client.get("/api/v1/notifications/unread-count/").data["count"],0)
        self.assertEqual(client.get("/api/v1/notifications/").data["count"],0)
        process_deliveries()
        self.assertEqual(NotificationDeliveryAttempt.objects.filter(delivery__notification__recipient=user).count(),0)


class ProjectsConcurrencyTests(TransactionTestCase):
    def setUp(self):
        self.user=get_user_model().objects.create_superuser(username="synthetic-project-concurrency",email="concurrency@example.test",password="synthetic-only")
        self.actor=Employee.objects.create(user=self.user,first_name="Synthetic concurrent actor")
        self.first=ProjectService.create(actor=self.actor,actor_user=self.user,name="Concurrent first",manager=self.actor)
        self.second=ProjectService.create(actor=self.actor,actor_user=self.user,name="Concurrent second",manager=self.actor)
        self.task=Task.objects.create(number="TASK-CONCURRENT-PRJ",title="Concurrent Work task",author=self.actor,created_by=self.user,updated_by=self.user)

    def _race(self, callbacks):
        barrier=Barrier(2)
        def run(callback):
            close_old_connections()
            try:
                barrier.wait(timeout=10)
                try: return callback()
                except ProjectBusinessError as error: return error.code
            finally:
                connections.close_all()
        with ThreadPoolExecutor(max_workers=2) as pool:
            return list(pool.map(run,callbacks))

    def test_parallel_links_keep_exactly_one_project(self):
        def link(project):
            return ProjectTaskService.link(project=project,task=self.task,actor=self.actor,actor_user=self.user,
                project_version=project.version,task_version=self.task.version).project_id
        results=self._race([lambda:link(self.first),lambda:link(self.second)])
        self.assertEqual(ProjectTaskLink.objects.filter(task=self.task,is_active=True).count(),1)
        self.assertEqual(ProjectTaskLinkHistory.objects.filter(task=self.task,action="link").count(),1)
        self.assertIn("project_task_already_linked",results)

    def test_complete_and_link_do_not_leave_completed_project_with_open_task(self):
        first=ProjectService.transition(project=self.first,actor=self.actor,actor_user=self.user,
            version=self.first.version,action="start")
        def complete():
            return ProjectService.transition(project=first,actor=self.actor,actor_user=self.user,
                version=first.version,action="complete").status
        def link():
            return ProjectTaskService.link(project=first,task=self.task,actor=self.actor,actor_user=self.user,
                project_version=first.version,task_version=self.task.version).project_id
        self._race([complete,link])
        first.refresh_from_db()
        linked=ProjectTaskLink.objects.filter(task=self.task,project=first,is_active=True).exists()
        self.assertFalse(first.status=="completed" and linked)
        if linked:self.assertEqual(first.status,"active")

    def test_stage_delete_and_link_never_leave_crossed_reference(self):
        stage=ProjectService.create_stage(project=self.first,actor=self.actor,actor_user=self.user,
            version=self.first.version,name="Concurrent stage")
        self.first.refresh_from_db()
        def delete():
            return ProjectService.delete_stage(project=self.first,stage=stage,actor=self.actor,actor_user=self.user,
                version=self.first.version).version
        def link():
            return ProjectTaskService.link(project=self.first,task=self.task,actor=self.actor,actor_user=self.user,
                project_version=self.first.version,task_version=self.task.version,stage=stage).stage_id
        self._race([delete,link])
        linked=ProjectTaskLink.objects.filter(task=self.task,is_active=True).first()
        if linked:
            self.assertEqual(linked.stage_id,stage.pk)
            self.assertTrue(ProjectStage.objects.filter(pk=stage.pk).exists())
        else:
            self.assertFalse(ProjectStage.objects.filter(pk=stage.pk).exists())

    def test_project_number_sequence_survives_parallel_creation(self):
        def create():
            return ProjectService.create(actor=self.actor,actor_user=self.user,
                name="Parallel numbered",manager=self.actor).number
        numbers=self._race([create,create])
        self.assertEqual(len(set(numbers)),2)
        self.assertTrue(all(number.startswith("PRJ-") for number in numbers))

    def test_task_reopen_and_project_complete_serialize_without_wrong_final_state(self):
        self.task.status="completed";self.task.completed_at=timezone.now()
        self.task.save(update_fields=["status","completed_at"])
        ProjectTaskService.link(project=self.first,task=self.task,actor=self.actor,actor_user=self.user,
            project_version=self.first.version,task_version=self.task.version)
        self.first.refresh_from_db()
        first=ProjectService.transition(project=self.first,actor=self.actor,actor_user=self.user,
            version=self.first.version,action="start")
        def complete():
            return ProjectService.transition(project=first,actor=self.actor,actor_user=self.user,
                version=first.version,action="complete").status
        def reopen():
            return TaskService.reopen(task=self.task,actor=self.actor,actor_user=self.user,
                version=self.task.version,reason="Concurrent return").status
        self._race([complete,reopen])
        first.refresh_from_db();self.task.refresh_from_db()
        self.assertEqual(first.status,"active")
        self.assertEqual(self.task.status,"in_progress")
        self.assertIsNone(first.actual_end_at)
        self.assertEqual(AuditEvent.objects.filter(action="project.reopened_by_task").count(),
            OutboxEvent.objects.filter(event_type="project.reopened_by_task").count())
