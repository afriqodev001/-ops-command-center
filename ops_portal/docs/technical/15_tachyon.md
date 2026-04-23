# Tachyon Integration

Enterprise LLM playground and AI provider backend.

## Dual Role

1. **Playground UI** (`/tachyon/playground/`) — direct LLM interaction with preset management
2. **AI Provider Backend** — powers AI features across ServiceNow, Splunk via `_call_tachyon()`

## Key Files

```
tachyon/
├── pages.py        # playground UI + session management
├── views.py        # JSON API endpoints
├── tasks.py        # run_tachyon_llm_task, run_tachyon_llm_with_file_task
├── models.py       # TachyonPreset (UUID pk, slug, model, params, system instruction)
└── services/
    └── tachyon_upload.py  # file sanitization
```

## TachyonPreset Model

```python
class TachyonPreset(models.Model):
    id = UUIDField(primary_key=True)
    slug = CharField(unique=True)        # lookup key
    title = CharField()
    preset_id = CharField()              # Tachyon-side ID
    default_model_id = CharField()       # e.g. "gpt5.1"
    parameters = JSONField()             # temperature, max_completion_tokens
    system_instruction = TextField()
    enabled = BooleanField(default=True)
```

## Task Flow

```python
# Single query
run_tachyon_llm_task.delay(
    user_key='localuser',
    preset_slug='default',
    query='...',
    overrides={'systemInstruction': '...', 'modelId': '...'},
)

# With file attachment
run_tachyon_llm_with_file_task.delay(
    user_key='localuser',
    preset_slug='default',
    query='...',
    file_path='/path/to/file.json',
    folder_name='uploads',
)
```

## Browser Integration

Uses `fetch()` inside the authenticated browser to call Tachyon's internal API. The browser must be logged into Tachyon via SSO.

## Settings

```python
TACHYON_BASE = 'https://your-tachyon-instance.net'
TACHYON_DEFAULT_USER_ID = 'localuser'  # from .env
```
