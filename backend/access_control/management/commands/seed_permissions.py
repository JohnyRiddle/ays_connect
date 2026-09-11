from django.core.management.base import BaseCommand
from access_control.models import Permission


PERMISSIONS = {
    "iiko.sheregesh.card.reassign": "Снятие регистрации и передача карт iikoCard: Шерегеш",
    "iiko.sheregesh.card.delete_guest": "Удаление прежнего гостя при переоформлении iikoCard: Шерегеш",
    "iiko.sheregesh.card.topup": "Пополнение кошелька при создании iikoCard: Шерегеш",
    "iiko.sheregesh.card.create": "Создание карт iikoCard: Шерегеш",
    "iiko.sheregesh.card.view": "Проверка карт iikoCard: Шерегеш",
    "employee.view": "Просмотр сотрудников",
    "employee.manage": "Управление сотрудниками",
    "organization.view": "Просмотр оргструктуры",
    "organization.manage": "Управление оргструктурой",
    "location.view": "Просмотр локаций",
    "location.manage": "Управление локациями",
    "functional_group.view": "Просмотр функциональных групп",
    "functional_group.manage": "Управление функциональными группами",
    "role.view": "Просмотр ролей",
    "role.manage": "Управление ролями",
    "audit.view": "Просмотр аудита",
    "task.create": "Создание задач",
    "task.view": "Просмотр задач",
    "task.edit": "Редактирование задач",
    "task.assign": "Публикация и назначение задач",
    "task.reassign": "Переназначение задач",
    "task.change_deadline": "Изменение срока задач",
    "task.start": "Начало выполнения задач",
    "task.pause": "Приостановка и возобновление задач",
    "task.complete": "Передача результата и завершение задач",
    "task.accept": "Приёмка задач",
    "task.reject": "Возврат задач с приёмки",
    "task.cancel": "Отмена задач",
    "task.reopen": "Повторное открытие задач",
    "task.admin": "Полное администрирование задач",
    "task.comment": "Комментирование задач",
    "task.comment_internal": "Внутренние комментарии задач",
    "task.comment_moderate": "Модерация комментариев задач",
    "task.attachment_add": "Добавление вложений задач",
    "task.attachment_delete": "Удаление вложений задач",
    "task.watch": "Самостоятельное наблюдение за задачами",
    "task.watcher_manage": "Управление наблюдателями задач",
    "task.checklist_manage": "Управление чек-листами задач",
    "task.checklist_complete": "Выполнение пунктов чек-листов",
    "checklist_template.view": "Просмотр шаблонов чек-листов",
    "checklist_template.manage": "Управление шаблонами чек-листов",
    "task_template.view": "Просмотр шаблонов задач",
    "task_template.manage": "Управление шаблонами задач",
    "task_template.use": "Создание задач из шаблонов",
    "task_recurrence.view": "Просмотр повторяющихся задач",
    "task_recurrence.manage": "Управление повторяющимися задачами",
    "task_recurrence.run": "Запуск и повтор генерации задач",
    "service_catalog.view": "Просмотр каталога услуг",
    "service_catalog.manage": "Управление каталогом услуг",
    "request_type.view": "Просмотр типов заявок",
    "request_type.manage": "Управление типами заявок",
    "request_type.publish": "Публикация схем типов заявок",
    "request.create": "Создание заявки",
}


class Command(BaseCommand):
    help = "Создаёт системный каталог permissions Phase 1.1A"

    def handle(self, *args, **options):
        for code, name in PERMISSIONS.items():
            Permission.objects.update_or_create(code=code, defaults={"name": name})
        self.stdout.write(self.style.SUCCESS(f"Permissions ready: {len(PERMISSIONS)}"))
