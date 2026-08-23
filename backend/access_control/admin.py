from django.contrib import admin
from .models import EmployeeRole, Permission, Role, RolePermission

for model in (Permission, Role, RolePermission, EmployeeRole):
    admin.site.register(model)
