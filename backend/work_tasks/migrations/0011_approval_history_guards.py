from django.db import migrations

SQL = r'''
CREATE FUNCTION work_approval_history_guard() RETURNS trigger AS $$
BEGIN
  RAISE EXCEPTION 'approval_history_immutable';
END;
$$ LANGUAGE plpgsql;
CREATE TRIGGER work_approval_history_immutable BEFORE UPDATE OR DELETE ON work_tasks_taskapprovalevent
FOR EACH ROW EXECUTE FUNCTION work_approval_history_guard();

CREATE FUNCTION work_approval_identity_guard() RETURNS trigger AS $$
BEGIN
  IF TG_OP = 'DELETE' THEN RAISE EXCEPTION 'approval_identity_immutable'; END IF;
  IF ROW(NEW.id,NEW.task_id,NEW.comment_id,NEW.requester_id,NEW.approver_id,NEW.source_body,NEW.source_internal,NEW.created_at)
     IS DISTINCT FROM ROW(OLD.id,OLD.task_id,OLD.comment_id,OLD.requester_id,OLD.approver_id,OLD.source_body,OLD.source_internal,OLD.created_at)
  THEN RAISE EXCEPTION 'approval_identity_immutable'; END IF;
  IF NEW.version != OLD.version+1 THEN RAISE EXCEPTION 'approval_version_invalid'; END IF;
  IF NOT ((OLD.status='PENDING' AND NEW.status IN ('APPROVED','CLARIFICATION_REQUESTED','CANCELLED') AND NEW.round_number=OLD.round_number)
      OR (OLD.status='CLARIFICATION_REQUESTED' AND NEW.status='CANCELLED' AND NEW.round_number=OLD.round_number)
      OR (OLD.status IN ('CLARIFICATION_REQUESTED','APPROVED') AND NEW.status='PENDING' AND NEW.round_number=OLD.round_number+1))
  THEN RAISE EXCEPTION 'approval_transition_invalid'; END IF;
  RETURN NEW;
END;
$$ LANGUAGE plpgsql;
CREATE TRIGGER work_approval_identity_immutable BEFORE UPDATE OR DELETE ON work_tasks_taskapproval
FOR EACH ROW EXECUTE FUNCTION work_approval_identity_guard();

CREATE FUNCTION work_approval_event_guard() RETURNS trigger AS $$
DECLARE a work_tasks_taskapproval; previous work_tasks_taskapprovalevent;
BEGIN
  SELECT * INTO a FROM work_tasks_taskapproval WHERE id=NEW.approval_id;
  IF NEW.sequence<>a.version OR NEW.to_status<>a.status OR NEW.round_number<>a.round_number OR length(btrim(NEW.text))=0
  THEN RAISE EXCEPTION 'approval_history_invalid'; END IF;
  SELECT * INTO previous FROM work_tasks_taskapprovalevent WHERE approval_id=a.id ORDER BY sequence DESC LIMIT 1;
  IF previous.id IS NULL THEN
    IF NEW.sequence<>1 OR NEW.action<>'request' OR NEW.from_status<>'' OR NEW.to_status<>'PENDING' OR NEW.round_number<>1 OR NEW.actor_id<>a.requester_id
    THEN RAISE EXCEPTION 'approval_first_event_invalid'; END IF;
  ELSE
    IF NEW.sequence<>previous.sequence+1 OR NEW.from_status<>previous.to_status THEN RAISE EXCEPTION 'approval_event_sequence_invalid'; END IF;
    IF NOT ((NEW.action='approve' AND NEW.to_status='APPROVED' AND NEW.actor_id=a.approver_id)
        OR (NEW.action='clarify' AND NEW.to_status='CLARIFICATION_REQUESTED' AND NEW.actor_id=a.approver_id)
        OR (NEW.action='resubmit' AND NEW.to_status='PENDING' AND NEW.actor_id=a.requester_id)
        OR (NEW.action='cancel' AND NEW.to_status='CANCELLED'))
    THEN RAISE EXCEPTION 'approval_event_action_invalid'; END IF;
  END IF;
  RETURN NEW;
END;
$$ LANGUAGE plpgsql;
CREATE TRIGGER work_approval_event_valid BEFORE INSERT ON work_tasks_taskapprovalevent
FOR EACH ROW EXECUTE FUNCTION work_approval_event_guard();

CREATE FUNCTION work_approval_consistency_guard() RETURNS trigger AS $$
DECLARE a work_tasks_taskapproval; e work_tasks_taskapprovalevent;
BEGIN
  SELECT * INTO a FROM work_tasks_taskapproval WHERE id=NEW.id;
  SELECT * INTO e FROM work_tasks_taskapprovalevent WHERE approval_id=a.id ORDER BY sequence DESC LIMIT 1;
  IF e.id IS NULL OR e.sequence<>a.version OR e.to_status<>a.status OR e.round_number<>a.round_number
  THEN RAISE EXCEPTION 'approval_history_missing'; END IF;
  RETURN NULL;
END;
$$ LANGUAGE plpgsql;
CREATE CONSTRAINT TRIGGER work_approval_consistent AFTER INSERT OR UPDATE ON work_tasks_taskapproval
DEFERRABLE INITIALLY DEFERRED FOR EACH ROW EXECUTE FUNCTION work_approval_consistency_guard();
'''

REVERSE = '''
DROP TRIGGER IF EXISTS work_approval_consistent ON work_tasks_taskapproval;
DROP TRIGGER IF EXISTS work_approval_event_valid ON work_tasks_taskapprovalevent;
DROP TRIGGER IF EXISTS work_approval_identity_immutable ON work_tasks_taskapproval;
DROP TRIGGER IF EXISTS work_approval_history_immutable ON work_tasks_taskapprovalevent;
DROP FUNCTION IF EXISTS work_approval_consistency_guard();
DROP FUNCTION IF EXISTS work_approval_event_guard();
DROP FUNCTION IF EXISTS work_approval_identity_guard();
DROP FUNCTION IF EXISTS work_approval_history_guard();
'''

def forwards(apps,schema_editor):
    if schema_editor.connection.vendor=='postgresql':schema_editor.execute(SQL)
    Permission=apps.get_model('access_control','Permission')
    for code,name in [('view','Просмотр согласований'),('request','Запрос согласования'),('respond','Ответ на согласование'),('cancel','Отмена согласования')]:
        Permission.objects.get_or_create(code='task.approval.'+code,defaults={'name':name})


def backwards(apps,schema_editor):
    if schema_editor.connection.vendor=='postgresql':schema_editor.execute(REVERSE)
    # Catalog permissions are intentionally retained; no grants are added/removed.


class Migration(migrations.Migration):
    dependencies=[('work_tasks','0010_comment_approvals')]
    operations=[migrations.RunPython(forwards,backwards)]
