from django.db import migrations


PERMISSIONS = {
    "people.invitation.view": "Просмотр приглашений сотрудников", "people.invitation.create": "Создание приглашений сотрудников",
    "people.invitation.resend": "Повторная отправка приглашений сотрудников", "people.invitation.revoke": "Отзыв приглашений сотрудников",
    "people.onboarding.view_self": "Просмотр собственного онбординга", "people.onboarding.step_complete_self": "Выполнение собственных шагов онбординга",
    "people.onboarding.view": "Просмотр онбординга сотрудников", "people.onboarding.assign": "Назначение онбординга",
    "people.onboarding.manage": "Управление онбордингом", "people.onboarding.step_skip": "Пропуск шага онбординга",
    "people.onboarding_template.view": "Просмотр шаблонов онбординга", "people.onboarding_template.create": "Создание шаблонов онбординга",
    "people.onboarding_template.update": "Изменение шаблонов онбординга", "people.onboarding_template.publish": "Публикация шаблонов онбординга",
    "people.onboarding_template.archive": "Архивация шаблонов онбординга", "people.account_access.view": "Просмотр доступа сотрудников",
    "people.account_access.suspend": "Приостановка доступа сотрудников", "people.account_access.restore": "Восстановление доступа сотрудников",
    "people.account_access.block": "Блокировка доступа сотрудников", "people.account_access.reactivate": "Реактивация доступа сотрудников",
}


def seed(apps, schema_editor):
    Permission = apps.get_model("access_control", "Permission")
    for code, name in PERMISSIONS.items():
        Permission.objects.update_or_create(code=code, defaults={"name": name})


class Migration(migrations.Migration):
    dependencies = [("employees", "0013_firstloginprogress_onboardinginstance_and_more")]
    operations = [migrations.RunPython(seed, migrations.RunPython.noop)]
