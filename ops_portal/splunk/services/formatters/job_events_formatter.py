import copy

def prune_splunk_events_payload(payload: dict) -> dict:
    """
    Prunes a raw Splunk job events payload.

    Removes:
        - raw.tokens
        - raw.segment_tree

    Expected shape:
        payload.data.results[*]._raw.{tokens, segment_tree}
    """
    data = copy.deepcopy(payload)

    events = data.get("events") or data  # supports wrapped or raw usage

    if not isinstance(events, dict):
        return data

    data_block = events.get("data")
    if not isinstance(data_block, dict):
        return data

    results = data_block.get("results")
    if not isinstance(results, list):
        return data

    for result in results:
        if not isinstance(result, dict):
            continue

        raw = result.get("_raw")
        if isinstance(raw, dict):
            raw.pop("tokens", None)
            raw.pop("segment_tree", None)

    return data
