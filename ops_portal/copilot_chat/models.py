from __future__ import annotations

from django.db import models
from django.utils import timezone


class PromptPack(models.Model):
    """
    DB-backed prompt pack (can be imported from JSON packs).
    Mirrors your Streamlit pack schema: name, description, created_utc, tags, prompts[].
    """

    name = models.CharField(max_length=200, unique=True)
    description = models.TextField(blank=True, default="")
    created_utc = models.DateTimeField(default=timezone.now)

    # Store tags as a simple CSV-like text to keep it lightweight.
    # If you want full tag relations later, we can normalize.
    tags = models.TextField(blank=True, default="")  # "incident,triage,vendor"
    enabled = models.BooleanField(default=True)
    updated_utc = models.DateTimeField(auto_now=True)

    def tag_list(self) -> list[str]:
        return [t.strip() for t in (self.tags or "").split(",") if t.strip()]

    def primary_prompt(self) -> str:
        first = self.prompts.order_by("order").first()
        return first.text if first else ""

    def __str__(self) -> str:
        return self.name


class Prompt(models.Model):
    pack = models.ForeignKey(PromptPack, on_delete=models.CASCADE, related_name="prompts")
    order = models.PositiveIntegerField(default=1)
    text = models.TextField()

    class Meta:
        ordering = ["pack", "order"]

    def __str__(self) -> str:
        return f"{self.pack.name} #{self.order}"


class CopilotRun(models.Model):
    """
    A single Copilot execution (prompt-only or with files).
    Persists what Streamlit stored in session_state.results.
    """

    created_at = models.DateTimeField(auto_now_add=True)
    user_key = models.CharField(max_length=120, default="localuser")

    # Celery task id (the async handle)
    task_id = models.CharField(max_length=80, blank=True, default="", db_index=True)

    # Copilot-side identifiers returned by client
    guid = models.CharField(max_length=64, blank=True, default="")
    run_id = models.CharField(max_length=64, blank=True, default="")

    prompt = models.TextField()
    answer = models.TextField(blank=True, default="")
    status = models.CharField(max_length=20, default="queued")  # queued|running|ok|timeout|error
    error = models.TextField(blank=True, default="")

    timestamp_utc = models.CharField(max_length=64, blank=True, default="")

    # For prompt-with-files runs (optional)
    uploaded_files = models.JSONField(blank=True, default=list)

    def __str__(self) -> str:
        return f"{self.created_at:%Y-%m-%d %H:%M:%S} [{self.status}] {self.prompt[:60]}"


class CopilotDownload(models.Model):
    run = models.ForeignKey(
        CopilotRun,
        on_delete=models.CASCADE,
        related_name="downloads",
    )
    filename = models.CharField(max_length=255)  # user-facing name
    disk_filename = models.CharField(max_length=255)

    def __str__(self):
        return self.filename


class CopilotBatch(models.Model):
    created_at = models.DateTimeField(auto_now_add=True)
    user_key = models.CharField(max_length=120, default="localuser")
    task_id = models.CharField(max_length=80, blank=True, default="", db_index=True)

    name = models.CharField(max_length=200, blank=True, default="")
    status = models.CharField(max_length=20, default="queued")  # queued|running|ok|error
    error = models.TextField(blank=True, default="")
    prompts = models.JSONField(default=list)  # list[str]

    def __str__(self) -> str:
        return f"{self.created_at:%Y-%m-%d %H:%M:%S} [{self.status}] {self.name or 'Batch'}"