from django.db import migrations


PERMISSIONS = {
    "people.profile.view_self": "Просмотр собственного профиля",
    "people.profile.update_self": "Изменение собственного профиля",
    "people.profile.manage": "Управление профилями сотрудников",
    "people.profile.view_sensitive": "Просмотр чувствительных полей профиля",
    "people.directory.view": "Просмотр справочника сотрудников",
    "people.directory.view_extended": "Расширенный просмотр справочника",
    "people.directory.view_inactive": "Просмотр неактивных сотрудников",
    "people.change_request.create_self": "Создание запроса на изменение своих данных",
    "people.change_request.view_self": "Просмотр своих запросов на изменение",
    "people.change_request.review": "Рассмотрение запросов на изменение данных",
    "people.change_request.apply": "Применение одобренных изменений данных",
    "people.change_request.manage": "Управление запросами на изменение данных",
}


def seed(apps, schema_editor):
    Permission=apps.get_model("access_control","Permission")
    for code,name in PERMISSIONS.items():Permission.objects.update_or_create(code=code,defaults={"name":name})


class Migration(migrations.Migration):
    dependencies=[("employees","0011_employee_profile_self_service"),("access_control","0002_initial")]
    operations=[migrations.RunPython(seed,migrations.RunPython.noop)]
