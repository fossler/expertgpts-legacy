# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

ExpertGPTs is a multi-expert AI chat application built with Streamlit that provides access to domain-specific AI experts (Python, Data Science, Writing, etc.) with support for multiple LLM providers (DeepSeek, OpenAI, Z.AI, KIMI), full internationalization (14 languages), template-based page generation, and persistent chat history.

## Working Guidelines

### DRY Principle (Don't Repeat Yourself)

**CRITICAL:** Always follow the DRY principle when making changes to this codebase.

#### Guidelines:

1. **Before writing any code:**
   - Search for existing implementations that do the same thing

2. **When you find duplicated code:**
   - Extract it to a shared function in the appropriate `lib/` subdirectory
   - Update ALL locations to use the shared function
   - Update templates AND generated pages
   - Test to ensure no regressions

3. **Common patterns that should be shared:**
   - Form fields (temperature, text inputs, etc.)
   - Validation logic (expert names, descriptions, etc.)
   - Dialog rendering (add, edit, delete)
   - Documentation content (constants)
   - **i18n translations**: Import `i18n` at module level, never inline in functions
   - **Expert name translations**: Use `sanitize_name()` to generate keys dynamically

4. **Checklist before committing:**
   - [ ] Did I search for existing implementations?
   - [ ] Is this code duplicated anywhere else?
   - [ ] Did I update all templates?
   - [ ] Did I update all generated pages?

### No Backward Compatibility

**IMPORTANT: Do NOT maintain backward compatibility code.**

When refactoring or changing data structures:
- Remove old code paths immediately
- Do NOT add "legacy" support or migration logic
- Assume all configs and data will be regenerated from scratch
- The user can run `scripts/reset_application.py` to recreate everything

**Rationale:**
- This is a personal project with a small number of experts
- Configs are easy to regenerate
- Backward compatibility adds complexity and technical debt
- Clean code is more valuable than supporting old data formats


## Reference Documentation

Read these documents when working on specific areas:

| Document | When to Read |
|----------|--------------|
| `docs/architecture/overview.md` | Understanding overall system architecture |
| `docs/architecture/template-system.md` | Modifying expert page templates |
| `docs/architecture/multi-provider-llm.md` | Adding LLM providers, thinking parameters |
| `docs/architecture/background-streaming.md` | Streaming implementation, battery optimization |
| `docs/architecture/state-management.md` | Session state, persistent storage |
| `docs/internationalization/I18N_GUIDE.md` | Adding translations, language handling |
| `docs/configuration/overview.md` | Configuration files structure |
| `docs/configuration/api-keys.md` | API key management, secrets |
| `docs/configuration/tls.md` | HTTPS with a Caddy reverse proxy (`deploy/caddy/`); keep it generic, no host- or domain-specific values |
| `docs/configuration/expert-configs.md` | Expert YAML configuration format |
| `docs/development/adding-features.md` | Step-by-step feature development |
| `docs/development/testing.md` | Writing and running tests |
| `docs/reference/troubleshooting.md` | Debugging common issues |


## Development Commands

### Setup & Installation
```bash
# Install uv (fast Python package manager)
curl -LsSf https://astral.sh/uv/install.sh | sh

# Install locked dependencies (pyproject.toml + uv.lock; `uv run` also does this automatically)
uv sync

# First-time setup (creates 9 example experts)
uv run python scripts/setup.py
```

### Running the Application
```bash
# Start the Streamlit app (recommended)
uv run streamlit run app.py

# With enhanced file watching (faster reload during development)
uv run streamlit run app.py --server.fileWatcherType=watchdog
```

### Testing
```bash
# Run all tests (recommended)
./scripts/run_tests.sh

# Direct pytest commands
uv run pytest -v                           # All tests
uv run pytest -v -m "unit"                # Unit tests only
uv run pytest -v -m "integration"         # Integration tests only
uv run pytest -v -m "not slow"            # Exclude slow tests
```

### Code Quality
```bash
# Format code with Ruff
uv run ruff format .

# Check formatting without making changes
uv run ruff format --check .
```

### Administrative Scripts
```bash
# Regenerate expert pages from templates/template.py (keeps configs and chat history)
uv run python scripts/regenerate_pages.py

# Reset application - DELETES all configs, pages, chat history, chat images and
# streaming cache, then recreates the example experts
echo "yes" | uv run python scripts/reset_application.py

# Update translations - syncs English source with all locale files
uv run python scripts/update_translations.py
```

## Architecture Patterns

### 1. Template-Based Expert System

The application uses a **template-driven architecture** where expert pages are generated from a single template:

- **Permanent pages** (committed to git): `pages/1000_Home.py`, `pages/9998_Settings.py`, `pages/9999_Help.py` and the hidden `pages/_debug.py`
- **Generated expert pages** (auto-generated): `pages/1001_*.py` and higher
- **Template source**: `templates/template.py` with `{{EXPERT_ID}}` and `{{EXPERT_NAME}}` placeholders
- **Configuration files**: Each expert has a YAML config in `configs/{expert_id}.yaml`
- **Page numbering scheme**: Home (1000) → Experts (1001+) → Settings (9998) → Help (9999)

**Key insight**: When modifying expert page UI/UX, edit the template and regenerate all pages (`uv run python scripts/regenerate_pages.py`). When modifying Home/Settings/Help, edit the permanent files directly.

### 2. Multi-Provider LLM Abstraction

A unified client interface supports multiple LLM providers through OpenAI-compatible APIs:

- **Client implementation**: `lib/llm/llm_client.py` - `LLMClient` class
- **Provider-specific thinking parameters**:
  - **OpenAI**: `reasoning_effort` - passed as direct parameter and **always sent explicitly, including `none`** (if omitted, the API applies its own default and GPT-6 reasons anyway). Per-model levels: `gpt-6.1-sol` (default) / `gpt-6-astra` low/medium/high/xhigh (always reason, default medium); `gpt-6-luna`, GPT-5.6, GPT-5.4 none/low/medium/high/xhigh (default none). No `max` (Responses API only; the app uses Chat Completions). Unsupported levels fall back to the model's default via `resolve_reasoning_effort()`.
  - **DeepSeek**: `reasoning_effort` (high/max) as direct param + `thinking.type=disabled` in extra_body to turn off. Both `deepseek-flash` (V4.1 Flash, app-wide default) and `deepseek-v4-pro` support dual thinking modes; API defaults to enabled.
  - **Z.AI**: `thinking.type` (enabled/disabled) - set via extra_body parameter. `glm-5.3` (default; low/high/max, default max) and `glm-5.2` (high/max) always think and add a direct `reasoning_effort`.
  - **KIMI**: generation-dependent. `kimi-k3` uses a top-level `reasoning_effort` (low/high/max, default max; always reasons). `kimi-k2.7-code` / `kimi-k2.7-code-highspeed` always think (`thinking_always_on: True`; reasoning_effort ignored; UI shows a fixed, disabled "Enabled" selector). `kimi-k2.6` uses the `thinking.type` (enabled/disabled) extra_body toggle; "none" sends `type=disabled` explicitly because the API thinks by default. Detected by whether the model config defines `reasoning_efforts` (same pattern as Z.AI's GLM-5.2/5.3).
- **Fixed temperature**: `fixed_temperature` may be declared provider-wide (OpenAI = 1.0, since OpenAI rejects temperature != 1 while reasoning) or per model (kimi-k3, kimi-k2.7-code* = 1.0); `fixed_temperature_without_thinking` covers per-mode values (kimi-k2.6: 1.0 thinking / 0.6 without). Resolved by `get_fixed_temperature(provider, model=None, thinking=True)`; `LLMClient._effective_temperature()` overrides the user-selected temperature on every call path; `render_temperature_input()` disables the control for such models.
- **Temperature limits**: provider-level `max_temperature` (Z.AI = 1.0, API range [0, 1]; default `DEFAULT_MAX_TEMPERATURE` = 2.0) caps the UI control and is clamped in `_effective_temperature()`. Provider flag `temperature_ignored_with_thinking` (DeepSeek: thinking mode silently ignores temperature) makes `render_temperature_input(thinking_level=...)` disable the control with a hint (`dialogs.temperature.ignored_with_thinking`) unless thinking is `none`; the toolbox model row (`_render_model_settings()`) applies the same cap and disabled state. Helpers: `get_max_temperature()`, `is_temperature_ignored()`, `is_thinking_enabled()`.
- **Effort helpers**: `get_default_reasoning_effort(provider, model)` and `resolve_reasoning_effort(provider, model, thinking_level)` in `constants.py`. The UI preselects the model's default effort when a stored level isn't supported, and shows effort selectors for every model with `reasoning_efforts`.
- **Provider configuration**: Centralized in `lib/shared/constants.py` with O(1) lookup tables
- **Connection pooling**: `lib/llm/client_pool.py` caches client instances for performance

**Key insight**: All four providers use the OpenAI Python client with custom `base_url`. Provider differences are handled in `_prepare_thinking_param()` method.

### 3. State Management

Multi-layered state system with different lifetimes:

- **Shared session state** (initialized once per session):
  - API keys for all providers (`st.session_state["api_keys"]`)
  - Default LLM settings (provider, model, thinking level)
  - Language preference
  - Navigation state

- **Per-expert session state** (separate for each expert):
  - Messages history: `st.session_state[f"messages_{expert_id}"]`
  - Config cache version: `st.session_state[f"cache_version_{expert_id}"]` (bumped by `invalidate_expert_cache()`)
  - Attachment uploader generation: `st.session_state[f"attachments_{expert_id}"]` (incremented after each sent message to clear the toolbox)
  - Provider, model, temperature and thinking level are not kept in session state: they live in the expert's YAML config and are saved there directly by the toolbox model row

- **Persistent storage** (survives app restarts):
  - Chat history: `chat_history/{expert_id}.json` (1MB file size limit)
  - Chat images: `chat_attachments/{expert_id}/<uuid>.<ext>` (gitignored, local per machine; messages only hold `<image ... ref="...">` references)
  - Expert configurations: `configs/{expert_id}.yaml`
  - User preferences: `.streamlit/app_defaults.toml`
  - Theme settings: `.streamlit/config.toml`

**Key insight**: Session state initialization happens in two phases - shared state first (via `initialize_shared_session_state()`), then per-expert state with chat history loading.

### 4. Background Streaming System

Battery-optimized file-based caching that allows LLM responses to complete in the background when users navigate away:

- **Implementation**: `lib/storage/streaming_cache.py` - `StreamingCache` class
- **Fixed filenames**: `{expert_id}_latest.txt` and `{expert_id}_latest.meta` per expert
- **Daemon threads**: Background threads write chunks to cache files with `fsync()` for crash resilience
- **Polling mechanism**: Foreground polls cache files every 100ms (battery-optimized: 2-3% CPU vs 5-10% for session state polling)
- **Smart cleanup**: Only deletes completed/error streams, preserves in-progress streams
- **Isolation**: one pair of cache files and one writer thread per expert; previous cache files are cleared before a new stream starts

**Key features:**
- ✅ Real-time streaming with blinking cursor (`▌`)
- ✅ Background completion when navigating away
- ✅ Automatic resume when returning to page
- ✅ Survives app crashes and restarts
- ✅ Easy debugging (inspect `.txt` cache files)
- ✅ Follows DRY principle (mirrors `chat_history_manager.py` pattern)

**Key insight**: File I/O uses DMA (Direct Memory Access), allowing CPU to enter deep sleep states between reads. This provides significantly better battery life on notebooks compared to session state polling approaches.

**Usage in template:**
```python
# Start background streaming
cache = StreamingCache(EXPERT_ID)
cache.start_streaming_to_file(client, messages, temperature, model, system_prompt, thinking_level)

# Poll for updates
response = poll_stream_and_display(cache, EXPERT_ID, messages_key, message_placeholder)

# Resume incomplete streams on page load
check_and_display_cached_responses(config, messages_key)
```

### 5. Three-Layer Internationalization

Clean separation of concerns for 14-language support:

```
┌─────────────────────────────────────────────────────────┐
│  1. STORAGE LAYER (configs/*.yaml)                      │
│  Expert content in English - Single Source of Truth     │
└─────────────────────────────────────────────────────────┘

┌─────────────────────────────────────────────────────────┐
│  2. TRANSLATION LAYER (locales/ui/*.json)               │
│  UI translations ONLY - Buttons, labels, messages       │
└─────────────────────────────────────────────────────────┘

┌─────────────────────────────────────────────────────────┐
│  3. RUNTIME LAYER (template.py, i18n.py)                │
│  Language prefix injection: "Respond in German"         │
└─────────────────────────────────────────────────────────┘
```

**Implementation**: `i18n.get_language_prefix()` injects language instruction into system prompts at runtime, ensuring AI responds in user's selected language while expert content remains in English.

**Key insight**: Never translate expert content in YAML configs. Only UI elements go in locale files. Language selection auto-detects on first run and persists in `app_defaults.toml`.

## Critical Files Reference

### Core Application
- **`app.py`** - Main entry point using `st.navigation()`; handles first-run detection and dynamic page loading
- **`templates/template.py`** - Master template for all expert pages; edit here then run `scripts/regenerate_pages.py` to update all experts
- **`pages/1000_Home.py`** - Home page with expert list and "Add Chat" functionality (permanent file)
- **`pages/9998_Settings.py`** - Settings page for API keys, themes, language, provider defaults (permanent file); sections are deep-linkable via `?tab=<key>`
- **`pages/9999_Help.py`** - Help page with documentation and links (permanent file)
- **`pages/_debug.py`** - Hidden diagnostics page, reachable only via `/debug` (permanent file, not in the navigation)

### Core Library (`lib/`)
- **`config_manager.py`** - Expert YAML config operations (load, update, delete, list)
- **`page_generator.py`** - Creates new expert pages from template; generates unique expert IDs; `regenerate_pages()` rewrites existing expert pages from the template (keeps filename, `EXPERT_ID`, `EXPERT_NAME`)
- **`chat_toolbox.py`** (`lib/ui/`) - Model row (`_render_model_settings()`: dropdown of all models of providers with an API key, thinking/temperature where supported, saved immediately after an `on_change`; replaces the former sidebar "Model settings") and toolbox row below the chat input (first row: toolbox; second row: model; `render_chat_toolbox(widget_key, config, expert_id, messages_key)` → `ToolboxInput(attachments, images, voice_prompt)`): "Attach file", "Attach image" (disabled with a tooltip unless `supports_images()`), "Voice input" (`_render_voice_input()`: `st.audio_input` in a popover, transcribed via `lib/audio/transcription.py` and sent automatically as `ToolboxInput.voice_prompt`), status captions and, right-aligned, "Clear chat history" (confirmation popover) and the context usage popover (`_calculate_context_stats()`, `_render_context_usage()`; replaces the former sidebar metric). `render_user_message()` shows image thumbnails (width 240) and text attachments as "📎 <filename>" expanders. Rendered inside `with st.bottom:` right after `st.chat_input` in `handle_user_input()`
- **`transcription.py`** (`lib/audio/`) - Speech-to-text for voice input: `get_transcription_provider(chat_provider)` (OpenAI → "openai", else "zai"), `TRANSCRIPTION_MODELS` (`gpt-transcribe`, `glm-asr-2512`), `MAX_DURATION_SECONDS` (Z.AI: 30), `get_audio_duration()`, `transcribe(audio, chat_provider, api_key, mime_type, language, context)` → `TranscriptionResult(text, error)` (`language` → OpenAI hint, `context` → GLM-ASR `prompt`)
- **`attachments.py`** (`lib/shared/`) - Text file attachments (UTF-8, ≤ `ATTACHMENT_MAX_SIZE_KB`, extensions in `ATTACHMENT_FILE_TYPES`) and images (`IMAGE_FILE_TYPES`, ≤ `IMAGE_MAX_SIZE_MB`, `validate_image_attachment()` via Pillow); `build_message_content()` appends `<image name="..." ref="...">` tags and `<attachment name="...">` blocks to the prompt, `split_message_content()` returns `(prompt, attachments, images)`, `to_api_content(content, images_supported)` turns image tags into `image_url` parts (base64) or a text note for text-only models / missing files
- **`attachment_store.py`** (`lib/storage/`) - Image files under `chat_attachments/{expert_id}/` (`save_image()`, `get_image_path()`, `get_image_data_url()`, `delete_expert_attachments()`); path-traversal safe via `safe_path_join()`, directory resolved from the project root
- **`llm_client.py`** - Multi-provider LLM client; handles thinking parameter differences via `_prepare_thinking_param()`
- **`client_pool.py`** - Cached client connections; use `get_cached_client()` instead of direct instantiation
- **`secrets_manager.py`** - Secure API key management; reads/writes `.streamlit/secrets.toml` with 600 permissions
- **`app_defaults_manager.py`** - User preferences management (default provider/model/thinking level, language, display settings)
- **`config_toml_manager.py`** - Theme configuration management for `.streamlit/config.toml`
- **`chat_history_manager.py`** - Persistent conversation storage; enforces 1MB file size limit; `delete_chat_history()` also deletes the expert's images
- **`session_state.py`** - Initializes shared session state (API keys, navigation, defaults); `handle_pending_navigation()`, `invalidate_expert_cache()`
- **`streaming_cache.py`** - Background streaming with file-based caching; battery-optimized polling for LLM responses
- **`token_manager.py`** - Token counting and context usage tracking; calculates percentage of context used
- **`i18n.py`** - Internationalization engine; loads locale files and injects language prefixes
- **`constants.py`** - Provider/model configurations; defines `LLM_PROVIDERS` dict and O(1) lookup tables
- **`helpers.py`** - Utility functions including `translate_expert_name()` for default expert names
- **`file_ops.py`** - Shared file system operations - **UPDATED**: Added `ensure_streamlit_file()` helper
- **`format_ops.py`** - Shared file format operations (TOML, YAML, JSON read/write)

### Configuration Files
- **`.streamlit/secrets.toml`** - API keys (gitignored, auto-set to 600 permissions)
- **`.streamlit/config.toml`** - Theme settings (gitignored)
- **`.streamlit/app_defaults.toml`** - User preferences (gitignored)
- **`.streamlit/*.example`** - Template files for configuration (committed to git)
- **`configs/{expert_id}.yaml`** - Expert-specific configurations (name, description, system_prompt, temperature, metadata)

### Documentation
- **`README.md`** - Comprehensive user and developer documentation
- **`docs/`** - Full documentation organized by topic (see Reference Documentation section above)

## Important Development Workflows

### Modifying Expert Pages

**To update ALL expert pages** (UI, layout, functionality):
1. Edit `templates/template.py`
2. Run `uv run python scripts/regenerate_pages.py`
3. All existing expert pages (1001+) are rewritten from the updated template; each keeps its filename, `EXPERT_ID` and `EXPERT_NAME`, so configs and chat history stay attached

Do NOT use `reset_application.py` for this: it deletes all configs, pages and chat history.

**To update Home, Settings or Help pages only**:
- Edit `pages/1000_Home.py`, `pages/9998_Settings.py` or `pages/9999_Help.py` directly (these are permanent files)
- No regeneration needed

**Key insight**: The template uses `{{EXPERT_ID}}` and `{{EXPERT_NAME}}` placeholders. The page generator replaces these when creating new expert pages.

### Adding a New LLM Provider

1. **Add provider configuration** in `lib/shared/constants.py`:
   - Add entry to `LLM_PROVIDERS` dict with name, base_url, default_model, models dict
   - Models must include: display_name, max_tokens, thinking_param
   - Add `"vision": True` only if the model accepts image input (verify live; some models silently ignore images)

2. **Update thinking parameter handling** in `lib/llm/llm_client.py`:
   - Modify `_prepare_thinking_param()` method if provider uses custom thinking parameters
   - Return format: `(extra_body_dict, direct_params_dict)`

3. **API key UI** in `pages/9998_Settings.py`:
   - No change needed: the API Key section lists every provider in `LLM_PROVIDERS`; keys are stored under the provider's `api_key_env` name

4. **Update secrets template**:
   - Add `{PROVIDER}_API_KEY = ""` to `.streamlit/secrets.toml.example`

5. **Update lookup tables** in `lib/shared/constants.py`:
   - Existing code automatically generates lookup tables from `LLM_PROVIDERS`

### Creating a New Expert

**Via UI** (recommended):
1. Go to Home page
2. Click "➕ Add Chat" in sidebar
3. Fill form: name, description, temperature, optional custom system prompt
4. Page automatically generated and navigated to

**Programmatically** (creates config + page, like the UI):
```python
from lib.ui.dialogs import create_new_expert

expert_id, page_path = create_new_expert(
    chat_name="My Expert",
    description="Expert in...",
    temperature=0.7,
    custom_system_prompt="Custom prompt...",  # None = generate via LLM (needs api_key)
    provider="deepseek",
    model="deepseek-flash",
)
```

### Internationalization

**Adding a new UI string translation**:
1. Add string to all locale files: `locales/ui/{language}.json`
2. Use in code: `i18n.t("key.path")`
3. Update `scripts/update_translations.py` if needed

**Key principle**:
- **Expert content** (name, description, system_prompt): Keep in English in YAML configs
- **UI elements** (buttons, labels, errors): Translate in locale files
- **AI responses**: Automatically in user's language via runtime prefix injection

### Debugging Common Issues

**Expert not appearing in navigation**:
- Check expert page file exists in `pages/` with correct numbering (1001+)
- Verify corresponding config exists in `configs/`
- `app.py` builds the navigation from `PageGenerator.list_pages()` (cached with `st.cache_resource`; `clear_page_cache()` resets it)

**"Configuration not found" error**:
- Run `uv run python scripts/setup.py` to create example experts
- Verify `configs/{expert_id}.yaml` exists

**API key errors**:
- Check `.streamlit/secrets.toml` exists and has valid key (min 20 characters)
- Verify permissions: `ls -la .streamlit/secrets.toml` should show `-rw-------`
- Set key via Settings → API Key for automatic permission management

**Chat history not persisting**:
- Check `chat_history/` directory exists
- Verify file size under 1MB limit
- Check `save_chat_history()` and `load_chat_history()` in `chat_history_manager.py`

## Security Considerations

- **API keys**: Stored in `.streamlit/secrets.toml` (gitignored, 600 permissions)
- **No hardcoded credentials**: All secrets through Streamlit secrets API
- **Input validation**: API keys validated for minimum length (20 characters)
- **File permissions**: Secrets file automatically set to 600 (owner read/write only) on creation/modification
- **Sanitization**: Expert IDs and filenames sanitized to prevent path traversal

## Performance Guidelines

- **Use connection pooling**: Always use `get_cached_client()` from `client_pool.py` instead of creating new `LLMClient` instances
- **Leverage caching**: Expert configs cached with TTL; invalidate by incrementing `cache_version_{expert_id}` in session state
- **Pre-computed lookups**: Use utility functions from `constants.py` (`get_provider_config()`, `get_model_config()`, etc.) for O(1) access
- **Chat history limits**: 1MB file size limit enforced; old messages auto-trimmed when exceeded
- **Lazy loading**: Streamlit only loads active page; no need to implement additional lazy loading

## Git Workflow Notes

- **Branch protection**: `main` is protected; never commit or push to it directly. Work on a feature branch, push it and merge via a pull request
- **Permanent pages**: `pages/1000_Home.py`, `pages/9998_Settings.py`, `pages/9999_Help.py` and `pages/_debug.py` are committed to git
- **Generated pages**: `pages/1001_*.py` and higher are auto-generated and gitignored (created by `setup.py` / the UI, refreshed via `regenerate_pages.py`)
- **Template changes**: Commit `templates/template.py` only; generated pages are gitignored and local. Run `uv run python scripts/regenerate_pages.py` after changing the template, and again on every other machine after pulling a template change
- **Configurations**: Expert YAML configs in `configs/` are gitignored (local per machine, like `chat_history/` and `chat_attachments/`)

## File Watching During Development

For faster development workflow:
```bash
uv run streamlit run app.py --server.fileWatcherType=watchdog
```

Requires `watchdog` package (in the `dev` dependency group of `pyproject.toml`, installed by `uv sync`). Provides instant reload when Python files change.

### Current Session (2026-10-10)

**Completed:**
- **OpenAI GPT-6**: added `gpt-6.1-sol` (new default), `gpt-6-astra` (top tier), `gpt-6-luna` (cheap); all 1.05M context. Sol/Astra always reason (low/medium/high/xhigh, default medium); Luna none..xhigh (default none). GPT-5.6 / GPT-5.4 kept
  - **reasoning_effort fix**: now always sent explicitly for OpenAI, including `none` (omitting it let GPT-6 reason anyway); unsupported levels fall back to the model's default via `resolve_reasoning_effort()`
  - **Temperature fix**: provider-level `fixed_temperature: 1.0` for OpenAI, resolved by `get_fixed_temperature()`
- **DeepSeek rename**: `deepseek-v4-flash` → `deepseek-flash` ("DeepSeek V4.1 Flash"); now the DeepSeek and app-wide default
- **Z.AI GLM-5.3**: new default (1M context, 128K output, always reasons, low/high/max, default max)
- **KIMI**: `kimi-k3` efforts now low/high/max (default max); added `kimi-k2.7-code` / `kimi-k2.7-code-highspeed` (262K context, always think via `thinking_always_on`, temperature 1.0)
  - **K2.6 fix**: "none" now sends `thinking.type=disabled` explicitly; temperature fixed per mode (1.0 thinking / 0.6 without, `fixed_temperature_without_thinking`)
- UI preselects the model's default effort for unsupported stored levels; expert dialog shows effort selectors for every model with `reasoning_efforts` (incl. GLM-5.2/5.3)
- Updated README, this file and `docs/`
- **Chat toolbox**: toolbox row pinned below the chat input (`st.chat_input` + `render_chat_toolbox()` inside `with st.bottom:`); first entry "Attach file" (`lib/ui/chat_toolbox.py`, `lib/shared/attachments.py`, i18n section `chat_toolbox`)
  - **Attach file**: text files only (UTF-8, ≤ 200 KB each); embedded into the user message as `<attachment name="...">` blocks, so LLM request, token counting and chat history work unchanged; shown as "📎 <filename>" expanders
  - **Attach image**: PNG/JPEG/WebP/GIF, ≤ 5 MB each (`IMAGE_FILE_TYPES`, `IMAGE_MAX_SIZE_MB`, Pillow validation); only for models with `"vision": True` (`supports_images()`), otherwise disabled with tooltip. Verified live via Chat Completions: deepseek-flash, all 8 OpenAI and all 4 KIMI models accept images; deepseek-v4-pro silently ignores them (no flag); Z.AI text-only per docs (no flag, not live-tested)
  - Images saved to `chat_attachments/{expert_id}/<uuid>.<ext>` (`lib/storage/attachment_store.py`, gitignored); the message only holds an `<image name="..." ref="...">` tag (before `<attachment>` blocks), so images are not counted in the context usage
  - `to_api_content()` builds `image_url` parts (base64 data URLs) per request; text-only models get "[Image <name> omitted: ...]", missing files "[Image <name> is no longer available]"; user messages show thumbnails, also after reload
  - "Clear chat history" moved from the sidebar into the toolbox (left of the context usage) with a confirmation popover; it also deletes the expert's images; `reset_application.py` deletes `chat_attachments/`
  - **Voice input**: "Voice input" popover (`:material/mic:` icon) with `st.audio_input`; `lib/audio/transcription.py` routes OpenAI experts to `gpt-transcribe` and all others to Z.AI `glm-asr-2512` (30 s limit), both via the OpenAI-compatible `/audio/transcriptions` endpoint and the pooled client. The transcript is sent automatically (`ToolboxInput.voice_prompt`); each recording is sent once (cached by audio hash, recorder key resets). GLM-ASR has no language parameter, so the localized sentence `chat_toolbox.voice_asr_context` is sent as `prompt` (without it German came back as Chinese/English). Both paths verified end-to-end; also live-tested GLM-5.3 (low/high/max) and the other Z.AI chat models
  - **Model settings** moved from the sidebar into a toolbox row: dropdown of all models of providers with an API key (switches provider), thinking/temperature only where the model supports them, saved immediately; provider links ("Chat | Platform") removed
  - **Avatar per answer**: `assistant_message()` stores `provider`/`model` on assistant messages (persisted in the chat history, stream metadata for background streams); older messages fall back to the current provider
  - **Context usage** moved from the sidebar into the toolbox (right side): popover "<emoji> <percent>%" with usage %, total/max, system prompt and chat message tokens; `display_context_usage()` removed from the template
  - New i18n keys in `chat_toolbox` (all 14 locales): `attach_image`, `attach_image_help`, `image_not_supported`, `attached_images`, `error_image_too_large`, `error_not_image`, `image_unavailable`
- **`scripts/regenerate_pages.py`** (`PageGenerator.regenerate_pages()`): rewrites existing expert pages from the template without touching configs or chat history; replaces `reset_application.py` as the way to apply template changes
- **Pytest config** moved from `tests/pytest.ini` to `[tool.pytest.ini_options]` in `pyproject.toml` (`uv run pytest -m unit` works from the project root)
- **Real dialogs**: "Add Chat" (`open_add_chat_dialog()`), "Edit Expert", delete and reset confirmations are blocking modal `st.dialog`s (`dismissible=False`: no X, ESC or outside click; they close only via their own Cancel/confirm buttons) opened from the button click (title built at call time for i18n); the `show_*_dialog` / `editing_expert_*` / `confirm_*` flags and `ensure_dialog_state()` were removed, success messages use `st.toast`. The edit dialog now also validates the expert name
- **Settings deep links**: the Settings section is bound to the URL with stable, language-independent keys (`/Settings?tab=api_key`; `SETTINGS_SECTIONS` in `pages/9998_Settings.py`, `SETTINGS_TAB_PARAM` in `constants.py`) via `st.query_params` instead of the built-in `bind="query-params"`, which puts the translated label in the URL. Only the active section renders; `settings_active_tab` was removed
- **Heading icons**: page titles and section headings use `st.title/st.subheader(..., icon=":material/...:")` instead of emojis in the text (Home `smart_toy`, expert pages `psychology_alt`, Help `menu_book`, Settings sections per `SETTINGS_SECTIONS`); the Settings tab labels use `:material/<name>:` markup. Buttons, alerts and captions keep their emojis
- **Audit fixes**: deleting an expert also deletes its chat history, images and streaming cache; streaming errors are saved like other request errors (`save_stream_result()` in the template keeps a partial response and adds the translated, sanitized error; `StreamingCache` writes the error to the metadata only; failed background streams are shown on page load); the Add Chat dialog preselects the default thinking level; the template no longer forces the OpenAI temperature (`LLMClient._effective_temperature()` does); navigation icons match the page titles (`smart_toy`, `psychology_alt`, `menu_book`); `packaging` is a direct dependency; Streamlit 1.65 items 3, 5, 6, 7 documented as not adopted

### Previous Session (2026-07-18)

**Completed:**
- **KIMI K3 support**: added the `kimi-k3` flagship model (Moonshot / `MOONSHOT_API_KEY`)
  - 1M context (1,048,576 tokens); set as the new default KIMI model (`kimi-k2.6` kept as secondary)
  - K3 reasons via a **top-level `reasoning_effort`** (`max` only today), NOT the K2.x `thinking` extra_body toggle — handled per-model in `LLMClient._prepare_thinking_param()`
  - Introduced a generic **`fixed_temperature`** model-config field (kimi-k3 = 1.0), enforced in `LLMClient._effective_temperature()` (covers streaming, non-streaming, and system-prompt generation) and surfaced in the UI via `render_temperature_input(model=...)`
  - `render_provider_selection` / `render_thinking_mode_ui` now show kimi-k3 as a reasoning-effort selector (`max`); k2.6 keeps the enabled/disabled toggle
  - Added `KIMI` to the `Provider` enum / `ProviderKey`; regenerated expert pages from the template
  - Updated docs (README, `docs/api/providers.md`, `docs/architecture/multi-provider-llm.md`, `app_defaults.toml.example`)

### Previous Session (2026-07-15)

**Completed:**
- **OpenAI model refresh**: upgraded the small models and added the GPT-5.6 family
  - Upgraded `gpt-5-mini` → `gpt-5.4-mini` and `gpt-5-nano` → `gpt-5.4-nano` (both 400K context, up to `xhigh` reasoning)
  - Added `gpt-5.6-sol`, `gpt-5.6-terra`, `gpt-5.6-luna` (1.05M context, reasoning up to `xhigh`)
  - Dropped `gpt-5.5`; new default OpenAI model is `gpt-5.6-terra`
  - Added `MAX` to `ThinkingLevel` / `ThinkingLevelType` in `lib/shared/types.py`
  - Updated `lib/shared/constants.py` and all model docs (README, this file, `docs/`)

### Recent Session (2026-03-09)

**Completed:**
- Regenerated expert pages from template (Git branch footer now visible)
- **Dead code cleanup**: Removed ~525 lines of unused code across 10 files
- **PR created & merged**: https://github.com/fossler/expertgpts-legacy/pull/4

### Current Session (2026-03-22)

**Completed:**
- **Documentation updated to use uv as recommended package manager**:
  - Added uv installation instructions (macOS/Linux/Windows)
  - Updated all run commands to use `uv run`
  - Updated test commands to use `uv run pytest`
  - Updated administrative scripts to use `uv run python`
- **Files updated**:
  - `README.md` - Quick Start and Development sections
  - `CLAUDE.md` - Development Commands section
  - `docs/getting-started/first-use.md` - Running the Application
  - `docs/getting-started/installation.md` - Complete rewrite for uv
  - `docs/getting-started/quickstart.md` - Installation section
  - `docs/development/setup.md` - Development Workflow and Testing

**Previous Session (2026-03-09)**

**Completed:**
- **OpenAI GPT-5.4 model support**: Added new flagship model with 1M context, xhigh reasoning
- Updated model configuration in `lib/shared/constants.py`:
  - Added `gpt-5.4` (1M context, none/low/medium/high/xhigh reasoning)
  - Removed deprecated `gpt-5` and `gpt-5.2` models
  - Changed default OpenAI model to `gpt-5.4`
- Fixed documentation mismatch (docs referenced `o3-mini`, code used `gpt-5` series)
- Updated 8 documentation files with correct model references
- All 49 tests pass with no regressions
- Committed and pushed: commit `217ebdc`

**Next Step:** Commit documentation changes
