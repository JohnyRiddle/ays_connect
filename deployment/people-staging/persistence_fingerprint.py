import hashlib, json, os, sys
from pathlib import Path
sys.path.insert(0,'/app')
os.environ.setdefault('DJANGO_SETTINGS_MODULE','config.settings')
import django
django.setup()
from django.conf import settings
from employees.models import Employee,EmployeeProfile
from accounts.models import User
from work_tasks.models import Task
from service_requests.models import ServiceRequest
assert os.environ.get('PEOPLE_ACCEPTANCE_MODE')=='1'
assert settings.DATABASES['default']['NAME']=='people_acceptance'
rows={
    'employees':list(Employee.objects.order_by('pk').values_list('pk','employee_number','user_id')),
    'users':list(User.objects.order_by('pk').values_list('pk','is_active','auth_version')),
    'profiles':list(EmployeeProfile.objects.order_by('pk').values_list('pk','employee_id','version')),
    'tasks':list(Task.objects.order_by('pk').values_list('pk','number')),
    'requests':list(ServiceRequest.objects.order_by('pk').values_list('pk','number')),
    'media':sorted(hashlib.sha256(p.read_bytes()).hexdigest() for p in Path(settings.MEDIA_ROOT).rglob('*') if p.is_file()),
}
print(hashlib.sha256(json.dumps(rows,default=str,sort_keys=True).encode()).hexdigest())
