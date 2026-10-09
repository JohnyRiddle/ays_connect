import uuid

from django.db import connection, transaction
from django.utils import timezone

from audit.services import AuditService
from events.services import DomainEventService
from work_tasks.models import Task, TaskStatus
from work_tasks.policies import TaskAccessPolicy
from work_tasks.selectors import TaskSelector
from work_tasks.services import TaskService
from work_tasks.automation import TaskTemplateService

from .models import Project, ProjectMember, ProjectMilestone, ProjectMilestoneHistory, ProjectNumberSequence, ProjectStage, ProjectStatus, ProjectTaskLink, ProjectTaskLinkHistory
from .policies import ProjectAccessPolicy


class ProjectBusinessError(Exception):
    def __init__(self, message, code="project_invalid"):
        super().__init__(message)
        self.code = code


def project_lock(project_id):
    if connection.vendor == "postgresql":
        key = uuid.UUID(str(project_id)).int % (2 ** 63)
        with connection.cursor() as cursor:
            cursor.execute("SELECT pg_advisory_xact_lock(%s)", [key])


class ProjectService:
    @staticmethod
    def available_employee(employee):
        from employees.models import Employee
        return bool(employee and employee.is_active and employee.status not in {
            Employee.Status.ARCHIVED, Employee.Status.SUSPENDED, Employee.Status.DISMISSED, Employee.Status.TERMINATED})

    @staticmethod
    def authorize(actor, actor_user, permission, project=None):
        if actor_user and actor_user.is_superuser:
            return
        if not ProjectAccessPolicy.allows(actor, permission, project):
            raise ProjectBusinessError("Недостаточно прав для операции с проектом.", "project_permission_denied")

    @staticmethod
    def record(project, actor, actor_user, action, old=None, new=None, correlation_id=None):
        AuditService.record(action=action, entity=project, actor_user=actor_user, actor_employee=actor,
                            old_value=old, new_value=new, correlation_id=correlation_id)
        DomainEventService.publish(event_type=action, entity=project, actor=actor_user,
                                   payload={"project_id":str(project.pk), "version":project.version}, correlation_id=correlation_id)

    @staticmethod
    def notify(project, actor_user, recipients, reason, correlation_id=None, **payload):
        for employee_id in set(pk for pk in recipients if pk):
            DomainEventService.publish(event_type="notification.requested",entity=project,actor=actor_user,
                payload={"reason":reason,"recipient_employee_id":str(employee_id),"project_id":str(project.pk),
                         "project_number":project.number,**payload},correlation_id=correlation_id)

    @staticmethod
    def next_number():
        sequence, _ = ProjectNumberSequence.objects.select_for_update().get_or_create(key="project")
        sequence.value += 1
        sequence.save(update_fields=["value"])
        return f"PRJ-{sequence.value:06d}"

    @classmethod
    @transaction.atomic
    def create(cls, *, actor, actor_user, name, manager=None, correlation_id=None, **data):
        cls.authorize(actor, actor_user, "project.create")
        from organizations.object_services import require_available_location
        require_available_location(data.get("location"), actor_user)
        if not name.strip():
            raise ProjectBusinessError("Укажите название проекта.")
        if data.get("planned_start_at") and data.get("planned_end_at") and data["planned_start_at"] > data["planned_end_at"]:
            raise ProjectBusinessError("Плановая дата начала позже завершения.")
        if manager and not cls.available_employee(manager):
            raise ProjectBusinessError("Руководитель недоступен.")
        if data.get("customer") and not cls.available_employee(data["customer"]):
            raise ProjectBusinessError("Заказчик недоступен.")
        project = Project.objects.create(number=cls.next_number(), name=name.strip(), manager=manager,
                                         created_by=actor_user, updated_by=actor_user, **data)
        if manager:
            ProjectMember.objects.create(project=project, employee=manager, role=ProjectMember.Role.MANAGER, added_by=actor_user)
        cls.record(project, actor, actor_user, "project.created", new={"status":project.status}, correlation_id=correlation_id)
        return project

    @classmethod
    def locked(cls, project, version):
        project_lock(project.pk)
        current = Project.objects.select_for_update().get(pk=project.pk)
        if current.version != version:
            raise ProjectBusinessError("Версия проекта устарела.", "project_version_conflict")
        return current

    @classmethod
    @transaction.atomic
    def transition(cls, *, project, actor, actor_user, version, action, reason="", correlation_id=None):
        project = cls.locked(project, version)
        cls.authorize(actor, actor_user, "project.lifecycle", project)
        transitions = {
            "start": ({ProjectStatus.DRAFT, ProjectStatus.ON_HOLD}, ProjectStatus.ACTIVE),
            "hold": ({ProjectStatus.ACTIVE}, ProjectStatus.ON_HOLD),
            "complete": ({ProjectStatus.ACTIVE, ProjectStatus.ON_HOLD}, ProjectStatus.COMPLETED),
            "cancel": ({ProjectStatus.DRAFT, ProjectStatus.ACTIVE, ProjectStatus.ON_HOLD}, ProjectStatus.CANCELLED),
            "reopen": ({ProjectStatus.COMPLETED}, ProjectStatus.ACTIVE),
            "restore": ({ProjectStatus.CANCELLED}, ProjectStatus.DRAFT),
        }
        if action not in transitions or project.status not in transitions[action][0] or project.is_archived:
            raise ProjectBusinessError("Переход проекта недоступен.", "project_transition_invalid")
        if action in {"start", "reopen"} and not cls.available_employee(project.manager):
            raise ProjectBusinessError("Для запуска нужен руководитель проекта.")
        if action in {"cancel", "reopen", "restore"} and not reason.strip():
            raise ProjectBusinessError("Укажите причину перехода.")
        if action == "complete":
            if ProjectTaskLink.objects.filter(project=project, is_active=True).exclude(task__status__in=[TaskStatus.COMPLETED, TaskStatus.CANCELLED]).exists():
                raise ProjectBusinessError("Завершению мешают незавершённые задачи.", "project_tasks_incomplete")
            if ProjectMilestone.objects.filter(project=project, required=True, confirmed_at__isnull=True).exists():
                raise ProjectBusinessError("Обязательные контрольные точки не подтверждены.", "project_milestones_incomplete")
        old = project.status
        project.status = transitions[action][1]
        project.version += 1
        project.updated_by = actor_user
        fields = ["status", "version", "updated_by", "updated_at"]
        if action == "start":
            project.actual_start_at = project.actual_start_at or timezone.now(); fields.append("actual_start_at")
        if action == "complete":
            project.actual_end_at = timezone.now(); fields.append("actual_end_at")
        if action == "reopen":
            project.actual_end_at = None; fields.append("actual_end_at")
        project.save(update_fields=fields)
        cls.record(project, actor, actor_user, f"project.{action}", old={"status":old},
                   new={"status":project.status, "reason":reason[:500]}, correlation_id=correlation_id)
        cls.notify(project,actor_user,[project.manager_id],"PROJECT_LIFECYCLE",correlation_id,
                   lifecycle_action=action)
        return project

    @classmethod
    @transaction.atomic
    def edit(cls, *, project, actor, actor_user, version, changes, correlation_id=None):
        project = cls.locked(project, version)
        cls.authorize(actor, actor_user, "project.edit", project)
        if project.is_archived or project.status in {ProjectStatus.COMPLETED, ProjectStatus.CANCELLED}:
            raise ProjectBusinessError("Финальный проект нельзя редактировать обычной командой.")
        allowed = {"name", "description", "goal", "expected_result", "manager", "customer", "org_unit", "location", "planned_start_at", "planned_end_at"}
        from organizations.object_services import require_available_location
        if "location" in changes and changes["location"] != project.location:
            require_available_location(changes["location"], actor_user)
        if not changes or not set(changes) <= allowed:
            raise ProjectBusinessError("Укажите допустимые поля проекта.")
        if "name" in changes and not changes["name"].strip():
            raise ProjectBusinessError("Укажите название проекта.")
        start = changes.get("planned_start_at", project.planned_start_at)
        end = changes.get("planned_end_at", project.planned_end_at)
        if start and end and start > end:
            raise ProjectBusinessError("Плановая дата начала позже завершения.")
        old = {key: str(getattr(project, key)) for key in changes}
        old_manager = project.manager
        new_manager = changes.get("manager", old_manager)
        if project.status != ProjectStatus.DRAFT and not new_manager:
            raise ProjectBusinessError("Активному проекту нужен руководитель.")
        if new_manager and not cls.available_employee(new_manager):
            raise ProjectBusinessError("Руководитель недоступен.")
        if changes.get("customer") and not cls.available_employee(changes["customer"]):
            raise ProjectBusinessError("Заказчик недоступен.")
        for key, value in changes.items(): setattr(project, key, value)
        if new_manager != old_manager:
            if old_manager:
                ProjectMember.objects.filter(project=project, employee=old_manager, left_at__isnull=True).update(left_at=timezone.now(), removed_by=actor_user)
            if new_manager:
                existing = ProjectMember.objects.filter(project=project, employee=new_manager, left_at__isnull=True).first()
                if existing:
                    existing.left_at = timezone.now(); existing.removed_by = actor_user
                    existing.save(update_fields=["left_at", "removed_by"])
                ProjectMember.objects.create(project=project, employee=new_manager, role=ProjectMember.Role.MANAGER, added_by=actor_user)
        project.version += 1; project.updated_by = actor_user
        project.save(update_fields=[*changes.keys(), "version", "updated_by", "updated_at"])
        cls.record(project, actor, actor_user, "project.edited", old=old,
                   new={key: str(getattr(project, key)) for key in changes}, correlation_id=correlation_id)
        if new_manager != old_manager:
            cls.notify(project, actor_user, [project.manager_id], "PROJECT_MANAGER_CHANGED", correlation_id)
        return project

    @classmethod
    @transaction.atomic
    def archive(cls, *, project, actor, actor_user, version, archive, reason, correlation_id=None):
        project = cls.locked(project, version)
        cls.authorize(actor, actor_user, "project.lifecycle", project)
        if not reason.strip() or project.is_archived == archive:
            raise ProjectBusinessError("Нужна причина и изменение состояния архива.")
        if archive and project.status not in {ProjectStatus.COMPLETED, ProjectStatus.CANCELLED}:
            raise ProjectBusinessError("Архивировать можно только завершённый или отменённый проект.")
        project.is_archived = archive; project.version += 1; project.updated_by = actor_user
        project.save(update_fields=["is_archived", "version", "updated_by", "updated_at"])
        cls.record(project, actor, actor_user, "project.archived" if archive else "project.unarchived",
                   new={"reason": reason[:500], "is_archived": archive}, correlation_id=correlation_id)
        return project

    @classmethod
    @transaction.atomic
    def remove_member(cls, *, project, member, actor, actor_user, version, correlation_id=None):
        project = cls.locked(project, version)
        cls.authorize(actor, actor_user, "project.members_manage", project)
        if project.is_archived or project.status in {ProjectStatus.COMPLETED, ProjectStatus.CANCELLED}:
            raise ProjectBusinessError("Финальный проект нельзя менять.")
        member = ProjectMember.objects.select_for_update().get(pk=member.pk, project=project)
        if member.left_at or member.employee_id == project.manager_id:
            raise ProjectBusinessError("Руководителя нельзя удалить без смены руководителя.")
        member.left_at = timezone.now(); member.removed_by = actor_user
        member.save(update_fields=["left_at", "removed_by"])
        project.version += 1; project.updated_by = actor_user
        project.save(update_fields=["version", "updated_by", "updated_at"])
        cls.record(project, actor, actor_user, "project.member_removed",
                   new={"employee_id": str(member.employee_id)}, correlation_id=correlation_id)
        return member

    @classmethod
    @transaction.atomic
    def delete_stage(cls, *, project, stage, actor, actor_user, version, correlation_id=None):
        project = cls.locked(project, version)
        cls.authorize(actor, actor_user, "project.structure_manage", project)
        if project.is_archived or project.status in {ProjectStatus.COMPLETED, ProjectStatus.CANCELLED}:
            raise ProjectBusinessError("Финальный проект нельзя менять.")
        stage = ProjectStage.objects.select_for_update().get(pk=stage.pk, project=project)
        if ProjectTaskLink.objects.filter(stage=stage).exists() or ProjectMilestone.objects.filter(stage=stage).exists():
            raise ProjectBusinessError("Сначала перенесите или отвяжите задачи и контрольные точки этапа.", "project_stage_not_empty")
        stage_id = str(stage.pk); stage.delete()
        project.version += 1; project.updated_by = actor_user
        project.save(update_fields=["version", "updated_by", "updated_at"])
        cls.record(project, actor, actor_user, "project.stage_deleted", new={"stage_id": stage_id}, correlation_id=correlation_id)
        return project

    @classmethod
    @transaction.atomic
    def add_member(cls, *, project, actor, actor_user, version, employee, role=ProjectMember.Role.MEMBER, correlation_id=None):
        project = cls.locked(project, version)
        cls.authorize(actor, actor_user, "project.members_manage", project)
        if project.is_archived or project.status in {ProjectStatus.COMPLETED, ProjectStatus.CANCELLED}:
            raise ProjectBusinessError("Структуру финального проекта изменить нельзя.")
        if not cls.available_employee(employee) or role not in ProjectMember.Role.values:
            raise ProjectBusinessError("Недопустимый участник или роль.")
        if role == ProjectMember.Role.MANAGER and employee.pk != project.manager_id:
            raise ProjectBusinessError("Роль руководителя соответствует только руководителю проекта.")
        if ProjectMember.objects.filter(project=project, employee=employee, left_at__isnull=True).exists():
            raise ProjectBusinessError("Сотрудник уже участвует в проекте.", "project_member_exists")
        member = ProjectMember.objects.create(project=project, employee=employee, role=role, added_by=actor_user)
        project.version += 1;project.updated_by=actor_user;project.save(update_fields=["version","updated_by","updated_at"])
        cls.record(project, actor, actor_user, "project.member_added", new={"employee_id":str(employee.pk),"role":role}, correlation_id=correlation_id)
        cls.notify(project,actor_user,[employee.pk],"PROJECT_MEMBER_ADDED",correlation_id)
        return member

    @classmethod
    @transaction.atomic
    def create_stage(cls, *, project, actor, actor_user, version, name, correlation_id=None, **data):
        project = cls.locked(project, version)
        cls.authorize(actor, actor_user, "project.structure_manage", project)
        if project.is_archived or project.status in {ProjectStatus.COMPLETED, ProjectStatus.CANCELLED}:
            raise ProjectBusinessError("Структуру финального проекта изменить нельзя.")
        if not name.strip(): raise ProjectBusinessError("Укажите название этапа.")
        if data.get("planned_start_at") and data.get("planned_end_at") and data["planned_start_at"] > data["planned_end_at"]:
            raise ProjectBusinessError("Плановые даты этапа перепутаны.")
        if data.get("responsible") and not cls.available_employee(data["responsible"]):
            raise ProjectBusinessError("Ответственный этапа недоступен.")
        stage = ProjectStage.objects.create(project=project, name=name.strip(), **data)
        project.version += 1;project.updated_by=actor_user;project.save(update_fields=["version","updated_by","updated_at"])
        cls.record(project, actor, actor_user, "project.stage_created", new={"stage_id":str(stage.pk)}, correlation_id=correlation_id)
        return stage

    @classmethod
    @transaction.atomic
    def edit_stage(cls, *, project, stage, actor, actor_user, version, changes, correlation_id=None):
        project=cls.locked(project,version)
        cls.authorize(actor,actor_user,"project.structure_manage",project)
        if project.is_archived or project.status in {ProjectStatus.COMPLETED,ProjectStatus.CANCELLED}:
            raise ProjectBusinessError("Финальный проект нельзя менять.")
        allowed={"name","description","position","planned_start_at","planned_end_at","responsible"}
        if not changes or not set(changes)<=allowed:
            raise ProjectBusinessError("Укажите допустимые поля этапа.")
        stage=ProjectStage.objects.select_for_update().get(pk=stage.pk,project=project)
        if "name" in changes and not changes["name"].strip(): raise ProjectBusinessError("Укажите название этапа.")
        start=changes.get("planned_start_at",stage.planned_start_at)
        end=changes.get("planned_end_at",stage.planned_end_at)
        if start and end and start>end: raise ProjectBusinessError("Плановые даты этапа перепутаны.")
        if changes.get("responsible") and not cls.available_employee(changes["responsible"]):
            raise ProjectBusinessError("Ответственный этапа недоступен.")
        old={key:str(getattr(stage,key)) for key in changes}
        for key,value in changes.items(): setattr(stage,key,value)
        stage.save(update_fields=[*changes.keys(),"updated_at"])
        project.version+=1;project.updated_by=actor_user;project.save(update_fields=["version","updated_by","updated_at"])
        cls.record(project,actor,actor_user,"project.stage_edited",old={"stage_id":str(stage.pk),**old},
            new={"stage_id":str(stage.pk),**{key:str(getattr(stage,key)) for key in changes}},correlation_id=correlation_id)
        return stage

    @classmethod
    @transaction.atomic
    def create_milestone(cls, *, project, actor, actor_user, version, name, stage=None,
                         correlation_id=None, **data):
        project=cls.locked(project,version)
        cls.authorize(actor,actor_user,"project.structure_manage",project)
        if project.is_archived or project.status in {ProjectStatus.COMPLETED,ProjectStatus.CANCELLED}:
            raise ProjectBusinessError("Структуру финального проекта менять нельзя.")
        if stage and stage.project_id!=project.pk:
            raise ProjectBusinessError("Этап принадлежит другому проекту.","project_stage_mismatch")
        if not name.strip(): raise ProjectBusinessError("Укажите название контрольной точки.")
        if data.get("responsible") and not cls.available_employee(data["responsible"]):
            raise ProjectBusinessError("Ответственный точки недоступен.")
        milestone=ProjectMilestone.objects.create(project=project,stage=stage,name=name.strip(),created_by=actor_user,**data)
        project.version+=1;project.updated_by=actor_user;project.save(update_fields=["version","updated_by","updated_at"])
        cls.record(project,actor,actor_user,"project.milestone_created",new={"milestone_id":str(milestone.pk)},correlation_id=correlation_id)
        if milestone.responsible_id:
            cls.notify(project,actor_user,[milestone.responsible_id],"PROJECT_MILESTONE_ASSIGNED",correlation_id,
                       milestone_id=str(milestone.pk),milestone_name=milestone.name)
        return milestone

    @classmethod
    @transaction.atomic
    def edit_milestone(cls, *, project, milestone, actor, actor_user, version, changes, correlation_id=None):
        project=cls.locked(project,version)
        cls.authorize(actor,actor_user,"project.structure_manage",project)
        if project.is_archived or project.status in {ProjectStatus.COMPLETED,ProjectStatus.CANCELLED}:
            raise ProjectBusinessError("Финальный проект нельзя менять.")
        allowed={"name","stage","due_at","criterion","required","responsible"}
        if not changes or not set(changes)<=allowed: raise ProjectBusinessError("Укажите допустимые поля точки.")
        milestone=ProjectMilestone.objects.select_for_update().get(pk=milestone.pk,project=project)
        if milestone.confirmed_at: raise ProjectBusinessError("Сначала явно откройте подтверждённую точку повторно.")
        if "name" in changes and not changes["name"].strip(): raise ProjectBusinessError("Укажите название точки.")
        if "stage" in changes and changes["stage"] and changes["stage"].project_id!=project.pk:
            raise ProjectBusinessError("Этап принадлежит другому проекту.","project_stage_mismatch")
        if changes.get("responsible") and not cls.available_employee(changes["responsible"]):
            raise ProjectBusinessError("Ответственный точки недоступен.")
        old={key:str(getattr(milestone,key)) for key in changes}
        old_responsible=milestone.responsible_id
        for key,value in changes.items(): setattr(milestone,key,value)
        milestone.save(update_fields=[*changes.keys(),"updated_at"])
        project.version+=1;project.updated_by=actor_user;project.save(update_fields=["version","updated_by","updated_at"])
        cls.record(project,actor,actor_user,"project.milestone_edited",old={"milestone_id":str(milestone.pk),**old},
            new={"milestone_id":str(milestone.pk),**{key:str(getattr(milestone,key)) for key in changes}},correlation_id=correlation_id)
        if milestone.responsible_id!=old_responsible and milestone.responsible_id:
            cls.notify(project,actor_user,[milestone.responsible_id],"PROJECT_MILESTONE_ASSIGNED",correlation_id,
                milestone_id=str(milestone.pk),milestone_name=milestone.name)
        return milestone

    @classmethod
    @transaction.atomic
    def milestone_action(cls, *, milestone, actor, actor_user, project_version, action, comment="", correlation_id=None):
        project=cls.locked(milestone.project,project_version)
        cls.authorize(actor,actor_user,"project.structure_manage",project)
        milestone=ProjectMilestone.objects.select_for_update().get(pk=milestone.pk,project=project)
        if project.is_archived or project.status in {ProjectStatus.COMPLETED,ProjectStatus.CANCELLED}:
            raise ProjectBusinessError("Контрольную точку финального проекта менять нельзя.")
        if action=="confirm":
            if milestone.confirmed_at: raise ProjectBusinessError("Контрольная точка уже подтверждена.")
            milestone.confirmed_at=timezone.now();milestone.confirmed_by=actor
            milestone.confirmation_comment=comment
        elif action=="reopen":
            if not milestone.confirmed_at or not comment.strip():
                raise ProjectBusinessError("Для повторного открытия подтверждённой точки нужна причина.")
            milestone.confirmed_at=None;milestone.confirmed_by=None;milestone.confirmation_comment=""
        else: raise ProjectBusinessError("Неизвестное действие с контрольной точкой.")
        milestone.save(update_fields=["confirmed_at","confirmed_by","confirmation_comment","updated_at"])
        ProjectMilestoneHistory.objects.create(milestone=milestone,action=action,actor=actor,comment=comment)
        project.version+=1;project.updated_by=actor_user;project.save(update_fields=["version","updated_by","updated_at"])
        cls.record(project,actor,actor_user,f"project.milestone_{action}",new={"milestone_id":str(milestone.pk),"comment":comment[:500]},correlation_id=correlation_id)
        return milestone


class ProjectTaskService:
    @staticmethod
    def authorize_task(actor, actor_user, task):
        if actor_user and actor_user.is_superuser: return
        if not TaskSelector.visible_to(actor).filter(pk=task.pk).exists() or not TaskAccessPolicy.allows(employee=actor, permission="task.edit", task=task):
            raise ProjectBusinessError("Задача недоступна для привязки.", "project_task_forbidden")

    @staticmethod
    def validate_stage(project, stage):
        if stage and stage.project_id != project.pk:
            raise ProjectBusinessError("Этап принадлежит другому проекту.", "project_stage_mismatch")

    @classmethod
    @transaction.atomic
    def link(cls, *, project, task, actor, actor_user, project_version, task_version, stage=None, correlation_id=None):
        project_lock(project.pk)
        task = Task.objects.select_for_update().get(pk=task.pk)
        if task.version != task_version:
            raise ProjectBusinessError("Версия задачи устарела.", "task_version_conflict")
        project = Project.objects.select_for_update().get(pk=project.pk)
        if project.version != project_version:
            raise ProjectBusinessError("Версия проекта устарела.", "project_version_conflict")
        ProjectService.authorize(actor, actor_user, "project.task_link_manage", project)
        cls.authorize_task(actor, actor_user, task)
        cls.validate_stage(project, stage)
        if project.is_archived or project.status in {ProjectStatus.COMPLETED, ProjectStatus.CANCELLED}:
            raise ProjectBusinessError("В финальный проект задачу привязать нельзя.")
        existing = ProjectTaskLink.objects.select_for_update().filter(task=task).first()
        if existing and existing.is_active:
            raise ProjectBusinessError("Задача уже связана с проектом.", "project_task_already_linked")
        old_project = existing.project if existing else None
        old_stage = existing.stage if existing else None
        if existing:
            link = existing
            link.project=project;link.stage=stage;link.is_active=True;link.unlinked_at=None;link.version+=1
            link.linked_by=actor_user
            link.save(update_fields=["project","stage","is_active","unlinked_at","version","linked_by","updated_at"])
        else:
            link = ProjectTaskLink.objects.create(project=project, stage=stage, task=task, linked_by=actor_user)
        ProjectTaskLinkHistory.objects.create(task=task,action=ProjectTaskLinkHistory.Action.LINK,
            old_project=old_project,old_stage=old_stage,new_project=project,new_stage=stage,actor=actor_user)
        project.version += 1;project.updated_by=actor_user;project.save(update_fields=["version","updated_by","updated_at"])
        AuditService.record(action="project.task_linked", entity=link, actor_user=actor_user, actor_employee=actor,
                            new_value={"project_id":str(project.pk),"task_id":str(task.pk),"stage_id":str(stage.pk) if stage else None}, correlation_id=correlation_id)
        DomainEventService.publish(event_type="project.task_linked", entity=link, actor=actor_user,
                                   payload={"project_id":str(project.pk),"task_id":str(task.pk)}, correlation_id=correlation_id)
        return link

    @classmethod
    @transaction.atomic
    def unlink(cls, *, task, actor, actor_user, task_version, project_version, reason="", correlation_id=None):
        project_id = ProjectTaskLink.objects.filter(task=task,is_active=True).values_list("project_id",flat=True).first()
        if not project_id: raise ProjectBusinessError("Задача не связана с проектом.")
        project_lock(project_id)
        task = Task.objects.select_for_update().get(pk=task.pk)
        if task.version != task_version: raise ProjectBusinessError("Версия задачи устарела.","task_version_conflict")
        link = ProjectTaskLink.objects.select_for_update().get(task=task,is_active=True)
        project = Project.objects.select_for_update().get(pk=link.project_id)
        if project.version != project_version: raise ProjectBusinessError("Версия проекта устарела.","project_version_conflict")
        ProjectService.authorize(actor,actor_user,"project.task_link_manage",project)
        cls.authorize_task(actor,actor_user,task)
        if project.is_archived or project.status in {ProjectStatus.COMPLETED,ProjectStatus.CANCELLED}:
            raise ProjectBusinessError("Связь финального проекта нельзя менять обычной командой.")
        old_stage=link.stage
        link.is_active=False;link.unlinked_at=timezone.now();link.version+=1
        link.save(update_fields=["is_active","unlinked_at","version","updated_at"])
        ProjectTaskLinkHistory.objects.create(task=task,action=ProjectTaskLinkHistory.Action.UNLINK,
            old_project=project,old_stage=old_stage,actor=actor_user,reason=reason)
        project.version+=1;project.updated_by=actor_user;project.save(update_fields=["version","updated_by","updated_at"])
        ProjectService.record(project,actor,actor_user,"project.task_unlinked",new={"task_id":str(task.pk)},correlation_id=correlation_id)
        return link

    @classmethod
    @transaction.atomic
    def move_stage(cls, *, task, stage, actor, actor_user, task_version, project_version, correlation_id=None):
        project_id=ProjectTaskLink.objects.filter(task=task,is_active=True).values_list("project_id",flat=True).first()
        if not project_id: raise ProjectBusinessError("Задача не связана с проектом.")
        project_lock(project_id)
        task=Task.objects.select_for_update().get(pk=task.pk)
        if task.version!=task_version: raise ProjectBusinessError("Версия задачи устарела.","task_version_conflict")
        link=ProjectTaskLink.objects.select_for_update().get(task=task,is_active=True)
        project=Project.objects.select_for_update().get(pk=link.project_id)
        if project.version!=project_version: raise ProjectBusinessError("Версия проекта устарела.","project_version_conflict")
        ProjectService.authorize(actor,actor_user,"project.task_link_manage",project)
        cls.authorize_task(actor,actor_user,task)
        cls.validate_stage(project,stage)
        if project.is_archived or project.status in {ProjectStatus.COMPLETED,ProjectStatus.CANCELLED}:
            raise ProjectBusinessError("Этап финального проекта менять нельзя.")
        old_stage=link.stage
        if old_stage==stage:return link
        link.stage=stage;link.version+=1;link.save(update_fields=["stage","version","updated_at"])
        ProjectTaskLinkHistory.objects.create(task=task,action=ProjectTaskLinkHistory.Action.STAGE,
            old_project=project,new_project=project,old_stage=old_stage,new_stage=stage,actor=actor_user)
        project.version+=1;project.updated_by=actor_user;project.save(update_fields=["version","updated_by","updated_at"])
        ProjectService.record(project,actor,actor_user,"project.task_stage_changed",new={"task_id":str(task.pk),"stage_id":str(stage.pk) if stage else None},correlation_id=correlation_id)
        return link

    @classmethod
    @transaction.atomic
    def move_project(cls, *, task, target_project, target_stage, actor, actor_user,
                     task_version, source_version, target_version, reason="", correlation_id=None):
        source_id=ProjectTaskLink.objects.filter(task=task,is_active=True).values_list("project_id",flat=True).first()
        if not source_id or source_id == target_project.pk:
            raise ProjectBusinessError("Укажите другой целевой проект.")
        for project_id in sorted([source_id,target_project.pk],key=str):
            project_lock(project_id)
        task=Task.objects.select_for_update().get(pk=task.pk)
        if task.version!=task_version: raise ProjectBusinessError("Версия задачи устарела.","task_version_conflict")
        link=ProjectTaskLink.objects.select_for_update().get(task=task,is_active=True)
        if link.project_id!=source_id: raise ProjectBusinessError("Связь задачи изменилась.","project_link_conflict")
        locked={obj.pk:obj for obj in Project.objects.select_for_update().filter(pk__in=[source_id,target_project.pk]).order_by("pk")}
        source=locked[source_id];target=locked[target_project.pk]
        if source.version!=source_version or target.version!=target_version:
            raise ProjectBusinessError("Версия проекта устарела.","project_version_conflict")
        for project in (source,target):
            ProjectService.authorize(actor,actor_user,"project.task_link_manage",project)
            if project.is_archived or project.status in {ProjectStatus.COMPLETED,ProjectStatus.CANCELLED}:
                raise ProjectBusinessError("Связь финального проекта менять нельзя.")
        cls.authorize_task(actor,actor_user,task)
        cls.validate_stage(target,target_stage)
        old_stage=link.stage
        link.project=target;link.stage=target_stage;link.version+=1
        link.save(update_fields=["project","stage","version","updated_at"])
        ProjectTaskLinkHistory.objects.create(task=task,action=ProjectTaskLinkHistory.Action.PROJECT,
            old_project=source,new_project=target,old_stage=old_stage,new_stage=target_stage,actor=actor_user,reason=reason)
        for project in (source,target):
            project.version+=1;project.updated_by=actor_user;project.save(update_fields=["version","updated_by","updated_at"])
        AuditService.record(action="project.task_moved",entity=link,actor_user=actor_user,actor_employee=actor,
            old_value={"project_id":str(source.pk),"stage_id":str(old_stage.pk) if old_stage else None},
            new_value={"project_id":str(target.pk),"stage_id":str(target_stage.pk) if target_stage else None},
            metadata={"reason":reason[:500]},correlation_id=correlation_id)
        DomainEventService.publish(event_type="project.task_moved",entity=link,actor=actor_user,
            payload={"task_id":str(task.pk),"source_project_id":str(source.pk),"target_project_id":str(target.pk)},correlation_id=correlation_id)
        return link

    @classmethod
    @transaction.atomic
    def create_task(cls, *, project, actor, actor_user, project_version, stage=None, template=None, task_data=None, correlation_id=None):
        project_lock(project.pk)
        # Work creation and link are one outer transaction; a failed link removes the Task and its events.
        if template:
            task = TaskTemplateService.create_task(template=template, actor=actor, actor_user=actor_user, correlation_id=correlation_id)
        else:
            task = TaskService.create(actor=actor, actor_user=actor_user, correlation_id=correlation_id, **(task_data or {}))
        cls.link(project=project, task=task, actor=actor, actor_user=actor_user,
                 project_version=project_version, task_version=task.version, stage=stage, correlation_id=correlation_id)
        return task
