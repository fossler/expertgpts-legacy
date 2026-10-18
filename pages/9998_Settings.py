"""Settings page for ExpertGPTs application."""

import io
import os
import subprocess
import sys
import zipfile
from datetime import datetime
from pathlib import Path
import streamlit as st
from lib.config.config_manager import get_config_manager, get_llm_metadata
from lib.shared.page_generator import PageGenerator, is_system_page
from lib.shared.constants import (
    EXPERT_BEHAVIOR_DOCS,
    get_expert_behavior_docs_edit,
    LLM_PROVIDERS,
    get_provider_display_name,
    get_provider_links,
    get_model_display_name,
    get_default_model_for_provider,
    SETTINGS_TAB_PARAM,
)
from lib.ui import create_new_expert, open_add_chat_dialog, render_llm_configuration
from lib.ui.dialogs import render_thinking_mode_ui, render_model_selection
from lib.shared.helpers import (
    sanitize_name,
    translate_expert_name,
    translate_expert_names_batch,
    validate_expert_name,
    validate_api_key,
    render_git_branch_footer,
)
from lib.config import secrets_manager
from lib.config import config_toml_manager
from lib.shared.session_state import (
    initialize_shared_session_state,
    handle_pending_navigation,
    invalidate_expert_cache,
)
from lib.shared.file_ops import safe_path_join, validate_cwd
from lib.ui.logo import theme_logo
from lib.storage import StreamingCache, delete_chat_history


def initialize_session_state():
    """Initialize session state variables."""
    # Initialize shared session state (API key, navigation, etc.)
    initialize_shared_session_state()

    # Handle navigation to newly created expert (after rerun)
    handle_pending_navigation()


def render_api_key_section():
    """Render the multi-provider API Key management section."""
    from lib.i18n import i18n

    st.subheader(i18n.t("api_key.title"), icon=":material/vpn_key:")

    # Provider selection

    # Initialize api_keys in session state if not exists
    if "api_keys" not in st.session_state:
        st.session_state.api_keys = {}

    provider_options = list(LLM_PROVIDERS.keys())
    selected_provider = st.selectbox(
        i18n.t("api_key.select_provider"),
        options=provider_options,
        format_func=lambda x: get_provider_display_name(x),
        key="api_key_provider_selector",
    )

    # Get API keys from session state
    api_keys = st.session_state.api_keys
    current_api_key = api_keys.get(selected_provider, "")

    # Check if key exists in file
    has_file_key = secrets_manager.has_provider_api_key(selected_provider)

    # Current status
    col1, col2 = st.columns(2)

    with col1:
        if has_file_key:
            st.success(
                f"✅ {i18n.t('status.api_key_saved_in_secrets', provider=get_provider_display_name(selected_provider))}"
            )
        else:
            st.info(
                f"💡 {i18n.t('status.no_api_key_in_secrets', provider=get_provider_display_name(selected_provider))}"
            )

    with col2:
        if current_api_key:
            st.success(
                f"✅ {i18n.t('status.api_key_available', provider=get_provider_display_name(selected_provider))}"
            )
        else:
            st.warning(
                f"⚠️ {i18n.t('status.api_key_not_set_warning', provider=get_provider_display_name(selected_provider))}"
            )

    st.divider()

    # API Key input
    api_key = st.text_input(
        i18n.t("forms.api_key"),
        key=f"settings_api_key_{selected_provider}",
        type="password",
        value="",  # Always show empty for security
        help=i18n.t(
            "api_key.enter_key_help",
            provider=get_provider_display_name(selected_provider),
        ),
        placeholder=i18n.t(
            "api_key.enter_key", provider=get_provider_display_name(selected_provider)
        ),
    )

    # Save and Clear buttons
    col1, col2 = st.columns(2)

    with col1:
        if st.button(
            f"💾 {i18n.t('buttons.save_api_key')}",
            type="primary",
            disabled=not api_key,
            key=f"save_{selected_provider}",
        ):
            # Validate API key format before saving
            is_valid, error_msg = validate_api_key(api_key, provider=selected_provider)
            if not is_valid:
                st.error(f"❌ {error_msg}")
            else:
                try:
                    # Save to secrets.toml file
                    secrets_manager.save_provider_api_key(selected_provider, api_key)

                    # Update session state
                    if "api_keys" not in st.session_state:
                        st.session_state.api_keys = {}
                    st.session_state.api_keys[selected_provider] = api_key

                    st.success(f"✅ {i18n.t('success.api_key_saved')}")
                    st.info(f"🔄 {i18n.t('status.application_will_rerun')}")

                    # Rerun to load the new key from st.secrets
                    st.rerun()
                except Exception as e:
                    st.error(
                        f"❌ {i18n.t('errors.error_saving_api_key', error=str(e))}"
                    )

    with col2:
        if st.button(
            f"🗑️ {i18n.t('buttons.clear')}",
            disabled=not has_file_key,
            key=f"clear_{selected_provider}",
        ):
            try:
                # Save empty key to remove it from file
                secrets_manager.save_provider_api_key(selected_provider, "")

                # Clear from session state
                if selected_provider in st.session_state.api_keys:
                    del st.session_state.api_keys[selected_provider]

                st.success(
                    f"✅ {i18n.t('success.api_key_cleared', provider=get_provider_display_name(selected_provider))}"
                )
                st.rerun()
            except Exception as e:
                st.error(f"❌ {i18n.t('errors.error_clearing_api_key', error=str(e))}")

    st.divider()

    # Resources links
    st.subheader(i18n.t("api_key.resources"), icon=":material/library_books:")

    # Provider name and links (one-liner)
    provider_name = get_provider_display_name(selected_provider)
    provider_links_md = get_provider_links(selected_provider)
    st.markdown(f"**{provider_name}:** {provider_links_md}")


def render_default_llm_settings_section():
    """Render the Default LLM Settings section for configuring global defaults."""
    from lib.i18n import i18n

    st.subheader(i18n.t("default_llm.title"), icon=":material/smart_toy:")

    st.caption(i18n.t("default_llm.description"))

    st.divider()

    # Get available providers (only those with API keys configured)
    api_keys = st.session_state.get("api_keys", {})
    available_providers = [p for p in LLM_PROVIDERS.keys() if api_keys.get(p)]

    # Show message if no API keys are configured
    if not available_providers:
        st.warning(f"⚠️ {i18n.t('api_key.no_api_keys_configured')}")
        return

    # Default provider selection (filtered to available providers only)
    current_default_provider = st.session_state.get("default_provider")

    # If current default provider is not available or not set, use first available
    if (
        not current_default_provider
        or current_default_provider not in available_providers
    ):
        current_default_provider = available_providers[0]

    provider_index = available_providers.index(current_default_provider)

    default_provider = st.selectbox(
        i18n.t("default_llm.default_provider"),
        options=available_providers,
        index=provider_index,
        format_func=lambda x: get_provider_display_name(x),
        help=i18n.t("default_llm.default_provider_help"),
        key="default_provider_selector",
    )

    # Update session state when provider changes
    if st.session_state.get("default_provider") != default_provider:
        st.session_state.default_provider = default_provider
        # Update model to match new provider
        new_model = get_default_model_for_provider(default_provider)
        st.session_state.default_model = new_model

    # Default model selection (filtered by provider)
    model_options = list(LLM_PROVIDERS[default_provider]["models"].keys())
    current_default_model = st.session_state.get("default_model")

    # If current default model is not in the new provider's models, use provider default
    if not current_default_model or current_default_model not in model_options:
        current_default_model = get_default_model_for_provider(default_provider)
        st.session_state.default_model = current_default_model

    model_index = (
        model_options.index(current_default_model)
        if current_default_model in model_options
        else 0
    )

    default_model = st.selectbox(
        i18n.t("default_llm.default_model"),
        options=model_options,
        index=model_index,
        format_func=lambda x: get_model_display_name(default_provider, x),
        help=i18n.t(
            "default_llm.default_model_help",
            provider=get_provider_display_name(default_provider),
        ),
        key="default_model_selector",
    )

    # Update session state when model changes
    if st.session_state.get("default_model") != default_model:
        st.session_state.default_model = default_model

    # Default thinking mode (using shared helper, with model-specific efforts)
    current_thinking = st.session_state.get("default_thinking_level", "none")

    # Note: We use "default" label for Settings page context
    default_thinking_level = render_thinking_mode_ui(
        provider=default_provider,
        current_thinking=current_thinking,
        widget_key="default_thinking_selector",
        model=default_model,
        label=f"🧠 {i18n.t('default_llm.thinking_mode') if default_provider == 'zai' else i18n.t('default_llm.select_thinking_mode')}",
        help_text=(
            i18n.t("default_llm.thinking_mode_help")
            if default_provider == "openai"
            else (
                i18n.t("default_llm.thinking_mode_help_zai")
                if default_provider == "zai"
                else None
            )
        ),
        use_sidebar=False,
    )

    # Save defaults button
    if st.button(
        f"💾 {i18n.t('buttons.save_defaults')}", type="primary", key="save_defaults"
    ):
        from lib.config.app_defaults_manager import save_llm_defaults

        # Update session state
        st.session_state.default_provider = default_provider
        st.session_state.default_model = default_model
        st.session_state.default_thinking_level = default_thinking_level

        # Persist to disk
        saved = save_llm_defaults(
            default_provider, default_model, default_thinking_level
        )

        if saved:
            st.success(
                f"✅ {i18n.t('success.defaults_saved', provider=get_provider_display_name(default_provider), model=get_model_display_name(default_provider, default_model))}"
            )
        else:
            st.warning(
                f"⚠️ {i18n.t('success.defaults_saved', provider=get_provider_display_name(default_provider), model=get_model_display_name(default_provider, default_model))}"
            )
            st.caption("ℹ️ Settings saved to session but could not persist to disk.")

        st.rerun()


def render_general_settings_section():
    """Render the General Settings section for theme and language customization."""
    from lib.i18n import i18n

    # Theme Customization
    st.subheader(i18n.t("theme.title"), icon=":material/palette:")

    st.caption(i18n.t("theme.description"))

    st.divider()

    # Load available themes from .streamlit/themes/ directory
    themes = config_toml_manager.load_available_themes()

    # Create theme options with icons (using translated names)
    theme_options = [
        f"{theme['icon']} {i18n.t(f'theme.{name}')}" for name, theme in themes.items()
    ]
    theme_labels = {
        f"{theme['icon']} {i18n.t(f'theme.{name}')}": name
        for name, theme in themes.items()
    }

    # Initialize session state for selected theme KEY (language-independent) and colors
    if "selected_theme_key" not in st.session_state:
        # First, try to get the theme name directly from config.toml base parameter
        current_theme_name = config_toml_manager.get_current_theme_name()

        if current_theme_name and current_theme_name in themes:
            # Found a valid theme name in config.toml
            st.session_state.selected_theme_key = current_theme_name
            st.session_state.theme_primary_color = themes[current_theme_name]["primary"]
            st.session_state.theme_background_color = themes[current_theme_name][
                "background"
            ]
            st.session_state.theme_secondary_background_color = themes[
                current_theme_name
            ]["secondary"]
            st.session_state.theme_text_color = themes[current_theme_name]["text"]
        else:
            # Fallback: Read current theme colors from config file and try to match
            current_config = config_toml_manager.get_theme_settings()

            # Get current colors from config
            current_primary = current_config.get("primaryColor", "#F59E0B")
            current_background = current_config.get("backgroundColor", "#FFFBEB")
            current_secondary = current_config.get(
                "secondaryBackgroundColor", "#FEF3C7"
            )
            current_text = current_config.get("textColor", "#78350F")

            # Try to match current colors against predefined themes
            matched_theme = None
            for theme_key, theme_data in themes.items():
                if theme_key == "custom":
                    continue
                if (
                    theme_data["primary"] == current_primary
                    and theme_data["background"] == current_background
                    and theme_data["secondary"] == current_secondary
                    and theme_data["text"] == current_text
                ):
                    matched_theme = theme_key
                    break

            if matched_theme:
                # Found a matching predefined theme
                st.session_state.selected_theme_key = matched_theme
                st.session_state.theme_primary_color = themes[matched_theme]["primary"]
                st.session_state.theme_background_color = themes[matched_theme][
                    "background"
                ]
                st.session_state.theme_secondary_background_color = themes[
                    matched_theme
                ]["secondary"]
                st.session_state.theme_text_color = themes[matched_theme]["text"]
            else:
                # Use Custom theme with current config values
                st.session_state.selected_theme_key = "custom"
                st.session_state.theme_primary_color = current_primary
                st.session_state.theme_background_color = current_background
                st.session_state.theme_secondary_background_color = current_secondary
                st.session_state.theme_text_color = current_text

    # Get the current display name for the selected theme key (in current language)
    current_theme_display = f"{themes[st.session_state.selected_theme_key]['icon']} {i18n.t(f'theme.{st.session_state.selected_theme_key}')}"

    # Radio button for theme selection (outside form for reactivity)
    selected_theme = st.radio(
        i18n.t("theme.select_theme"),
        options=theme_options,
        index=theme_options.index(current_theme_display),
        horizontal=True,
        key="theme_radio_selector",
    )

    # Extract theme name from selected option
    theme_name = theme_labels[selected_theme]
    theme_colors = themes[theme_name]

    # Update session state and rerun if selection changed
    if theme_name != st.session_state.selected_theme_key:
        st.session_state.selected_theme_key = theme_name
        # Update color values in session state
        st.session_state.theme_primary_color = theme_colors["primary"]
        st.session_state.theme_background_color = theme_colors["background"]
        st.session_state.theme_secondary_background_color = theme_colors["secondary"]
        st.session_state.theme_text_color = theme_colors["text"]
        st.rerun()

    st.divider()

    # Color Preview section (outside form for reactivity)
    st.markdown(f"### {i18n.t('forms.color_preview')}")

    # Check if Custom theme is selected
    is_custom_theme = theme_name == "custom"

    # Create columns for color inputs in one row
    col1, col2, col3, col4 = st.columns(4)

    with col1:
        primary_color = st.color_picker(
            i18n.t("forms.buttons_elements"),
            value=st.session_state.theme_primary_color,
            help=i18n.t("theme.buttons_elements_help"),
            key=f"primary_{st.session_state.selected_theme_key}",
            disabled=not is_custom_theme,
        )

    with col2:
        background_color = st.color_picker(
            i18n.t("forms.background_color"),
            value=st.session_state.theme_background_color,
            help=i18n.t("theme.background_help"),
            key=f"background_{st.session_state.selected_theme_key}",
            disabled=not is_custom_theme,
        )

    with col3:
        secondary_background_color = st.color_picker(
            i18n.t("forms.secondary_background"),
            value=st.session_state.theme_secondary_background_color,
            help=i18n.t("theme.secondary_background_help"),
            key=f"secondary_{st.session_state.selected_theme_key}",
            disabled=not is_custom_theme,
        )

    with col4:
        text_color = st.color_picker(
            i18n.t("forms.text_color"),
            value=st.session_state.theme_text_color,
            help=i18n.t("theme.text_help"),
            key=f"text_{st.session_state.selected_theme_key}",
            disabled=not is_custom_theme,
        )

    # Update session state with current color picker values
    st.session_state.theme_primary_color = primary_color
    st.session_state.theme_background_color = background_color
    st.session_state.theme_secondary_background_color = secondary_background_color
    st.session_state.theme_text_color = text_color

    st.divider()

    # Check if we need to reload page (from Save & Apply button)
    # Note: We use switch_page() instead of rerun() because Streamlit only reads
    # config.toml on page load, not on rerun. This forces a complete page reload.
    if st.session_state.get("trigger_page_reload", False):
        st.session_state.trigger_page_reload = False
        # Switch to current page to force complete reload (re-reads config.toml)
        st.switch_page("pages/9998_Settings.py")

    # Single button to save and apply theme settings
    col1, col2, col3 = st.columns([2, 2, 4])

    def save_and_apply_theme():
        """Callback to save theme settings to config.toml and force page reload."""
        try:
            if st.session_state.selected_theme_key == "custom":
                # Custom theme: update custom.toml file and save base path
                primary_key = f"primary_{st.session_state.selected_theme_key}"
                background_key = f"background_{st.session_state.selected_theme_key}"
                secondary_key = f"secondary_{st.session_state.selected_theme_key}"
                text_key = f"text_{st.session_state.selected_theme_key}"

                # Update custom.toml with new colors
                config_toml_manager.update_custom_theme(
                    primaryColor=st.session_state[primary_key],
                    backgroundColor=st.session_state[background_key],
                    secondaryBackgroundColor=st.session_state[secondary_key],
                    textColor=st.session_state[text_key],
                )
                # Save base path to config.toml
                config_toml_manager.save_theme_settings(
                    base=".streamlit/themes/custom.toml"
                )
            else:
                # Predefined theme: just save base path
                theme_file = (
                    f".streamlit/themes/{st.session_state.selected_theme_key}.toml"
                )
                config_toml_manager.save_theme_settings(base=theme_file)

            # Set flag to trigger page reload (not rerun!)
            st.session_state.trigger_page_reload = True

            # Show success toast
            st.toast(f"✅ {i18n.t('status.theme_saved_reloading')}", icon="🎨")
        except Exception as e:
            st.error(f"❌ {i18n.t('errors.error', error=str(e))}")

    with col1:
        if st.button(
            f"💾 {i18n.t('buttons.save_apply_theme')}",
            key="save_apply_button",
            on_click=save_and_apply_theme,
            type="primary",
        ):
            pass

    with col2:
        st.empty()  # Spacer

    with col3:
        st.empty()  # Spacer

    st.divider()

    # Language selector
    st.subheader(i18n.t("language.title"), icon=":material/language:")

    # Get current language
    current_lang = st.session_state.get("language", "en")
    current_info = i18n.get_language_info(current_lang)

    # Display current language
    st.caption(
        f"{i18n.t('language.current_language')}: {current_info['flag']} {current_info['native_name']}"
    )

    st.divider()

    # Group languages by script for better UX
    latin_langs = ["en", "de", "fr", "es", "it", "pt", "tr", "id", "ms"]
    cyrillic_langs = ["ru"]
    han_langs = ["zh-CN", "zh-TW", "wyw", "yue"]

    # Latin Script Languages
    st.write(f"**{i18n.t('language.latin_script')}**")
    cols_latin = st.columns(3)
    for idx, code in enumerate(latin_langs):
        info = i18n.get_language_info(code)
        with cols_latin[idx % 3]:
            if st.button(
                f"{info['flag']} {info['native_name']}",
                key=f"lang_{code}",
                width="stretch",
                type="secondary" if code != current_lang else "primary",
            ):
                i18n.set_language(code)

    # Cyrillic Script Languages
    st.write(f"**{i18n.t('language.cyrillic_script')}**")
    cols_cyrillic = st.columns(3)
    for idx, code in enumerate(cyrillic_langs):
        info = i18n.get_language_info(code)
        with cols_cyrillic[idx]:
            if st.button(
                f"{info['flag']} {info['native_name']}",
                key=f"lang_{code}",
                width="stretch",
                type="secondary" if code != current_lang else "primary",
            ):
                i18n.set_language(code)

    # Chinese (Han Script) Languages
    st.write(f"**{i18n.t('language.han_script')}**")
    cols_han = st.columns(2)
    for idx, code in enumerate(han_langs):
        info = i18n.get_language_info(code)
        with cols_han[idx % 2]:
            if st.button(
                f"{info['flag']} {info['native_name']}",
                key=f"lang_{code}",
                width="stretch",
                type="secondary" if code != current_lang else "primary",
            ):
                i18n.set_language(code)


def open_edit_expert_dialog(expert_id: str) -> None:
    """Open the Edit Expert dialog for an expert as a modal.

    Args:
        expert_id: Unique expert identifier
    """
    from lib.i18n import i18n

    try:
        expert_config = get_config_manager().load_config(expert_id)
    except FileNotFoundError:
        st.error(f"❌ {i18n.t('errors.expert_not_found', expert_id=expert_id)}")
        return

    translated_name = translate_expert_name(expert_config["expert_name"])
    st.dialog(
        i18n.t("dialogs.edit_expert.title", name=translated_name),
        width="large",
        icon=":material/edit:",
        dismissible=False,
    )(_render_edit_expert_dialog)(expert_id, expert_config)


def _render_edit_expert_dialog(expert_id: str, expert_config: dict) -> None:
    """Render the body of the Edit Expert dialog.

    This dialog allows users to edit an existing expert agent.
    Expert ID cannot be changed.

    Args:
        expert_id: Unique expert identifier
        expert_config: The expert's configuration, loaded when the dialog opened
    """
    from lib.i18n import i18n

    config_manager = get_config_manager()

    # LLM Configuration (Provider, Model, Temperature, Thinking)
    current_provider, current_model, current_thinking = get_llm_metadata(expert_config)
    current_temperature = expert_config.get("temperature", 1.0)

    provider, model, temperature, thinking_level = render_llm_configuration(
        current_provider=current_provider,
        current_model=current_model,
        current_temperature=current_temperature,
        current_thinking=current_thinking,
        show_thinking=True,
    )

    st.divider()

    with st.form("edit_expert_form"):
        st.subheader(i18n.t("dialogs.add_chat.expert_configuration"))

        # Expert ID (read-only)
        st.text_input(
            i18n.t("forms.expert_id"),
            value=expert_config["expert_id"],
            disabled=True,
            help=i18n.t("dialogs.edit_expert.expert_id_help"),
        )

        st.divider()

        # Expert Name
        chat_name = st.text_input(
            f"{i18n.t('forms.expert_name')} *",
            value=expert_config["expert_name"],
            help=i18n.t("dialogs.add_chat.help_expert_name"),
            max_chars=100,
        ).strip()

        # Add caption with allowed characters
        st.caption(
            f"💡 **{i18n.t('forms.allowed_characters')}:** {i18n.t('forms.allowed_characters_desc')}"
        )

        # Agent Description
        description = st.text_area(
            f"{i18n.t('forms.agent_description')} *",
            value=expert_config["description"],
            help=i18n.t("dialogs.add_chat.help_expert_description"),
            height="content",
            max_chars=1000,
        ).strip()

        st.divider()

        # Get provider from expert config
        metadata = expert_config.get("metadata", {})
        expert_provider = metadata.get("provider", "deepseek")  # Backward compatible

        # Expert Behavior (Advanced) - The most important field!
        st.subheader(
            i18n.t("dialogs.add_chat.expert_behavior_title"),
            icon=":material/psychology_alt:",
        )

        # Check if API key available for this expert's provider
        api_keys = st.session_state.get("api_keys", {})
        api_key_available = bool(api_keys.get(expert_provider, ""))

        if api_key_available:
            caption_text = f"💡 {i18n.t('dialogs.edit_expert.ai_powered_regeneration')}"
        else:
            caption_text = (
                f"💡 {i18n.t('dialogs.edit_expert.manual_mode_regeneration')}"
            )

        st.caption(caption_text)

        custom_system_prompt = st.text_area(
            i18n.t("forms.custom_system_prompt"),
            value=expert_config.get("system_prompt", ""),
            height=250,
            help=i18n.t("dialogs.add_chat.help_custom_behavior"),
            max_chars=3000,
        ).strip()

        # Inform users about automatic language response
        st.caption(f"💡 {i18n.t('info.language_prefix_auto')}")

        # Add expander with examples
        with st.expander(f"📖 {i18n.t('dialogs.add_chat.why_important_title')}"):
            st.markdown(get_expert_behavior_docs_edit())

        st.caption(i18n.t("info.required_fields_hint"))

        # Form buttons (left-aligned)
        st.write("")  # Spacing
        col1, col2, col3 = st.columns([1, 1, 6])

        with col1:
            submit_button = st.form_submit_button(
                i18n.t("buttons.save_changes"), type="primary"
            )

        with col2:
            cancel_button = st.form_submit_button(i18n.t("buttons.cancel"))

        # Handle form submission
        if submit_button:
            if not chat_name or not description:
                st.error(i18n.t("errors.required_fields"))
                return

            is_valid, error_msg = validate_expert_name(chat_name)
            if not is_valid:
                st.error(f"❌ {error_msg}")
                return

            try:
                # Determine if we need AI generation
                # Empty string means "regenerate with AI" (if API key available)
                # None means "keep existing"
                final_system_prompt = custom_system_prompt

                if custom_system_prompt == "" and api_key_available:
                    # User cleared the field - trigger AI regeneration
                    final_system_prompt = None

                elif custom_system_prompt == "" and not api_key_available:
                    # No API key - keep existing prompt
                    final_system_prompt = expert_config.get("system_prompt", "")

                # Get API key for AI generation (provider-specific)
                api_key = (
                    api_keys.get(expert_provider, None) if api_key_available else None
                )

                # Update the config
                config_manager.update_config(
                    expert_id,
                    {
                        "expert_name": chat_name,
                        "description": description,
                        "temperature": temperature,
                        "system_prompt": final_system_prompt,
                        "api_key": api_key,
                        "provider": provider,
                        "model": model,
                        "thinking_level": thinking_level,
                    },
                )

                # Invalidate cache for this expert (using shared helper)
                invalidate_expert_cache(expert_id)

                st.toast(i18n.t("status.expert_updated", name=chat_name), icon="✅")

                # Rerun closes the dialog and refreshes the expert list
                st.rerun()

            except Exception as e:
                st.error(f"❌ {i18n.t('errors.error_updating_expert', error=str(e))}")

        if cancel_button:
            st.rerun()


def render_expert_management_section():
    """Render the Expert Management section."""
    from lib.i18n import i18n

    st.subheader(i18n.t("experts.management.title"), icon=":material/manage_accounts:")

    # Check if ANY provider API key is available
    api_keys = st.session_state.get("api_keys", {})
    api_key_available = any(api_keys.values())

    if api_key_available:
        if st.button(
            f"➕ {i18n.t('buttons.add_new_chat')}", type="primary", width="content"
        ):
            open_add_chat_dialog()
    else:
        st.button(
            f"➕ {i18n.t('buttons.add_new_chat')}",
            type="primary",
            width="content",
            disabled=True,
            help=i18n.t("info.set_api_key_to_create"),
        )
        st.caption(f"⚠️ {i18n.t('info.set_api_key_to_create')}")

    st.divider()

    # Load experts (not cached to avoid tab switching issues)
    config_manager = get_config_manager()
    experts = config_manager.list_experts_lightweight()

    if not experts:
        st.info(f"🔍 {i18n.t('info.create_first_expert')}")
        return

    st.caption(i18n.t("status.found_experts", count=len(experts)))

    # Batch translate expert names (cached for 5 minutes)
    from lib.i18n import i18n as i18n_instance

    expert_names_tuple = tuple(e["expert_name"] for e in experts)
    name_translations = translate_expert_names_batch(
        expert_names_tuple, i18n_instance.current_language
    )

    # Display experts in a table
    for idx, expert in enumerate(experts):
        # Get provider and model info
        provider, model, thinking_level = get_llm_metadata(expert)

        provider_name = get_provider_display_name(provider)
        model_name = get_model_display_name(provider, model)

        # Translate expert name for display
        translated_name = name_translations[expert["expert_name"]]

        with st.expander(f"📝 {translated_name}", expanded=False):
            col1, col2 = st.columns([3, 1])

            with col1:
                # Show provider/model info
                st.markdown(f"**LLM:** {provider_name} - {model_name}")
                # Show thinking mode status
                if provider == "openai" and thinking_level != "none":
                    st.caption(
                        f"🧠 {i18n.t('experts.management.reasoning_effort', level=thinking_level.capitalize())}"
                    )
                elif thinking_level != "none":
                    st.caption(
                        f"🧠 {i18n.t('experts.management.thinking_mode_enabled')}"
                    )
                st.markdown(f"**Temperature:** `{expert['temperature']}`")
                st.markdown(f"**{i18n.t('experts.management.description_label')}:**")
                st.text_area(
                    i18n.t("experts.management.description_label"),
                    value=expert["description"],
                    height=None,
                    disabled=True,
                    key=f"desc_preview_{expert['expert_id']}",
                    label_visibility="collapsed",
                )

                # Show expert behavior
                system_prompt = expert.get("system_prompt", "")
                if system_prompt:
                    st.markdown(
                        f"**🧠 {i18n.t('experts.management.expert_behavior')}:**"
                    )
                    # Show explanatory message about language behavior
                    st.caption(f"💡 **{i18n.t('info.language_behavior_explanation')}**")
                    # Display as read-only text area preview
                    st.text_area(
                        i18n.t("experts.management.expert_behavior"),
                        value=system_prompt,
                        height=None,
                        disabled=True,
                        key=f"preview_{expert['expert_id']}",
                        label_visibility="collapsed",
                    )
                else:
                    st.markdown(
                        f"**🧠 {i18n.t('experts.management.expert_behavior')}:** {i18n.t('info.expert_behavior_auto')}"
                    )
                    # Show explanatory message about language behavior
                    st.caption(f"💡 **{i18n.t('info.language_behavior_explanation')}**")

            with col2:
                st.markdown(f"**{i18n.t('experts.management.actions')}**")
                edit_key = f"edit_{expert['expert_id']}"
                if st.button(
                    f"✏️ {i18n.t('buttons.edit')}", key=edit_key, width="stretch"
                ):
                    open_edit_expert_dialog(expert["expert_id"])

                delete_key = f"delete_{expert['expert_id']}"
                if st.button(
                    f"🗑️ {i18n.t('buttons.delete')}", key=delete_key, width="stretch"
                ):
                    open_delete_expert_dialog(expert)


def open_delete_expert_dialog(expert: dict) -> None:
    """Open the confirmation dialog for deleting an expert.

    Args:
        expert: Expert entry from ``list_experts_lightweight()``
    """
    from lib.i18n import i18n

    st.dialog(i18n.t("buttons.delete"), icon=":material/delete:", dismissible=False)(
        _render_delete_expert_dialog
    )(expert)


def _render_delete_expert_dialog(expert: dict) -> None:
    """Render the body of the delete confirmation dialog.

    Args:
        expert: Expert entry from ``list_experts_lightweight()``
    """
    from lib.i18n import i18n

    expert_id = expert["expert_id"]
    translated_name = translate_expert_name(expert["expert_name"])
    st.warning(f"⚠️ {i18n.t('experts.management.confirm_delete', name=translated_name)}")

    with st.container(horizontal=True):
        confirm = st.button(
            f"✅ {i18n.t('buttons.yes_delete')}",
            key=f"confirm_{expert_id}",
            type="primary",
        )
        cancel = st.button(f"❌ {i18n.t('buttons.cancel')}", key=f"cancel_{expert_id}")

    if cancel:
        st.rerun()

    if confirm:
        try:
            # Delete the config, the page, the chat history (incl. images)
            # and any leftover streaming cache
            get_config_manager().delete_config(expert_id)
            PageGenerator().delete_page(expert_id)
            delete_chat_history(expert_id)
            StreamingCache(expert_id).cleanup()

            # Clear all session state of this expert (cache version, messages, ...)
            keys_to_delete = [
                key for key in st.session_state.keys() if expert_id in str(key)
            ]
            for key in keys_to_delete:
                del st.session_state[key]

            st.toast(i18n.t("success.expert_deleted", name=translated_name), icon="✅")
            # Rerun closes the dialog and refreshes the expert list
            st.rerun()

        except Exception as e:
            st.error(f"❌ {i18n.t('errors.error_deleting_expert', error=str(e))}")


def get_configs_as_zip():
    """Create a zip file containing all expert configurations.

    Returns:
        bytes: Zip file content as bytes
    """
    configs_dir = Path(__file__).parent.parent / "configs"

    # Create a zip file in memory
    zip_buffer = io.BytesIO()

    with zipfile.ZipFile(zip_buffer, "w", zipfile.ZIP_DEFLATED) as zip_file:
        if configs_dir.exists():
            for config_file in configs_dir.glob("*.yaml"):
                # Add each config file to the zip
                zip_file.write(config_file, config_file.name)

    # Reset buffer position to the beginning
    zip_buffer.seek(0)

    return zip_buffer.getvalue()


def render_danger_zone_section():
    """Render the Danger Zone section for destructive actions."""
    from lib.i18n import i18n

    st.subheader(i18n.t("danger_zone.title"), icon=":material/warning:")

    st.warning(f"⚠️ **{i18n.t('danger_zone.warning')}**")

    # Download configs section
    st.markdown("---")
    st.subheader(i18n.t("danger_zone.backup_title"), icon=":material/backup:")

    st.markdown(i18n.t("danger_zone.backup_description"))

    # Get the zip file content
    config_zip = get_configs_as_zip()

    # Generate timestamped filename
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    filename = f"expertgpts_configs_{timestamp}.zip"

    # Download button
    st.download_button(
        label=f"📥 {i18n.t('danger_zone.download_button')}",
        data=config_zip,
        file_name=filename,
        mime="application/zip",
        width="content",
    )

    st.markdown("---")

    st.markdown(i18n.t("danger_zone.reset_description"))

    if st.button(
        f"🔄 {i18n.t('danger_zone.reset_button')}", type="primary", width="content"
    ):
        open_reset_dialog()


def open_reset_dialog() -> None:
    """Open the final confirmation dialog for resetting the application."""
    from lib.i18n import i18n

    st.dialog(
        i18n.t("danger_zone.reset_button"),
        icon=":material/warning:",
        dismissible=False,
    )(_render_reset_dialog)()


def _render_reset_dialog() -> None:
    """Render the body of the reset confirmation dialog."""
    from lib.i18n import i18n

    st.error(f"🚨 **{i18n.t('danger_zone.final_warning')}**")

    with st.container(horizontal=True):
        confirm = st.button(
            f"✅ {i18n.t('buttons.yes_reset_everything')}",
            key="confirm_reset_button",
            type="primary",
        )
        cancel = st.button(f"❌ {i18n.t('buttons.cancel')}", key="cancel_reset_button")

    if cancel:
        st.rerun()

    if confirm:
        try:
            # Delete all configs (with path validation)
            configs_dir = Path(__file__).parent.parent / "configs"
            if configs_dir.exists():
                for config_file in configs_dir.glob("*.yaml"):
                    # Validate the config file path is safe before deletion
                    safe_config_path = safe_path_join(configs_dir, config_file.name)
                    if safe_config_path.exists():
                        safe_config_path.unlink()

            # Delete all expert pages, preserving system pages (Home,
            # Settings, Help) and any hidden "_"-prefixed page (e.g.
            # _debug.py). is_system_page() is the single source of truth.
            pages_dir = Path(__file__).parent
            if pages_dir.exists():
                for page_file in pages_dir.glob("*.py"):
                    if not is_system_page(page_file.name):
                        # Validate the page file path is safe before deletion
                        safe_page_path = safe_path_join(pages_dir, page_file.name)
                        if safe_page_path.exists():
                            safe_page_path.unlink()

            # Recreate example experts using scripts/setup.py
            st.info(f"🔄 {i18n.t('status.recreating_experts')}")

            # Validate working directory before subprocess execution
            project_root = Path(__file__).parent.parent
            safe_cwd = validate_cwd(project_root)

            # Run scripts/setup.py as a subprocess
            result = subprocess.run(
                [sys.executable, "scripts/setup.py"],
                check=True,
                capture_output=True,
                text=True,
                cwd=safe_cwd,
            )

            st.toast(i18n.t("success.application_reset"), icon="✅")
            # Rerun closes the dialog and reloads the recreated experts
            st.rerun()

        except subprocess.CalledProcessError as e:
            st.error(f"❌ {i18n.t('errors.error_recreating_experts', error=str(e))}")
            if e.stdout:
                st.error(f"Output: {e.stdout}")
            if e.stderr:
                st.error(f"Error: {e.stderr}")
        except Exception as e:
            st.error(f"❌ {i18n.t('errors.error_resetting_application', error=str(e))}")


def render_about_section():
    """Render the About section."""
    from lib.i18n import i18n

    st.subheader(i18n.t("about.title"), icon=":material/info:")

    # The logo replaces the "ExpertGPTs" heading
    logo, _ = theme_logo()
    st.image(logo, width=260)

    st.markdown(f"""
    {i18n.t("about.description")}

    **{i18n.t("about.version")}**

    **{i18n.t("about.features_title")}:**
    - 🤖 {i18n.t("about.feature_multiple_experts")}
    - 🔄 {i18n.t("about.feature_multi_provider")}
    - ✨ {i18n.t("about.feature_ai_prompts")}
    - 🌍 {i18n.t("about.feature_internationalization")}
    - 📝 {i18n.t("about.feature_template_architecture")}
    - 🎨 {i18n.t("about.feature_theme_customization")}
    - 💾 {i18n.t("about.feature_chat_history")}
    - ⚙️ {i18n.t("about.feature_temperature")}
    - 🚀 {i18n.t("about.feature_modern_navigation")}
    - 📂 {i18n.t("about.feature_file_config")}

    ### {i18n.t("about.development")}
    """)

    # Display z.ai icon and link
    col1, col2 = st.columns([1, 6])
    with col1:
        # Read the SVG file and embed as data URL
        import base64
        from pathlib import Path

        icon_path = Path("icons/zai_logo.svg")
        if icon_path.exists():
            with open(icon_path, "rb") as f:
                svg_data = f.read().decode("utf-8")
            # Encode SVG as base64 data URL
            svg_base64 = base64.b64encode(svg_data.encode("utf-8")).decode("utf-8")
            data_url = f"data:image/svg+xml;base64,{svg_base64}"

            # Make the icon clickable
            st.markdown(
                f'<a href="https://z.ai/subscribe?ic=JGTYCX7ZO7" target="_blank">'
                f'<img src="{data_url}" width="100"></a>',
                unsafe_allow_html=True,
            )
        else:
            # Fallback to non-clickable image if file not found
            st.image("icons/zai_logo.svg", width=100)

        st.markdown(i18n.t("about.developed_with"))
    with col2:
        st.empty()

    st.markdown(f"""
    ### {i18n.t("about.resources")}
    """)
    st.markdown(
        "[![Open in GitHub Codespaces](https://github.com/codespaces/badge.svg)](https://codespaces.new/fossler/expertgpts-legacy)"
    )

    st.markdown(f"""
    ### {i18n.t("about.support")}
    """)

    # Buy Me a Coffee button
    st.markdown(
        '<div style="display: inline-block; width: fit-content;">'
        '<a href="https://www.buymeacoffee.com/MirzetKadic" target="_blank">'
        '<img src="https://cdn.buymeacoffee.com/buttons/v2/default-yellow.png" '
        'alt="Buy Me A Coffee" '
        'style="height: auto; width: 270px; border-radius: 5px; min-width: 0 !important; max-width: 270px !important;"></a>'
        "</div>",
        unsafe_allow_html=True,
    )


# Settings sections in display order: URL key -> (Material icon, i18n key, renderer).
# The URL key (?tab=<key>) is language independent, unlike the labels.
SETTINGS_SECTIONS = {
    "general": (
        "palette",
        "settings.sections.general",
        render_general_settings_section,
    ),
    "api_key": ("vpn_key", "settings.sections.api_key", render_api_key_section),
    "default_llm": (
        "smart_toy",
        "settings.sections.default_llm",
        render_default_llm_settings_section,
    ),
    "experts": (
        "manage_accounts",
        "settings.sections.expert_management",
        render_expert_management_section,
    ),
    "danger_zone": (
        "warning",
        "settings.sections.danger_zone",
        render_danger_zone_section,
    ),
    "about": ("info", "settings.sections.about", render_about_section),
}
DEFAULT_SECTION = "general"


def _store_section_in_url() -> None:
    """Write the selected section to the URL (removed for the default section)."""
    section = st.session_state.settings_section
    if section == DEFAULT_SECTION:
        st.query_params.pop(SETTINGS_TAB_PARAM, None)
    else:
        st.query_params[SETTINGS_TAB_PARAM] = section


def main():
    """Main settings page entry point."""
    initialize_session_state()

    from lib.i18n import i18n

    st.title(i18n.t("settings.title"), icon=":material/settings:")

    # The URL selects the section (?tab=api_key): deep links, reloads and
    # browser back/forward. Unknown values fall back to the default section.
    section = st.query_params.get(SETTINGS_TAB_PARAM, DEFAULT_SECTION)
    if section not in SETTINGS_SECTIONS:
        st.query_params.pop(SETTINGS_TAB_PARAM, None)
        section = DEFAULT_SECTION
    st.session_state.settings_section = section

    section = st.segmented_control(
        "Settings Sections",
        options=list(SETTINGS_SECTIONS),
        format_func=lambda key: (
            f":material/{SETTINGS_SECTIONS[key][0]}: {i18n.t(SETTINGS_SECTIONS[key][1])}"
        ),
        label_visibility="collapsed",
        key="settings_section",
        on_change=_store_section_in_url,
        required=True,
    )

    # Render only the active section
    SETTINGS_SECTIONS[section][2]()

    # Footer
    st.divider()

    # Git branch footer in sidebar (at very bottom)
    render_git_branch_footer()


if __name__ == "__main__":
    main()
