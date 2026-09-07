from __future__ import annotations

from django.core.exceptions import ValidationError
from django.db import transaction
from django.db.models import Q
from django.utils import timezone

from audit.services import AuditService
from events.services import DomainEventService
from .assignment import AssignmentResolver, AssignmentTargetUnresolved
from .models import (
    Employee, OnboardingInstance, OnboardingStepInstance, OnboardingTemplate,
    OnboardingTemplateStep, OnboardingTemplateVersion, TeamMembership,
)


def emit(action, entity, actor=None, payload=None):
    safe = payload or {}
    AuditService.record(action=action, entity=entity, actor_user=actor, new_value=safe)
    DomainEventService.publish(event_type=action, entity=entity, actor=actor, payload=safe)


class OnboardingConflict(ValidationError):
    pass


class TemplateResolver:
    @staticmethod
    def queryset(employee):
        memberships = TeamMembership.objects.filter(employee=employee, valid_to__isnull=True).values("team_id")
        return OnboardingTemplate.objects.filter(status=OnboardingTemplate.Status.PUBLISHED).filter(
            Q(scope="position", position=employee.position_ref)
            | Q(scope="org_unit", org_unit=employee.org_unit)
            | Q(scope="location", location=employee.primary_location)
            | Q(scope="legal_entity", legal_entity=employee.legal_entity)
            | Q(scope="team", team_id__in=memberships)
            | Q(scope="global")
        ).select_related("published_version")

    @classmethod
    def resolve(cls, employee, explicit=None):
        if explicit:
            if explicit.status != OnboardingTemplate.Status.PUBLISHED:
                raise ValidationError("Explicit onboarding template is not published.")
            return explicit
        priority = {"position": 60, "team": 55, "org_unit": 40, "location": 30, "legal_entity": 20, "global": 10}
        candidates = list(cls.queryset(employee))
        if not candidates:
            raise ValidationError("No onboarding template matches employee context.")
        best = max(priority[item.scope] for item in candidates)
        matches = [item for item in candidates if priority[item.scope] == best]
        if len(matches) != 1:
            raise OnboardingConflict("Ambiguous onboarding template resolution.")
        return matches[0]


class ResponsibleResolver:
    @staticmethod
    def resolve(step, employee):
        strategy = step.responsible_strategy
        result = None
        detail = {"strategy": strategy}
        if strategy == "self":
            result = employee
        elif strategy == "direct_manager":
            result = employee.manager
        elif strategy == "explicit_employee":
            result = step.explicit_employee
        elif strategy == "assignment_target" and step.responsible_target_id:
            people = AssignmentResolver.resolve(step.responsible_target)
            if len(people) == 1:
                result = people[0]
        elif strategy == "position" and step.responsible_target_id:
            people = AssignmentResolver.resolve(step.responsible_target)
            if len(people) == 1:
                result = people[0]
        elif strategy in {"team_lead", "team_role"}:
            memberships = TeamMembership.objects.filter(employee=employee, valid_to__isnull=True).select_related("team")
            candidates = []
            for membership in memberships:
                if strategy == "team_lead" and membership.team.lead_employee_id:
                    candidates.append(membership.team.lead_employee)
                elif strategy == "team_role":
                    candidates.extend(Employee.objects.filter(team_memberships__team=membership.team, team_memberships__role=step.team_role, team_memberships__valid_to__isnull=True))
            unique = {x.pk: x for x in candidates if x.is_active and x.status != Employee.Status.TERMINATED}
            if len(unique) == 1:
                result = next(iter(unique.values()))
        elif strategy == "org_unit":
            candidates = Employee.objects.filter(org_unit=employee.org_unit, is_active=True).exclude(status=Employee.Status.TERMINATED)
            if candidates.count() == 1:
                result = candidates.first()
        if not result or not result.is_active or result.status == Employee.Status.TERMINATED:
            raise AssignmentTargetUnresolved("Onboarding responsible employee cannot be resolved.")
        detail["employee_id"] = str(result.pk)
        return result, detail


class OnboardingTemplateService:
    @staticmethod
    @transaction.atomic
    def create(*, actor_user, name, description="", scope="global", **scope_values):
        scope_fields = {"legal_entity", "org_unit", "location", "position", "team"}
        populated = {key for key in scope_fields if scope_values.get(key) is not None}
        expected = set() if scope == "global" else {scope}
        if populated != expected:
            raise ValidationError("Onboarding template scope must have exactly its matching reference.")
        template = OnboardingTemplate.objects.create(created_by=actor_user, name=name, description=description, scope=scope, **scope_values)
        emit("people.onboarding_template.created", template, actor_user, {"scope": scope})
        return template

    @staticmethod
    def validate_steps(steps):
        if not steps:
            raise ValidationError("Published onboarding template requires at least one step.")
        if len({item["key"] for item in steps}) != len(steps):
            raise ValidationError("Onboarding step keys must be unique.")
        for item in steps:
            if item.get("step_type") == "task" and not item.get("task_template"):
                raise ValidationError("TASK onboarding step requires TaskTemplate.")
            if item.get("step_type") == "link" and not item.get("external_url"):
                raise ValidationError("LINK onboarding step requires an external URL.")
        keys = {item["key"] for item in steps}
        graph = {item["key"]: set(item.get("dependencies", [])) for item in steps}
        if any(key in deps or not deps.issubset(keys) for key, deps in graph.items()):
            raise ValidationError("Invalid onboarding step dependency.")
        visiting, visited = set(), set()
        def visit(key):
            if key in visiting:
                raise ValidationError("Onboarding step dependencies contain a cycle.")
            if key in visited:
                return
            visiting.add(key)
            for dependency in graph[key]:
                visit(dependency)
            visiting.remove(key); visited.add(key)
        for key in graph:
            visit(key)

    @classmethod
    @transaction.atomic
    def publish(cls, *, template, actor_user, expected_version, steps):
        template = OnboardingTemplate.objects.select_for_update().get(pk=template.pk)
        if template.version != expected_version:
            raise OnboardingConflict("Onboarding template version conflict.")
        if template.status == OnboardingTemplate.Status.ARCHIVED:
            raise ValidationError("Archived template cannot be published.")
        cls.validate_steps(steps)
        number = (template.versions.order_by("-number").values_list("number", flat=True).first() or 0) + 1
        version = OnboardingTemplateVersion.objects.create(template=template, number=number, name_snapshot=template.name, description_snapshot=template.description, published_by=actor_user)
        by_key = {}
        for position, data in enumerate(steps, start=1):
            dependency_keys = data.pop("dependencies", [])
            item = OnboardingTemplateStep.objects.create(version=version, position=data.pop("position", position), **data)
            by_key[item.key] = (item, dependency_keys)
        for item, dependencies in by_key.values():
            item.dependencies.set([by_key[key][0] for key in dependencies])
        template.status = OnboardingTemplate.Status.PUBLISHED
        template.published_version = version
        template.version += 1
        template.save(update_fields=["status", "published_version", "version", "updated_at"])
        emit("people.onboarding_template.published", template, actor_user, {"version": number})
        return version

    @staticmethod
    @transaction.atomic
    def archive(*, template, actor_user, expected_version):
        template = OnboardingTemplate.objects.select_for_update().get(pk=template.pk)
        if template.version != expected_version:
            raise OnboardingConflict("Onboarding template version conflict.")
        template.status = OnboardingTemplate.Status.ARCHIVED; template.version += 1
        template.save(update_fields=["status", "version", "updated_at"])
        emit("people.onboarding_template.archived", template, actor_user)
        return template


class OnboardingService:
    FINAL_STEP_STATES = {OnboardingStepInstance.Status.COMPLETED, OnboardingStepInstance.Status.SKIPPED}

    @classmethod
    @transaction.atomic
    def assign(cls, *, employee, actor_user, template=None):
        employee = Employee.objects.select_for_update().get(pk=employee.pk)
        if not employee.is_active or employee.status == Employee.Status.TERMINATED:
            raise ValidationError("Inactive employee cannot receive onboarding.")
        if OnboardingInstance.objects.select_for_update().filter(employee=employee, status__in=["pending", "active", "paused"]).exists():
            raise OnboardingConflict("Employee already has active onboarding.")
        template = TemplateResolver.resolve(employee, template)
        instance = OnboardingInstance.objects.create(employee=employee, template_version=template.published_version, assigned_by=actor_user)
        step_map = {}
        for source in template.published_version.steps.select_related("explicit_employee", "responsible_target").all():
            try:
                responsible, detail = ResponsibleResolver.resolve(source, employee)
                state = OnboardingStepInstance.Status.PENDING
            except AssignmentTargetUnresolved as exc:
                responsible, detail, state = None, {"error": str(exc)}, OnboardingStepInstance.Status.BLOCKED
            step_map[source.pk] = OnboardingStepInstance.objects.create(
                onboarding=instance, template_step=source, title_snapshot=source.title,
                description_snapshot=source.description, required=source.required, status=state,
                responsible_employee=responsible, resolution_detail=detail,
                due_at=timezone.now() + source.due_offset if source.due_offset else None,
            )
        cls._refresh_dependency_states(instance)
        emit("people.onboarding.assigned", instance, actor_user, {"employee_id": str(employee.pk), "template_version_id": str(instance.template_version_id)})
        return instance

    @staticmethod
    def _locked(instance, expected_version):
        locked = OnboardingInstance.objects.select_for_update().get(pk=instance.pk)
        if locked.version != expected_version:
            raise OnboardingConflict("Onboarding instance version conflict.")
        return locked

    @classmethod
    @transaction.atomic
    def transition(cls, *, instance, actor_user, expected_version, action, reason=""):
        instance = cls._locked(instance, expected_version)
        transitions = {
            "start": ({"pending"}, "active"), "pause": ({"active"}, "paused"),
            "resume": ({"paused"}, "active"), "cancel": ({"pending", "active", "paused"}, "cancelled"),
        }
        allowed, target = transitions[action]
        if instance.status not in allowed:
            raise ValidationError("Invalid onboarding lifecycle transition.")
        instance.status = target; instance.version += 1
        fields = ["status", "version", "updated_at"]
        if action == "start": instance.started_at = timezone.now(); fields.append("started_at")
        if action == "cancel":
            instance.cancelled_at = timezone.now(); instance.cancellation_reason = reason[:500]
            fields += ["cancelled_at", "cancellation_reason"]
            instance.steps.exclude(status__in=cls.FINAL_STEP_STATES).update(status="cancelled")
        instance.save(update_fields=fields)
        emit(f"people.onboarding.{action if action != 'cancel' else 'cancelled'}", instance, actor_user, {"reason": reason[:500]} if reason else {})
        return instance

    @classmethod
    def _refresh_dependency_states(cls, instance):
        all_steps = {x.template_step_id: x for x in instance.steps.select_related("template_step").all()}
        for item in all_steps.values():
            if item.status in cls.FINAL_STEP_STATES or item.status == "in_progress" or item.responsible_employee_id is None:
                continue
            dependencies = item.template_step.dependencies.values_list("pk", flat=True)
            ready = all(all_steps[pk].status in cls.FINAL_STEP_STATES for pk in dependencies)
            desired = "pending" if ready else "blocked"
            if item.status != desired:
                item.status = desired; item.save(update_fields=["status", "updated_at"])

    @classmethod
    @transaction.atomic
    def step_action(cls, *, step, actor_employee, actor_user, expected_version, action, reason="", allow_skip=False):
        actor_employee = Employee.objects.select_for_update().get(pk=actor_employee.pk)
        onboarding_id = OnboardingStepInstance.objects.values_list("onboarding_id", flat=True).get(pk=step.pk)
        # Global lock order is Employee -> Onboarding -> Step. Termination takes
        # the same order, preventing completion/termination deadlocks.
        OnboardingInstance.objects.select_for_update().get(pk=onboarding_id)
        step = OnboardingStepInstance.objects.select_for_update().select_related("onboarding", "template_step").get(pk=step.pk)
        if step.version != expected_version:
            raise OnboardingConflict("Onboarding step version conflict.")
        if action != "skip" and step.responsible_employee_id != actor_employee.pk and step.onboarding.employee_id != actor_employee.pk:
            raise ValidationError("This onboarding step belongs to another employee.")
        now = timezone.now()
        if action == "start" and step.status == "pending":
            step.status = "in_progress"; step.started_at = now
        elif action == "complete" and step.status in {"pending", "in_progress"}:
            step.status = "completed"; step.completed_at = now; step.completed_by = actor_employee
        elif action == "skip" and allow_skip and step.status in {"pending", "in_progress", "blocked"} and reason.strip():
            step.status = "skipped"; step.skipped_at = now; step.skipped_by = actor_employee; step.skip_reason = reason[:500]
        else:
            raise ValidationError("Invalid onboarding step transition.")
        step.version += 1; step.save()
        emit(f"people.onboarding.step_{'skipped' if action == 'skip' else action + 'ed'}", step, actor_user, {"onboarding_id": str(step.onboarding_id)})
        cls.reconcile(step.onboarding)
        return step

    @classmethod
    def reconcile(cls, instance):
        instance = OnboardingInstance.objects.select_for_update().get(pk=instance.pk)
        cls._refresh_dependency_states(instance)
        steps = list(instance.steps.all())
        required = [x for x in steps if x.required]
        complete = sum(x.status in cls.FINAL_STEP_STATES for x in required)
        percent = 100 if not required else int(complete * 100 / len(required))
        changed = instance.progress_percent != percent
        instance.progress_percent = percent
        if required and complete == len(required) and instance.status in {"pending", "active", "paused"}:
            instance.status = "completed"; instance.completed_at = timezone.now(); changed = True
            emit("people.onboarding.completed", instance, payload={"employee_id": str(instance.employee_id)})
        if changed:
            instance.version += 1; instance.save(update_fields=["progress_percent", "status", "completed_at", "version", "updated_at"])
        return instance

    @staticmethod
    @transaction.atomic
    def create_task(*, step, actor_employee, actor_user):
        from work_tasks.automation import TaskTemplateService
        # Lock only the step row. PostgreSQL rejects FOR UPDATE on the nullable
        # side introduced by the optional task_template outer join.
        step = OnboardingStepInstance.objects.select_for_update().get(pk=step.pk)
        if step.task_id:
            return step.task
        if step.template_step.step_type != "task" or not step.template_step.task_template_id:
            raise ValidationError("Onboarding step has no task template.")
        task = TaskTemplateService.create_task(template=step.template_step.task_template, actor=actor_employee, actor_user=actor_user)
        step.task = task; step.version += 1; step.save(update_fields=["task", "version", "updated_at"])
        emit("people.onboarding.task_created", step, actor_user, {"task_id": str(task.pk)})
        return task
