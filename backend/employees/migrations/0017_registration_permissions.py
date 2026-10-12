from django.db import migrations

CATALOG = {
    "people.invitation.delegate": "Делегировать роль и объектный scope",
    "people.responsibility.all": "Назначать ответственность за все объекты",
}


def catalog(apps, schema_editor):
    Permission = apps.get_model("access_control", "Permission")
    Role = apps.get_model("access_control", "Role")
    RolePermission = apps.get_model("access_control", "RolePermission")
    for code, name in CATALOG.items():
        Permission.objects.get_or_create(code=code, defaults={"name": name})
    # A new role in the existing RBAC directory; never alter an existing role.
    role, created = Role.objects.get_or_create(code="employee_objects_viewer", defaults={"name": "Сотрудник: просмотр своего объекта"})
    if created:
        for code, scope, name in [("location.view", "location", "Просмотр объекта"),
                                   ("people.profile.view_self", "own", "Просмотр своего профиля")]:
            permission, _ = Permission.objects.get_or_create(code=code, defaults={"name": name})
            RolePermission.objects.create(role=role, permission=permission, scope=scope)
    # No EmployeeRole assignments, User or Employee mutations.


class Migration(migrations.Migration):
    dependencies = [("employees", "0016_object_registration"), ("access_control", "0003_alter_rolepermission_scope")]
    operations = [migrations.RunPython(catalog, migrations.RunPython.noop)]
