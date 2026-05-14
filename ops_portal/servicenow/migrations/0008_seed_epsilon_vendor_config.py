import json

from django.db import migrations


EPSILON_DEFAULTS = {
    'cmdb_ci':           'Epsilon - EPSLN - VSS',
    'assignment_group':  'CTUMLS:Loyalty Platform Support',
    'u_code_change':     'No',
}


def seed_epsilon(apps, schema_editor):
    VendorConfig = apps.get_model('servicenow', 'VendorConfig')
    VendorConfig.objects.update_or_create(
        vendor_template='epsilon',
        defaults={'defaults_json': json.dumps(EPSILON_DEFAULTS, indent=2)},
    )


def unseed_epsilon(apps, schema_editor):
    VendorConfig = apps.get_model('servicenow', 'VendorConfig')
    VendorConfig.objects.filter(vendor_template='epsilon').delete()


class Migration(migrations.Migration):

    dependencies = [
        ('servicenow', '0007_vendorconfig'),
    ]

    operations = [
        migrations.RunPython(seed_epsilon, unseed_epsilon),
    ]
