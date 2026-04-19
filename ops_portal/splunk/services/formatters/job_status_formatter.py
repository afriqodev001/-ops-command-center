import copy

def prune_splunk_job_status(payload: dict) -> dict:
    """
    Produce a lean Splunk job status response.

    Keeps:
        - ok
        - sid
        - status (isDone, dispatchState, doneProgress)

    Drops:
        - content (entirely)
        - all other verbose status metadata
    """
    data = copy.deepcopy(payload)
    out = {}

    # pass-through basics
    for key in ("ok", "sid"):
        if key in data:
            out[key] = data[key]

    # slim status block
    status = data.get("status")
    if isinstance(status, dict):
        out["status"] = {
            "isDone": status.get("isDone"),
            "dispatchState": status.get("dispatchState"),
            "doneProgress": status.get("doneProgress"),
        }

    return out
