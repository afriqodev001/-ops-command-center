from django.contrib import admin
from .models import TachyonPreset


@admin.register(TachyonPreset)
class TachyonPresetAdmin(admin.ModelAdmin):
    list_display = ('slug', 'title', 'preset_id', 'default_model_id', 'enabled', 'version', 'owner_team')
    list_filter = ('enabled', 'default_model_id', 'owner_team')
    search_fields = ('slug', 'title', 'description', 'preset_id')
    prepopulated_fields = {'slug': ('title',)}
    readonly_fields = ('id', 'created_at', 'updated_at')
    fieldsets = (
        (None, {
            'fields': ('id', 'slug', 'title', 'description', 'enabled', 'owner_team'),
        }),
        ('Tachyon Config', {
            'fields': ('preset_id', 'default_model_id', 'parameters', 'system_instruction', 'version'),
        }),
        ('Timestamps', {
            'fields': ('created_at', 'updated_at'),
            'classes': ('collapse',),
        }),
    )
