from django.db import migrations


DEFAULT_PRESET = {
    'slug': 'default',
    'title': 'Default (GPT 5.1)',
    'description': 'General-purpose LLM preset',
    'preset_id': 'default',
    'default_model_id': 'gpt5.1',
    'parameters': {'temperature': 0.3, 'max_completion_tokens': 4096},
    'system_instruction': (
        'You are a helpful assistant. Answer questions clearly and concisely.'
    ),
    'enabled': True,
}


def seed_default_preset(apps, schema_editor):
    """Ensure the 'default' Tachyon preset exists so AI preflight passes
    without first visiting the playground page. Idempotent."""
    TachyonPreset = apps.get_model('tachyon', 'TachyonPreset')
    slug = DEFAULT_PRESET['slug']
    if not TachyonPreset.objects.filter(slug=slug).exists():
        TachyonPreset.objects.create(**DEFAULT_PRESET)


def unseed_default_preset(apps, schema_editor):
    TachyonPreset = apps.get_model('tachyon', 'TachyonPreset')
    TachyonPreset.objects.filter(slug=DEFAULT_PRESET['slug']).delete()


class Migration(migrations.Migration):

    dependencies = [
        ('tachyon', '0001_initial'),
    ]

    operations = [
        migrations.RunPython(seed_default_preset, unseed_default_preset),
    ]
