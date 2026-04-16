# ServiceNow API Documentation

## Overview

All ServiceNow endpoints follow an **async task pattern**:

1. `POST` to a ServiceNow endpoint → receives a `task_id` immediately (HTTP 202)
2. Poll `GET /tasks/<task_id>/status/` until `ready: true`
3. Fetch the result from `GET /tasks/<task_id>/result/`

This is necessary because every operation requires an authenticated Edge browser session, which may involve launching a browser, SSO login, and making fetch calls from inside the browser context.

All request bodies are JSON. All endpoints require `Content-Type: application/json`.

---

## Base URLs

| Prefix | App |
|--------|-----|
| `/servicenow/` | ServiceNow endpoints |
| `/` | Task status/result endpoints (core) |

---

## Task Lifecycle Endpoints

These are provided by the `core` app and shared across all integrations.

---

### `GET /tasks/<task_id>/status/`

Check whether a task has finished.

**Response**
```json
{
  "task_id": "abc-123",
  "state": "PENDING" | "STARTED" | "SUCCESS" | "FAILURE" | "RETRY",
  "ready": false
}
```

Poll this until `ready` is `true`, then fetch the result.

---

### `GET /tasks/<task_id>/result/`

Fetch the result of a completed task.

**Response — not ready yet**
```json
{
  "task_id": "abc-123",
  "state": "STARTED",
  "ready": false
}
```

**Response — success**
```json
{
  "task_id": "abc-123",
  "state": "SUCCESS",
  "ready": true,
  "result": { ... }
}
```

**Response — failure**
```json
{
  "task_id": "abc-123",
  "state": "FAILURE",
  "error": "Exception message"
}
```

---

## Authentication

### `POST /servicenow/login/open/`

Opens a headed (visible) Edge browser window for the user to log in to ServiceNow via SSO. The session is persisted to a profile directory on disk and reused by all subsequent tasks for that `user_key`.

Only needs to be called once per user (or after a session expires).

**Request**
```json
{
  "user_key": "jsmith"
}
```

**Task result**
```json
{
  "status": "login_opened",
  "profile_dir": "C:\\...\\EdgeProfiles\\servicenow\\jsmith",
  "debug_port": 9400,
  "mode": "headed",
  "pid": 12345
}
```

---

## Change Requests

### `POST /servicenow/changes/get/`

Fetch a single Change Request by `sys_id`.

**Request**
```json
{
  "user_key": "jsmith",
  "sys_id": "abc123def456",
  "fields": "number,short_description,state,assignment_group",
  "display_value": true
}
```

| Field | Required | Description |
|-------|----------|-------------|
| `sys_id` | Yes | ServiceNow sys_id of the change |
| `fields` | No | Comma-separated field names. Defaults to `SERVICENOW_CHANGE_FIELDS` |
| `display_value` | No | Return display labels instead of raw values |

**Task result**
```json
{
  "result": { "number": "CHG0034567", "state": "Implement", ... },
  "raw": { ... }
}
```

---

### `POST /servicenow/changes/get-by-number/`

Fetch a single Change Request by change number (e.g. `CHG0034567`). Resolves the `sys_id` automatically.

**Request**
```json
{
  "user_key": "jsmith",
  "number": "CHG0034567",
  "fields": "number,short_description,state",
  "display_value": true
}
```

---

### `POST /servicenow/changes/bulk-get-by-number/`

Fetch multiple Change Requests by number in a single request using the ServiceNow `IN` operator.

**Request**
```json
{
  "user_key": "jsmith",
  "numbers": ["CHG0034567", "CHG0034568", "CHG0034569"],
  "fields": "number,short_description,state",
  "display_value": true
}
```

**Task result**
```json
{
  "result": {
    "found": [ { "number": "CHG0034567", ... }, ... ],
    "not_found": ["CHG0034569"],
    "by_value": { "CHG0034567": { ... } }
  }
}
```

---

### `POST /servicenow/changes/patch/`

Update fields on a Change Request by `sys_id`.

**Request**
```json
{
  "user_key": "jsmith",
  "sys_id": "abc123def456",
  "fields_to_patch": {
    "assignment_group": "<group_sys_id>",
    "short_description": "Updated description"
  }
}
```

| Field | Required | Description |
|-------|----------|-------------|
| `sys_id` | Yes | sys_id of the change to update |
| `fields_to_patch` | Yes | Non-empty dict of field → value pairs |

---

### `POST /servicenow/changes/context/`

Fetch a Change together with its CTASKs and all attachments (change-level and per-CTASK) in a single call. Accepts either `change_sys_id` or `change_number`.

**Request**
```json
{
  "user_key": "jsmith",
  "change_number": "CHG0034567",
  "display_value": true
}
```

**Task result**
```json
{
  "result": {
    "change": { ... },
    "change_attachments": [ { "file_name": "runbook.pdf", ... } ],
    "ctasks": [
      {
        "sys_id": "...",
        "number": "CTASK001",
        "attachments": [ { "file_name": "evidence.png", ... } ]
      }
    ]
  },
  "meta": {
    "resolved_sys_id": "abc123",
    "input": { "change_sys_id": null, "change_number": "CHG0034567" }
  }
}
```

---

### `POST /servicenow/changes/create/`

Create a Normal or Emergency Change via the Table API.

**Request**
```json
{
  "user_key": "jsmith",
  "kind": "normal",
  "fields": {
    "short_description": "Deploy app v2.1",
    "description": "Rolling deploy, no downtime expected.",
    "assignment_group": "<group_sys_id>"
  }
}
```

| Field | Required | Description |
|-------|----------|-------------|
| `kind` | No | `"normal"` (default) or `"emergency"` |
| `fields` | Yes | Non-empty dict of field → value pairs |

---

## Change Tasks (CTASKs)

### `POST /servicenow/ctasks/list-for-change/`

List all CTASKs linked to a Change Request.

**Request**
```json
{
  "user_key": "jsmith",
  "change_sys_id": "abc123def456",
  "fields": "sys_id,number,short_description,state,assigned_to",
  "limit": 100
}
```

---

## Incidents

### `POST /servicenow/incidents/get/`

Fetch a single Incident by `sys_id`.

**Request**
```json
{
  "user_key": "jsmith",
  "sys_id": "inc123def456",
  "fields": "number,short_description,state,priority",
  "display_value": true
}
```

---

### `POST /servicenow/incidents/get-by-field/`

Fetch an Incident by any field (e.g. `number`). Resolves `sys_id` automatically.

**Request**
```json
{
  "user_key": "jsmith",
  "field": "number",
  "value": "INC0012345",
  "display_value": true
}
```

---

### `POST /servicenow/incidents/bulk-get-by-field/`

Fetch multiple Incidents by a field using the ServiceNow `IN` operator.

**Request**
```json
{
  "user_key": "jsmith",
  "field": "number",
  "values": ["INC0012345", "INC0012346"],
  "display_value": true
}
```

---

### `POST /servicenow/incidents/patch/`

Update fields on an Incident by `sys_id`.

**Request**
```json
{
  "user_key": "jsmith",
  "sys_id": "inc123def456",
  "fields_to_patch": {
    "state": "2",
    "assigned_to": "<user_sys_id>"
  }
}
```

---

### `POST /servicenow/incidents/context/`

Fetch an Incident together with its tasks and all attachments (incident-level and per-task). Accepts either `incident_sys_id` or `incident_number`.

**Request**
```json
{
  "user_key": "jsmith",
  "incident_number": "INC0012345",
  "display_value": true
}
```

**Task result**
```json
{
  "result": {
    "incident": { ... },
    "incident_attachments": [ { "file_name": "screenshot.png", ... } ],
    "tasks": [
      {
        "task": { "sys_id": "...", "number": "ITASK001", ... },
        "attachments": [ { "file_name": "logs.txt", ... } ]
      }
    ]
  },
  "meta": {
    "resolved_sys_id": "inc123",
    "input": { "incident_sys_id": null, "incident_number": "INC0012345" }
  }
}
```

---

### `POST /servicenow/incidents/create/`

Create a new Incident via the Table API.

**Request**
```json
{
  "user_key": "jsmith",
  "fields": {
    "short_description": "App unavailable for users in region EU-West",
    "description": "Users reporting 503 errors since 14:00 UTC.",
    "impact": "2",
    "urgency": "2",
    "assignment_group": "<group_sys_id>"
  }
}
```

---

## Attachments

### `POST /servicenow/attachments/list/`

List attachment metadata for any ServiceNow record.

**Request**
```json
{
  "user_key": "jsmith",
  "table_name": "change_request",
  "table_sys_id": "abc123def456",
  "fields": "sys_id,file_name,content_type,size_bytes,download_link",
  "limit": 200
}
```

| Field | Required | Description |
|-------|----------|-------------|
| `table_name` | Yes | The ServiceNow table the record belongs to |
| `table_sys_id` | Yes | sys_id of the parent record |
| `fields` | No | Defaults to `SERVICENOW_ATTACHMENT_FIELDS` |
| `limit` | No | Default 200 |

---

## Generic Table Endpoints

These are flexible endpoints for any ServiceNow table.

---

### `POST /servicenow/table/list/`

Run a sysparm_query against any table.

**Request**
```json
{
  "user_key": "jsmith",
  "table": "change_request",
  "query": "active=true^assignment_group=<sys_id>^ORDERBYDESCsys_updated_on",
  "fields": "number,short_description,state",
  "limit": 25,
  "display_value": true
}
```

---

### `POST /servicenow/table/get-by-field/`

Fetch the first record matching `field=value`.

**Request**
```json
{
  "user_key": "jsmith",
  "table": "sys_user_group",
  "field": "name",
  "value": "Network Operations",
  "fields": "sys_id,name,manager"
}
```

---

### `POST /servicenow/table/bulk-get-by-field/`

Fetch multiple records matching a list of values using the `IN` operator.

**Request**
```json
{
  "user_key": "jsmith",
  "table": "sys_user",
  "field": "user_name",
  "values": ["jsmith", "bdoe", "alee"],
  "fields": "sys_id,user_name,name,email"
}
```

---

## Presets

Presets are named, parameterised queries defined server-side. They are safe for use in UI menus and dashboards without exposing raw query strings to the client.

---

### `POST /servicenow/presets/list/`

Return all available presets grouped by domain.

**Request**
```json
{}
```

**Task result**
```json
{
  "result": {
    "change": {
      "change_by_number": {
        "description": "Single change by number (CHG...).",
        "required_params": ["number"]
      },
      "recent_open_changes_by_group": {
        "description": "Open changes for an assignment group (recent first).",
        "required_params": ["assignment_group_sys_id"]
      }
    },
    "incident": {
      "incident_by_number": { ... },
      "recent_open_incidents_by_service": { ... },
      "open_incidents_for_group": { ... }
    }
  }
}
```

---

### `POST /servicenow/presets/run/`

Execute a preset by name with the required parameters.

**Request**
```json
{
  "user_key": "jsmith",
  "preset": "recent_open_changes_by_group",
  "params": {
    "assignment_group_sys_id": "<group_sys_id>"
  },
  "limit": 25
}
```

---

### `POST /servicenow/incidents/presets/list/`

Return incident-domain presets only.

---

### `POST /servicenow/incidents/presets/run/`

Execute an incident preset by name.

**Request**
```json
{
  "user_key": "jsmith",
  "preset": "incident_by_number",
  "params": { "number": "INC0012345" }
}
```

---

## Error Responses

All task results use a consistent error shape:

**Missing parameter**
```json
{
  "error": "missing_parameter",
  "detail": "sys_id is required",
  "example": { "sys_id": "<change_sys_id>" }
}
```

**ServiceNow API failure**
```json
{
  "error": "servicenow_get_failed",
  "status": 403,
  "detail": { "error": { "message": "...", "detail": "..." } }
}
```

**Login required**
```json
{
  "error": "login_required",
  "detail": "Login required; headed browser opened for authentication.",
  "action": "login_opened",
  "profile_dir": "C:\\...\\EdgeProfiles\\servicenow\\jsmith",
  "debug_port": 9400
}
```

When `login_required` is returned, a headed browser window has already been opened. The user should log in, then retry the original request.

---

## Full Example: Fetch a Change by Number

```bash
# 1. Submit the task
curl -X POST http://localhost:8000/servicenow/changes/get-by-number/ \
  -H "Content-Type: application/json" \
  -d '{"user_key": "jsmith", "number": "CHG0034567"}'

# Response:
# {"task_id": "f47ac10b-58cc-4372-a567-0e02b2c3d479"}

# 2. Poll status
curl http://localhost:8000/tasks/f47ac10b-58cc-4372-a567-0e02b2c3d479/status/

# Response (while running):
# {"task_id": "...", "state": "STARTED", "ready": false}

# Response (when done):
# {"task_id": "...", "state": "SUCCESS", "ready": true}

# 3. Fetch result
curl http://localhost:8000/tasks/f47ac10b-58cc-4372-a567-0e02b2c3d479/result/

# Response:
# {
#   "task_id": "...",
#   "state": "SUCCESS",
#   "ready": true,
#   "result": {
#     "result": { "number": "CHG0034567", "short_description": "...", ... },
#     "raw": { ... }
#   }
# }
```
