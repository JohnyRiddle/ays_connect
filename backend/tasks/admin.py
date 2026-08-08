from django.contrib import admin
from .models import DeadlineChangeRequest, RecurrenceRule, Task, TaskAttachment, TaskComment, TaskHistory
for model in (Task,TaskComment,TaskAttachment,TaskHistory,DeadlineChangeRequest,RecurrenceRule): admin.site.register(model)
