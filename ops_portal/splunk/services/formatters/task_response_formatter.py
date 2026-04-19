from splunk.services.formatters.job_events_formatter import prune_splunk_events_payload
import copy

def prune_splunk_task_response(payload: dict) -> dict:
    data = copy.deepcopy(payload)

    # remove saved_search
    data.pop("saved_search", None)

    # remove status.content
    status = data.get("status")
    if isinstance(status, dict):
        status.pop("content", None)

    # prune events section
    if "events" in data:
        data["events"] = prune_splunk_events_payload({"events": data["events"]})["events"]

    return data
