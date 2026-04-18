# tachyon/models.py
import uuid
from django.db import models


class TachyonPreset(models.Model):
    """
    DB-backed Tachyon Playground preset wrapper.

    Stores:
    - preset_id (from Tachyon)
    - default model + parameters
    - system instruction
    """

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)

    slug = models.SlugField(max_length=120, unique=True)
    title = models.CharField(max_length=200)
    description = models.TextField(blank=True)

    # Tachyon identifiers
    preset_id = models.CharField(max_length=64)
    default_model_id = models.CharField(max_length=80, default="gpt5.1")

    # Default inference parameters (JSON)
    parameters = models.JSONField(default=dict)
    system_instruction = models.TextField(
        default="Please answer the given questions based on the context provided."
    )

    enabled = models.BooleanField(default=True)
    version = models.IntegerField(default=1)
    owner_team = models.CharField(max_length=120, blank=True)

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return self.slug