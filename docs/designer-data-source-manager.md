# Designer MySQL Data Source Manager

The SLIM REPORT DESIGNER toolbar includes **Data Sources** for configuring MySQL
connections on the active report. This Sprint 7 interface is intentionally MySQL-only;
dataset setup, view discovery, query editing, and row previews are not part of this manager.

## Add Or Edit A Connection

Open **Data Sources**, then choose **Add MySQL Data Source**. Configure the connection name,
host, port, database, username, charset, and timeouts. Existing connections can be tested,
edited, or removed from the same list.

The manager supports three credential methods:

- **Runtime password** keeps a masked password only in the current browser page's memory.
  It is sent by POST for connection operations and is excluded from report and history JSON.
- **Environment-variable reference** stores only a reference such as
  `SLIM_REPORT_MYSQL_PASSWORD`. The backend resolves the reference; the browser never does.
- **No password** explicitly clears the runtime password and stored password reference.

Leaving the runtime-password field blank while editing preserves the password held by the
current Designer page. Reloading the page clears runtime passwords, so they must be entered
again. Importing a template or using undo/redo also clears runtime passwords because secrets
are excluded from history snapshots. Switching credential methods uses explicit clear flags
and cannot silently retain a credential from the previous method.

## Testing And Saving

**Test Connection** checks proposed form settings without changing the active report. The
**Test** action on a saved row checks that report data source. Test outcomes are transient UI
state and are never serialized.

Saving the form updates the active report, marks it modified, and creates one undo entry.
Use the Designer's existing **Save** action to persist the updated report template. Reopening
a saved report restores all non-secret MySQL configuration and password references.

Removal never cascades. If datasets use a connection, the manager lists the dependent dataset
names and leaves the report unchanged until those datasets are removed or reassigned.

## Security

The Designer never stores resolved passwords in the report template.

Use a dedicated MySQL account with minimum SELECT privileges and prefer environment-variable
or application-provided credential references.

Connection testing and read-only session enforcement provide defense in depth but do not
replace MySQL permission controls.
