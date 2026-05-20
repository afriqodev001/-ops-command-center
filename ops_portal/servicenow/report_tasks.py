"""
Celery tasks for the ServiceNow Reports feature.

  - reports_run_task         pull rows for a saved Report from ServiceNow
  - reports_ai_summary_task  summarise already-pulled rows via the AI provider

Both return a serialisable dict for the polling endpoints in report_pages.py.
"""
from __future__ import annotations

from celery import shared_task

from servicenow.services.servicenow_table import list_records
from servicenow.tasks import with_servicenow_auth_retry


@shared_task(bind=True)
def reports_run_task(self, body: dict):
    """Run a saved Report's query against ServiceNow and return the rows."""
    from servicenow.models import Report

    report_id = (body or {}).get('report_id')
    if not report_id:
        return {'error': 'missing_report_id'}

    try:
        report = Report.objects.get(pk=report_id)
    except Report.DoesNotExist:
        return {'error': 'report_not_found'}

    table = (report.table or 'incident').strip()
    query = (report.query or '').strip()
    fields = (report.fields or '').strip()
    limit = int(report.row_limit or 100)

    def op(driver):
        return list_records(
            driver,
            table=table,
            query=query,
            fields=fields,
            limit=limit,
            display_value=True,
        )

    return with_servicenow_auth_retry(body=body, operation=op, retry_once=True)


@shared_task(bind=True)
def reports_ai_summary_task(self, body: dict):
    """Summarise a report's results (passed in as CSV text) via the AI provider."""
    from servicenow.services.ai_assist import _call_llm
    from servicenow.services.prompt_store import get_prompt

    csv_text = ((body or {}).get('csv') or '').strip()
    report_name = (body or {}).get('report_name') or 'report'
    if not csv_text:
        return {'error': 'no_data',
                'detail': 'The report has no rows to summarise. Run it first.'}

    system = get_prompt('report_ai_summary')
    # Cap the payload so a huge report doesn't blow the prompt budget.
    user = f"Report: {report_name}\n\nResults (CSV):\n{csv_text[:12000]}"

    raw = (_call_llm(system, user) or '').strip()
    if not raw:
        return {'error': 'ai_empty',
                'detail': 'The AI provider returned an empty response.'}

    return {'ok': True, 'summary': raw, 'report_name': report_name}
