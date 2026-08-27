from django.db.models import Q

from audit.models import AuditEvent
from .policies import ServiceRequestAccessPolicy


class ServiceRequestActivitySelector:
    TYPE_MAP={
        "request.comment.created":"request.comment_added","request.comment.updated":"request.comment_updated","request.comment.deleted":"request.comment_deleted",
        "request.attachment.added":"request.attachment_added","request.attachment.deleted":"request.attachment_deleted",
        "request.watcher.added":"request.watcher_added","request.watcher.removed":"request.watcher_removed",
        "request.in_progress":"request.started","request.waiting_requester":"request.waiting","request.waiting_external":"request.waiting",
        "request.resolved":"request.resolved","request.closed":"request.closed","request.cancelled":"request.cancelled","request.task_created":"request.task_created",
    }
    @classmethod
    def page(cls,*,request,employee,page=1,page_size=25):
        comment_internal=ServiceRequestAccessPolicy.can_view_internal(employee=employee,request=request,kind="comment")
        attachment_internal=ServiceRequestAccessPolicy.can_view_internal(employee=employee,request=request,kind="attachment")
        qs=AuditEvent.objects.select_related("actor_employee").filter(Q(entity_type="ServiceRequest",entity_id=str(request.pk))|Q(metadata__request_id=str(request.pk)))
        if not comment_internal:qs=qs.exclude(action__startswith="request.comment",metadata__visibility="internal")
        if not attachment_internal:qs=qs.exclude(action__startswith="request.attachment",metadata__visibility="internal")
        qs=qs.order_by("-created_at","-id");page=max(int(page),1);page_size=min(max(int(page_size),1),100);total=qs.count();rows=qs[(page-1)*page_size:page*page_size];results=[]
        for row in rows:
            actor=row.actor_employee;data=dict(row.metadata or {});data.pop("request_id",None);data.pop("request_number",None);data.pop("visibility",None)
            if row.action=="request.comment.deleted":data={"message":"Комментарий удалён"}
            results.append({"id":str(row.pk),"type":cls.TYPE_MAP.get(row.action,row.action),"timestamp":row.created_at,"actor":{"id":str(actor.pk),"display_name":actor.display_name} if actor else None,"data":data})
        return {"count":total,"page":page,"page_size":page_size,"results":results}
