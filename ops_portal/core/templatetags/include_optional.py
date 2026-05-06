"""Render a template only if it exists, silently no-op otherwise.

Django's {% include %} raises TemplateDoesNotExist for missing templates
(unlike Jinja2's `{% include "x" ignore missing %}`). This tag fills the
gap for opt-in local-only includes that may not be present on every
checkout — e.g. local_nav.html for unpushed app sidebar entries.

Usage:
    {% load include_optional %}
    {% include_optional 'local_nav.html' %}
"""
from django import template
from django.template import TemplateDoesNotExist
from django.template.loader import get_template

register = template.Library()


@register.simple_tag(takes_context=True)
def include_optional(context, template_name):
    try:
        tpl = get_template(template_name)
    except TemplateDoesNotExist:
        return ''
    return tpl.render(context.flatten())
