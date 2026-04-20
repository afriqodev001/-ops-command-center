from urllib.parse import urlencode, quote
from django.conf import settings


def _base() -> str:
    return getattr(settings, "SPLUNK_BASE", "https://your-splunk.splunkcloud.com").rstrip("/")


def _app() -> str:
    return getattr(settings, "SPLUNK_APP", "search").strip()


def build_alerts_search_url(
    *,
    search_term: str,
    count: int = 50,
    offset: int = 0,
):
    """
    Build the Splunk saved searches endpoint URL with a name filter.
    Searches all saved searches (not just scheduled alerts).
    """

    base = (
        f"{_base()}"
        f"/en-US/splunkd/__raw/servicesNS/-/{_app()}/saved/searches"
    )

    params = {
        "output_mode": "json",
        "sort_dir": "asc",
        "sort_key": "name",
        "sort_mode": "natural",
        "search": f'name="*{search_term}*"',
        "count": count,
        "offset": offset,
    }

    return base + "?" + urlencode(params)


def build_jobs_create_url(*, namespace_user: str) -> str:
    """
    POST /search/v2/jobs (create job) is typically scoped to a user namespace.
    Example:
      /servicesNS/<user>/<app>/search/v2/jobs
    """
    user_enc = quote(namespace_user, safe="")
    return f"{_base()}/en-US/splunkd/__raw/servicesNS/{user_enc}/{_app()}/search/v2/jobs"


def build_job_status_url(*, sid: str, namespace_user: str = "nobody") -> str:
    """
    GET /search/v2/jobs/{sid} (job status).
    Usually works with /servicesNS/nobody/<app>/... for reading, but we allow override.
    """
    user_enc = quote(namespace_user, safe="")
    sid_enc = quote(sid, safe="")
    base = f"{_base()}/en-US/splunkd/__raw/servicesNS/{user_enc}/{_app()}/search/v2/jobs/{sid_enc}"
    return base + "?" + urlencode({"output_mode": "json"})


def build_job_events_url(
    *,
    sid: str,
    offset: int = 0,
    count: int = 20,
    segmentation: str = "full",
    max_lines: int = 5,
    field_list: str = "host,source,sourcetype,_raw,_time,_audit,_decoration,eventtype,_eventtype_color,linecount,_fulllinecount,_icon,tag*,index",
    truncation_mode: str = "abstract",
    output_mode: str = "json",
) -> str:
    """
    Builds the Splunk endpoint that powers the Events tab for a search job.

    Example:
      /servicesNS/nobody/<app>/search/v2/jobs/<sid>/events?...
    """
    sid_enc = quote(sid, safe="")  # SID is a path segment; must be URL-safe
    base = f"{_base()}/en-US/splunkd/__raw/servicesNS/nobody/{_app()}/search/v2/jobs/{sid_enc}/events"

    params = {
        "output_mode": output_mode,
        "offset": str(int(offset)),
        "count": str(int(count)),
        "segmentation": segmentation,
        "max_lines": str(int(max_lines)),
        "field_list": field_list,
        "truncation_mode": truncation_mode,
    }
    return base + "?" + urlencode(params)


def build_job_results_preview_url(
    *,
    sid: str,
    offset: int = 0,
    count: int = 20,
    show_metadata: bool = True,
    add_summary_to_metadata: bool = False,
    output_mode: str = "json_rows",
) -> str:
    """
    Builds the Splunk endpoint that powers the Statistics tab preview for a search job.

    Example:
      /servicesNS/nobody/<app>/search/v2/jobs/<sid>/results_preview?...
    """
    sid_enc = quote(sid, safe="")
    base = f"{_base()}/en-US/splunkd/__raw/servicesNS/nobody/{_app()}/search/v2/jobs/{sid_enc}/results_preview"

    params = {
        "output_mode": output_mode,
        "count": str(int(count)),
        "offset": str(int(offset)),
        "show_metadata": "true" if show_metadata else "false",
        "add_summary_to_metadata": "true" if add_summary_to_metadata else "false",
    }
    return base + "?" + urlencode(params)
