from dataclasses import asdict, dataclass


@dataclass(frozen=True)
class MetricDefinition:
    code: str
    category: str
    title: str
    unit: str
    direction: str
    population: str
    description: str


_RAW = [
    ("tasks_created", "VOLUME", "Создано задач", "count", "neutral", "activity"),
    ("tasks_completed", "VOLUME", "Завершено задач", "count", "higher", "activity"),
    ("requests_created", "VOLUME", "Создано заявок", "count", "neutral", "activity"),
    ("requests_resolved", "VOLUME", "Решено заявок", "count", "higher", "activity"),
    ("task_cycle_seconds_avg", "SPEED", "Средний цикл задачи", "seconds", "lower", "cohort"),
    ("task_cycle_seconds_p50", "SPEED", "Медиана цикла задачи", "seconds", "lower", "cohort"),
    ("task_cycle_seconds_p90", "SPEED", "P90 цикла задачи", "seconds", "lower", "cohort"),
    ("request_resolution_seconds_avg", "SPEED", "Среднее время решения заявки", "seconds", "lower", "cohort"),
    ("request_resolution_seconds_p50", "SPEED", "Медиана решения заявки", "seconds", "lower", "cohort"),
    ("request_resolution_seconds_p90", "SPEED", "P90 решения заявки", "seconds", "lower", "cohort"),
    ("sla_response_compliance", "SLA", "Соблюдение SLA ответа", "percent", "higher", "cohort"),
    ("sla_resolution_compliance", "SLA", "Соблюдение SLA решения", "percent", "higher", "cohort"),
    ("task_deadline_compliance", "SLA", "Соблюдение сроков задач", "percent", "higher", "cohort"),
    ("sla_breaches", "SLA", "Нарушения SLA", "count", "lower", "activity"),
    ("task_rejection_rate", "QUALITY", "Доля возвратов задач", "percent", "lower", "cohort"),
    ("task_reopen_rate", "QUALITY", "Доля переоткрытий задач", "percent", "lower", "cohort"),
    ("request_reopen_rate", "QUALITY", "Доля переоткрытий заявок", "percent", "lower", "cohort"),
    ("review_acceptance_rate", "QUALITY", "Приёмка с первого раза", "percent", "higher", "cohort"),
    ("waiting_seconds", "DISCIPLINE", "Время ожидания", "seconds", "neutral", "activity"),
    ("waiting_requester_seconds", "DISCIPLINE", "Ожидание заявителя", "seconds", "neutral", "activity"),
    ("waiting_external_seconds", "DISCIPLINE", "Внешнее ожидание", "seconds", "neutral", "activity"),
    ("deadline_changes", "DISCIPLINE", "Переносы срока", "count", "lower", "activity"),
    ("reassignments", "DISCIPLINE", "Переназначения", "count", "neutral", "activity"),
    ("active_tasks", "LOAD", "Активные задачи", "count", "neutral", "snapshot"),
    ("active_requests", "LOAD", "Активные заявки", "count", "neutral", "snapshot"),
    ("overdue_tasks", "LOAD", "Просроченные задачи", "count", "lower", "snapshot"),
    ("backlog_requests", "FLOW", "Backlog заявок", "count", "lower", "snapshot"),
    ("throughput", "FLOW", "Пропускная способность", "count", "higher", "activity"),
    ("net_flow", "FLOW", "Чистый поток", "count", "neutral", "activity"),
    ("performance_score", "QUALITY", "Итоговый индекс", "score", "higher", "cohort"),
]

METRICS = {code: MetricDefinition(code, category, title, unit, direction, population, title) for code, category, title, unit, direction, population in _RAW}


def metric_payload(code=None):
    if code:
        definition = METRICS.get(code)
        return asdict(definition) if definition else None
    return [asdict(value) for value in METRICS.values()]
