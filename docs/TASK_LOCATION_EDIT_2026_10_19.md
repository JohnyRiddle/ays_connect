# Task location selection and editing

Task creation and parameter editing load every authorized page of the location
catalog. A failed page is shown as an error with retry, rather than a truncated
successful list. Archived/inactive entries are not offered for new selection.
The saved current reference is preserved if it is absent from the selectable list.

Task parameters now include location, with cancellation and a retained selection
after a failed save. PATCH sends the task version and only changed fields. The
existing task edit permission applies; changing locations also requires visibility
of both the source and destination, and eligibility of the responsible employee and
executor. Successful changes use the existing task.updated audit trail. Task status,
roles, object identities and history are not rewritten.

Validation: PostgreSQL tests cover edit/source/destination permission denials,
member restrictions, stale versions, successful change/clear and audit preservation.
Browser checks cover later pages, failed-page retry, cancellation, denied save and
desktop/mobile layout. Production smoke is read-only; business data is not changed
for verification. No migrations or permission grants are included.
