from django.contrib import admin
from .models import AssignmentTarget, Employee, EmployeeFacility, FunctionalGroup, FunctionalGroupMembership, Position
admin.site.register(Employee)
admin.site.register(EmployeeFacility)
admin.site.register(Position)
admin.site.register(FunctionalGroup)
admin.site.register(FunctionalGroupMembership)
admin.site.register(AssignmentTarget)
