from splunk.services.splunk_fetch import fetch_json_in_browser
from splunk.urls_builders import build_alerts_search_url


def search_alerts(
    driver,
    *,
    search_term: str,
    count: int = 20,
    offset: int = 0,
):
    url = build_alerts_search_url(
        search_term=search_term,
        count=count,
        offset=offset,
    )

    headers = {
        "accept": "application/json",
        "x-requested-with": "XMLHttpRequest",
    }

    return fetch_json_in_browser(
        driver,
        method="GET",
        url=url,
        headers=headers,
    )