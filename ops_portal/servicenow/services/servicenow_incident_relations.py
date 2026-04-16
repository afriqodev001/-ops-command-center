from django.conf import settings
from servicenow.services.servicenow_table import list_records


def list_tasks_for_incident(
    driver,
    *,
    incident_sys_id: str,
    fields: str,
    limit: int = 200,
):
    """
    List tasks related to an Incident.
    Relationship: incident_task.incident = incident.sys_id
    """
    query = f"incident={incident_sys_id}^ORDERBYsys_updated_on"

    return list_records(
        driver,
        table=settings.SERVICENOW_INCIDENT_TASK_TABLE,
        query=query,
        fields=fields,
        limit=limit,
        display_value=True,
    )


def list_attachments_for_record(
    driver,
    *,
    table_name: str,
    table_sys_id: str,
    fields: str,
    limit: int = 200,
):
    """
    Generic attachment listing via sys_attachment.
    """
    query = (
        f"table_name={table_name}"
        f"^table_sys_id={table_sys_id}"
        f"^ORDERBYDESCsys_created_on"
    )

    return list_records(
        driver,
        table="sys_attachment",
        query=query,
        fields=fields,
        limit=limit,
        display_value=False,
    )
