from .models import AuditEvent
def record(actor,action,entity,old_values=None,new_values=None,request=None):
    AuditEvent.objects.create(actor=actor,action=action,entity_type=entity.__class__.__name__,entity_id=str(entity.pk),old_values=old_values or {},new_values=new_values or {},ip_address=request.META.get("REMOTE_ADDR") if request else None,user_agent=request.META.get("HTTP_USER_AGENT","") if request else "")
