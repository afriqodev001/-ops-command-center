# AI Provider System

Unified AI routing used by all apps. Configuration in Preferences, prompts editable via UI.

## Architecture

```
Any app feature → _call_llm(system, user) → _get_ai_config()
                                                  ↓
                              provider == 'tachyon' → _call_tachyon()
                              provider == 'claude'  → _call_claude()
                              provider == 'openai'  → _call_openai()
                              provider == 'none'    → error message
```

## Key Files

- `servicenow/services/ai_assist.py` — `_call_llm()`, provider routing, response parsing
- `servicenow/services/prompt_store.py` — file-backed prompt CRUD with defaults
- `servicenow/services/user_preferences.py` — `ai_provider`, `ai_tachyon_preset_slug`, `ai_model`

## Provider Config (user_preferences.json)

```json
{
  "ai_provider": "tachyon",
  "ai_tachyon_preset_slug": "default",
  "ai_model": "gpt5.1"
}
```

## Prompt Store (prompts.json)

Each prompt has a key, label, description, and text. Defaults baked into `prompt_store.py` — overrides in the JSON file.

```python
from servicenow.services.prompt_store import get_prompt
system = get_prompt('splunk_results_analysis')
```

UI: Preferences → AI Prompts → Edit prompts

## Response Parsing

`_extract_json_dict(raw)` handles:
1. Direct JSON parse
2. Markdown code fences (```json ... ```)
3. First `{...}` block scan

`_call_tachyon` extracts from nested Tachyon shapes: `data.answer`, `data.response`, `data.text`

## Tachyon File Upload

For large data (e.g., Splunk results), `run_tachyon_llm_with_file_task` uploads a file alongside the prompt:

```python
task = run_tachyon_llm_with_file_task.delay(
    user_key='localuser',
    preset_slug='default',
    query=prompt,
    file_path='/path/to/results.json',
    folder_name='analysis',
    overrides={'systemInstruction': system_prompt},
)
```

## Error Handling

- All providers surface errors as `{'_ai_error': 'message'}` instead of silent `'{}'`
- Tachyon preset errors auto-retry once with 1s delay
- Unparseable responses show first 200 chars for debugging
