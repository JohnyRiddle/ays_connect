from django.db.models import Q
from django.utils import timezone

from .models import Task, TaskStatus
from .policies import TaskAccessPolicy


class TaskSelector:
    RELATED = (
        "author", "responsible_employee", "executor_employee", "org_unit", "legal_entity", "location", "parent",
        "responsible_target__employee", "responsible_target__position", "responsible_target__org_unit", "responsible_target__functional_group",
        "executor_target__employee", "executor_target__position", "executor_target__org_unit", "executor_target__functional_group",
    )

    @classmethod
    def visible_to(cls, employee):
        return Task.objects.select_related(*cls.RELATED).filter(TaskAccessPolicy.visibility_query(employee=employee)).distinct()

    @classmethod
    def apply_filters(cls, queryset, params):
        direct = ("status", "priority", "author", "responsible_employee", "executor_employee", "org_unit", "legal_entity", "location", "parent")
        for field in direct:
            if params.get(field):
                queryset = queryset.filter(**{field: params[field]})
        if str(params.get("overdue", "")).lower() == "true":
            queryset = queryset.filter(due_at__lt=timezone.now()).exclude(status__in=(TaskStatus.COMPLETED, TaskStatus.CANCELLED))
        if params.get("search"):
            value = params["search"]
            queryset = queryset.filter(Q(number__icontains=value) | Q(title__icontains=value) | Q(description__icontains=value))
        for key, lookup in (("created_from", "created_at__gte"), ("created_to", "created_at__lte"), ("due_from", "due_at__gte"), ("due_to", "due_at__lte")):
            if params.get(key):
                queryset = queryset.filter(**{lookup: params[key]})
        ordering = params.get("ordering", "-created_at")
        allowed = {"created_at", "updated_at", "due_at", "priority", "number"}
        if ordering.lstrip("-") in allowed:
            queryset = queryset.order_by(ordering)
        return queryset

    @classmethod
    def apply_saved_or_system_view(cls, queryset, employee, params):
        from .models import TaskSavedView
        from .exceptions import TaskBusinessError
        from .ux import SavedViewValidator, SystemViewService
        if params.get("saved_view"):
            view = TaskSavedView.objects.filter(pk=params["saved_view"], owner=employee, is_active=True).first()
            if view is None:
                raise TaskBusinessError("Saved View недоступен.", code="task_saved_view_forbidden")
            filters = SavedViewValidator.validate_filters(view.filters)
            proxy = {**filters, "ordering": view.ordering}
            return cls.apply_filters(queryset, proxy)
        if params.get("system_view"):
            return SystemViewService.apply(queryset, employee, params["system_view"])
        return queryset
