from django.contrib import admin

from .models import ChangeIntakeRequest, OncallChangeReview, Report, VendorConfig


@admin.register(VendorConfig)
class VendorConfigAdmin(admin.ModelAdmin):
    list_display = ('vendor_template', 'updated_at')
    search_fields = ('vendor_template',)


@admin.register(ChangeIntakeRequest)
class ChangeIntakeRequestAdmin(admin.ModelAdmin):
    list_display = (
        'id', 'vendor_template', 'original_filename',
        'submit_status', 'created_chg_number', 'created_ctask_number',
        'created_at',
    )
    list_filter = ('vendor_template', 'submit_status')
    search_fields = ('original_filename', 'created_chg_number',
                     'created_ctask_number')
    readonly_fields = (
        'created_at', 'updated_at',
        'parsed_payload_json', 'proposals_json',
        'ai_completeness_json', 'ai_field_debug_json',
        'submit_task_id', 'completeness_task_id',
    )


@admin.register(Report)
class ReportAdmin(admin.ModelAdmin):
    list_display = ('name', 'slug', 'table', 'row_limit', 'updated_at')
    search_fields = ('name', 'slug', 'table', 'query')
    prepopulated_fields = {'slug': ('name',)}
    readonly_fields = ('created_at', 'updated_at')


@admin.register(OncallChangeReview)
class OncallChangeReviewAdmin(admin.ModelAdmin):
    list_display = (
        'change_number', 'stage', 'cr_approval_status',
        'ai_outage_likely', 'scheduled_start', 'updated_at',
    )
    list_filter = ('stage', 'cr_approval_status', 'ai_outage_likely',
                   'pull_purpose')
    search_fields = ('change_number', 'short_description',
                     'cmdb_ci', 'assignment_group')
