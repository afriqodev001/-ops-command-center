from django.apps import AppConfig


class ServicenowConfig(AppConfig):
    name = 'servicenow'

    def ready(self):
        # Plug ServiceNow features into core's extension points so `core`
        # never imports from `servicenow` — the dependency arrow stays
        # servicenow -> core. See core/extensions.py.
        from core.extensions import (
            register_context_provider, register_dashboard_view,
        )
        from .pages import dashboard
        from .services.oncall_banner import get_active as oncall_banner_active

        # ServiceNow owns the rich landing-page dashboard.
        register_dashboard_view(dashboard)

        # The oncall banner is shown on every page; contribute it to the
        # shared template context.
        register_context_provider(
            lambda request: {'oncall_banner': oncall_banner_active()}
        )
