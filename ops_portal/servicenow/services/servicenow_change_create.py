from django.conf import settings
from servicenow.services.servicenow_fetch import fetch_json_in_browser
from servicenow.urls_builders import (
    build_change_create_url,
    build_standard_change_template_url,
)


def create_change_via_table_api(driver, *, kind: str, fields: dict):
    """
    Create Normal or Emergency change via Table API.
    """
    kind = (kind or "normal").lower()
    if kind not in ("normal", "emergency"):
        raise ValueError(f"Unsupported change kind: {kind}")

    payload = {
        "type": kind,
        "chg_model": kind,
        "state": "new",
        **(fields or {}),
    }

    url = (
        f"{settings.SERVICENOW_BASE}/api/now/table/{settings.SERVICENOW_CHANGE_TABLE}"
        f"?sysparm_input_display_value=true"
    )
    return fetch_json_in_browser(
        driver,
        method="POST",
        url=url,
        body_obj=payload,
    )


def open_standard_change_template(driver, *, template_key: str):
    """
    Open Standard Change creation UI using a template.
    """
    templates = getattr(settings, "SERVICENOW_STANDARD_TEMPLATES", {})
    if template_key not in templates:
        raise ValueError(f"Unknown standard template: {template_key}")

    url = build_standard_change_template_url(templates[template_key])
    driver.get(url)

    return {
        "status": "standard_change_ui_opened",
        "template_key": template_key,
        "url": url,
    }
