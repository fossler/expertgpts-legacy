"""ExpertGPTs - Multi-Expert AI Chat Application.

A Streamlit application that provides access to multiple domain-specific
expert AI agents powered by DeepSeek API.

This is the main entry point using the newer st.navigation() approach.
"""

import sys
import subprocess
import urllib.parse
import streamlit as st
from pathlib import Path
from lib.shared.page_generator import PageGenerator
from lib.shared.session_state import (
    initialize_shared_session_state,
    handle_pending_navigation,
)
from lib.shared.constants import EXAMPLE_EXPERTS_COUNT
from lib.i18n import i18n
from lib.shared.helpers import translate_expert_name
from lib.shared.file_ops import validate_cwd
from lib.ui.logo import theme_logo


def check_first_run():
    """Check if this is a first run (no expert pages exist).

    Returns True if setup should be run.
    """
    pages_dir = Path(__file__).parent / "pages"

    # Check if expert pages exist (excluding Home, Settings, and Help)
    if pages_dir.exists():
        expert_pages = [
            f
            for f in pages_dir.glob("*.py")
            if f.name not in ["1000_Home.py", "9998_Settings.py", "9999_Help.py"]
            and not f.name.startswith("_")
        ]
        return len(expert_pages) == 0

    return True


def run_first_time_setup():
    """Run first-time setup by calling scripts/setup.py."""
    project_root = Path(__file__).parent

    st.info("""
    🚀 **First Run Detected**

    Setting up ExpertGPTs with example expert agents...
    This will only happen once.
    """)

    try:
        # Validate working directory before subprocess execution
        safe_cwd = validate_cwd(project_root)

        result = subprocess.run(
            [sys.executable, "scripts/setup.py"],
            cwd=safe_cwd,
            check=True,
            capture_output=True,
            text=True,
        )

        st.success("✅ Setup complete! Refreshing...")
        st.rerun()

    except subprocess.CalledProcessError as e:
        st.error(f"""
        ❌ **Setup Failed**

        {e.stderr}

        Please run manually: `uv run python scripts/setup.py`
        """)


def initialize_session_state():
    """Initialize session state variables before navigation."""
    # Initialize shared session state (API key, etc.)
    initialize_shared_session_state()


def main():
    """Main application entry point using st.navigation()."""

    logo, icon = theme_logo()

    # Set page configuration (must be first st command)
    st.set_page_config(
        page_title="ExpertGPTs",
        page_icon=icon,
        layout="wide",
        initial_sidebar_state=320,
    )

    # Check for first run (before navigation)
    if check_first_run():
        run_first_time_setup()
        return  # Wait for rerun after setup

    # Initialize session state before navigation
    initialize_session_state()

    # Logo above the navigation; only the icon when the sidebar is collapsed
    st.logo(logo, size="large", icon_image=icon)

    # Define the home page with icon
    home = st.Page(
        "pages/1000_Home.py", title=i18n.t("nav.home"), icon=":material/smart_toy:"
    )

    # Define Settings page
    settings = st.Page(
        "pages/9998_Settings.py",
        title=i18n.t("nav.settings"),
        icon=":material/settings:",
    )

    # Define Help page
    help_page = st.Page(
        "pages/9999_Help.py",
        title=i18n.t("nav.help", default="Help"),
        icon=":material/menu_book:",
    )

    # Dynamically load all expert pages
    page_generator = PageGenerator()
    page_list = page_generator.list_pages()

    # Create page objects for each expert
    expert_pages = []
    for page_info in page_list:
        page_path = Path("pages") / page_info["filename"]

        # Skip if page file doesn't exist (may have been deleted)
        if not page_path.exists():
            continue

        # Get expert name for navigation (with translation for default experts)
        expert_id = page_info["expert_id"]
        expert_name = page_info["expert_name"]

        # Translate default expert names if available
        translated_name = translate_expert_name(expert_name)

        expert_pages.append(
            st.Page(
                str(page_path), title=translated_name, icon=":material/psychology_alt:"
            )
        )

    # Create page list: Home + Experts + Settings + Help
    pages = [home] + expert_pages + [settings, help_page]

    # Debug page: routable only via the /debug URL, never linked in nav.
    # st.navigation only shows (and routes to) pages in the list, so we add the
    # debug page exclusively when the browser is already on /debug.
    # Guard on file existence: the debug page is optional and may be absent
    # (fresh clone that didn't sync it, a deploy that strips "_" files, etc.).
    # A missing hidden page must not crash the whole app, unlike the mandatory
    # Home/Settings/Help pages which are intentionally created unconditionally.
    current_path = urllib.parse.urlparse(st.context.url).path.rstrip("/")
    debug_page_path = Path(__file__).parent / "pages" / "_debug.py"
    if current_path.endswith("/debug") and debug_page_path.exists():
        pages.append(
            st.Page(
                "pages/_debug.py",
                title="Debug",
                icon=":material/bug_report:",
                url_path="debug",
            )
        )

    # Set up navigation
    pg = st.navigation(pages)

    # Handle navigation to newly created expert (after rerun)
    # Must be called after st.navigation() is set up
    handle_pending_navigation()

    # Run the selected page
    pg.run()


if __name__ == "__main__":
    main()
