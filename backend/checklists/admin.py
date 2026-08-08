from django.contrib import admin
from .models import ChecklistAnswer,ChecklistQuestion,ChecklistRun,ChecklistTemplate,Violation
for model in (ChecklistTemplate,ChecklistQuestion,ChecklistRun,ChecklistAnswer,Violation):admin.site.register(model)
