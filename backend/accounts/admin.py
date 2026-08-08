from django.contrib import admin
from django.contrib.auth.admin import UserAdmin
from .models import Role, User, UserRole
admin.site.register(User, UserAdmin)
admin.site.register(Role)
admin.site.register(UserRole)
