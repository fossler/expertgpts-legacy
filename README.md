<p align="center">
  <img src="docs/assets/expertgpts-logo-dark.jpg" alt="ExpertGPTs legacy logo" width="320">
</p>

# ExpertGPTs

A multi-expert AI chat application built with Streamlit, providing access to domain-specific AI experts with support for multiple LLM providers, full internationalization, and persistent chat history.

![ExpertGPTs App Screenshot](docs/assets/expertgps_app.png)

## Overview

ExpertGPTs is a powerful AI chat interface that lets you create and interact with specialized AI experts. Each expert has deep knowledge in specific domains—from Python programming to career coaching—and maintains independent conversation history. Switch between LLM providers (DeepSeek, OpenAI, Z.AI, KIMI) per expert, customize responses with temperature controls, and enjoy a fully internationalized interface supporting 14 languages.

## Key Features

- **🤖 Multiple Expert Agents** - Chat with domain-specific AI experts, each specialized in different areas
- **🔄 Multi-Provider Support** - Choose between DeepSeek, OpenAI, Z.AI (with free models) and KIMI per expert
- **✨ AI-Generated System Prompts** - Let the LLM craft expert prompts from your description—no prompt engineering required
- **🌍 Full Internationalization** - 14 languages with automatic detection and AI language response
- **📝 Template-Based Architecture** - Consistent UI/UX across all experts with easy customization
- **🎨 Theme Customization** - Personalize colors and appearance with preset themes
- **💾 Persistent Chat History** - Conversations saved automatically per expert
- **📎 File & Image Attachments** - Attach text files (code, Markdown, CSV, JSON, logs, ...) and images (PNG, JPEG, WebP, GIF, up to 5 MB; for models with image support) to a message via the toolbox below the chat input
- **🎤 Voice Input** - Record a voice message in the toolbox; it is transcribed (OpenAI experts: `gpt-transcribe`, all others: Z.AI `glm-asr-2512`) and sent automatically
- **📊 Context Usage** - See how much of the model's context window a chat uses, right in the toolbox below the chat input
- **⚙️ Adjustable Temperature** - Control response creativity (0.0-2.0, range depends on the provider) for each expert
- **🚀 Modern Navigation** - Material Design icons using Streamlit's st.navigation() API
- **📂 File-Based Configuration** - Each expert has its own YAML config for easy management

## Tech Stack

| Category | Technology | Purpose |
|----------|------------|---------|
| **Framework** | [Streamlit](https://streamlit.io/) 1.65 | Web application framework |
| **Languages** | Python 3.13+ | Primary development language |
| **Packaging** | [uv](https://docs.astral.sh/uv/) (`pyproject.toml`, `uv.lock`) | Dependency management |

## Code Hosting

- **GitHub**: [https://github.com/fossler/expertgpts-legacy](https://github.com/fossler/expertgpts-legacy) (primary)

## Pay Only for What You Use: The Economic and Strategic Advantages of API-Based AI Chats

API-based AI chats operate on a **pay-as-you-go (PAYG)** model—meaning you pay **only for actual usage**, not for access. There are no fixed monthly fees, no long-term commitments, and no costs when the service isn't used. This makes PAYG inherently more transparent, flexible, and cost-efficient than traditional subscription models.

### Why PAYG Is Often Significantly Cheaper Than Flat-Rate Subscriptions

**FREE Models Available**
Some providers even offer completely **free models**! Z.AI provides GLM-4.7-Flash at zero cost—no charges for input, output, or storage. This is perfect for experimentation, learning, or everyday tasks without any financial commitment.

**Full Cost Transparency & Control**
Spending scales directly with usage. You decide how much you pay simply by how much you use the system.

**Perfect for Variable Demand**
Whether usage is sporadic or comes in bursts, PAYG adapts instantly. You never overpay during low-usage periods.

**Concrete Cost Example**
Around **180 requests to DeepSeek can cost as little as ~$0.06**. Even with higher-priced APIs like OpenAI—often several times more expensive—PAYG remains economical because **you are billed only when requests are made**.

**Real-World Proof**
During the development phase (1.5 months, January to mid-February), I spent only **$0.82** across all four supported LLM providers—while actively using the app myself the entire time.

In contrast, subscription-based AI chats charge the same monthly fee regardless of whether the service is used heavily, lightly, or not at all.

### Combine Providers, Optimize Performance, Reduce Costs

An application that **supports multiple AI providers** unlocks even greater advantages:

- Select the **most cost-effective model** for routine tasks
- Switch to **more powerful models** only when complexity truly requires it
- Avoid vendor lock-in and dynamically balance cost, quality, and speed

This strategy ensures optimal results without unnecessary expense.

### What Can Smaller, Cost-Efficient Models Handle?

For many everyday use cases, lightweight models are more than sufficient, including:

- **Text summarization**
- **Email and short-text drafting**
- **Standard programming questions** (e.g., "How do I write an if-clause in language X?")
- **Concept explanations** (e.g., "What are the advantages of microservices?")

Reserving large, expensive models only for genuinely complex tasks leads to **dramatic cost savings without sacrificing quality**.

### Conclusion

Why pay for an expensive flat-rate AI subscription when an **API-based, multi-provider chat solution** gives you:

- Precise cost control
- Maximum flexibility
- No unused capacity
- Optimal performance per task

With PAYG, **you stay in control—financially and technically—at all times**.


## Quick Start

Get ExpertGPTs up and running in 5 minutes:

```bash
# Clone and navigate
git clone <repository-url>
cd expertgpts-legacy

# Install uv (if not already installed)
# macOS/Linux:
curl -LsSf https://astral.sh/uv/install.sh | sh
# Windows:
# powershell -ExecutionPolicy ByPass -c "irm https://astral.sh/uv/install.ps1 | iex"

# Run the app (uv automatically manages dependencies)
uv run streamlit run app.py
```

**First run?** The app automatically creates 9 example experts and detects your system language.

**Get your API key**: [https://platform.deepseek.com/](https://platform.deepseek.com/)

Set it via **Settings → API Key** in the app.

**That's it!** Start chatting with experts.

**Detailed setup**: [Installation Guide](docs/getting-started/installation.md)


## Architecture Overview

```
expertgpts/
├── app.py                         # Main entry point with st.navigation()
├── pages/
│   ├── 1000_Home.py              # Home page (permanent)
│   ├── 1001_*.py                 # Expert pages (generated from template)
│   ├── 9998_Settings.py          # Settings page (permanent)
│   ├── 9999_Help.py              # Help page (permanent)
│   └── _debug.py                 # Hidden /debug diagnostics page (permanent)
├── templates/template.py          # Template for expert pages
├── configs/{expert_id}.yaml       # Expert configurations
├── lib/                           # Core library (domain-driven structure)
│   ├── llm/                      # LLM client, connection pooling, token management
│   ├── audio/                    # Voice input transcription (speech-to-text)
│   ├── config/                   # Expert config, secrets, app defaults, theme config
│   ├── i18n/                     # Internationalization
│   ├── storage/                  # Chat history, chat image files, streaming cache
│   ├── ui/                       # Dialogs, chat toolbox and UI components
│   └── shared/                   # Constants, helpers, file ops, attachments, types, session state
└── locales/ui/*.json             # UI translations (14 languages)
```

**Key Architecture Principles**:
- **Template-Based**: Single template generates all expert pages
- **Multi-Provider Abstraction**: Unified client interface for DeepSeek, OpenAI, Z.AI, KIMI
- **Clean Architecture**: Expert content in YAML (English), UI in locale files
- **State Management**: Multi-layered session state with persistent storage

**Detailed architecture**: [Architecture Documentation](docs/architecture/overview.md)

## Internationalization

ExpertGPTs supports **14 languages** with automatic detection:

🇺🇸 English | 🇩🇪 German | 🇪🇸 Spanish | 🇫🇷 French | 🇮🇹 Italian | 🇮🇩 Indonesian | 🇲🇾 Malay | 🇵🇹 Portuguese | 🇷🇺 Russian | 🇹🇷 Turkish | 🇨🇳 Simplified Chinese | 🇹🇼 Traditional Chinese | 🇭🇰 Cantonese | 🏛️ Classical Chinese

**How it works**: Language prefix injected at runtime ensures AI responds in your selected language, while expert content remains in English (single source of truth).

**Full guide**: [Internationalization Documentation](docs/internationalization/I18N_GUIDE.md)

## Documentation

### For Users

- **[Quick Start Guide](docs/getting-started/quickstart.md)** - 5-minute setup
- **[Installation Guide](docs/getting-started/installation.md)** - Detailed installation
- **[User Guide](docs/user-guide/basics.md)** - Using experts, navigation, provider selection
- **[Creating Experts](docs/user-guide/creating-experts.md)** - Custom expert creation
- **[Customization](docs/user-guide/customization.md)** - Themes, language, settings
- **[Troubleshooting](docs/reference/troubleshooting.md)** - Common issues

### For Developers

- **[Development Setup](docs/development/setup.md)** - Development environment
- **[Architecture Overview](docs/architecture/overview.md)** - System architecture
- **[Project Structure](docs/development/project-structure.md)** - File organization
- **[Adding Features](docs/development/adding-features.md)** - Feature development guidelines
- **[Testing Guide](docs/development/testing.md)** - Testing documentation

### Technical Reference

- **[Configuration](docs/configuration/overview.md)** - Configuration system
- **[API Providers](docs/api/providers.md)** - LLM provider integration
- **[Template System](docs/architecture/template-system.md)** - Page generation
- **[Scripts Reference](docs/reference/scripts.md)** - Administrative scripts
- **[Debug Page](docs/reference/debug-page.md)** - Hidden `/debug` diagnostics page
- **[HTTPS with Caddy](docs/configuration/tls.md)** - TLS reverse proxy for a server deployment

**Full documentation**: [docs/](docs/)

## Multi-Provider LLM Support

ExpertGPTs integrates with multiple LLM providers through OpenAI-compatible APIs:

| Provider | Default Model | Characteristics |
|----------|---------------|-----------------|
| **DeepSeek** | `deepseek-flash` | Cost-effective, 1M context, dual thinking modes |
| **OpenAI** | `gpt-6.1-sol` | GPT-6 / GPT-5.6 / GPT-5.4 series, advanced reasoning, coding, agentic tasks |
| **Z.AI** | `glm-5.3` | GLM models, 1M context, Chinese optimization, includes free tier |
| **KIMI** | `kimi-k3` | 1M context, always-on reasoning (`low`/`high`/`max`), multimodal; K2.7 Code for coding |

**Per-Expert Selection**: Each expert can use a different provider/model. Switch via the model dropdown below the chat input (all models of providers with an API key); thinking mode and temperature appear next to it where the model supports them, and changes are saved immediately.

**Image Input**: `deepseek-flash`, all OpenAI models and all KIMI models accept images; `deepseek-v4-pro` and the Z.AI GLM models are text-only. See [Attaching Images](docs/user-guide/basics.md#attaching-images).

**Connection Pooling**: Client instances cached for ~50% performance improvement.

**API Documentation**: [Provider Reference](docs/api/providers.md)

## Development

### Running the App

```bash
# Recommended (uses uv for automatic dependency management)
uv run streamlit run app.py

# With enhanced file watching (faster during development)
uv run streamlit run app.py --server.fileWatcherType=watchdog
```

### Installing uv

[uv](https://docs.astral.sh/uv/) is a fast Python package installer and resolver. Install it with:

```bash
# macOS/Linux
curl -LsSf https://astral.sh/uv/install.sh | sh

# Windows
powershell -ExecutionPolicy ByPass -c "irm https://astral.sh/uv/install.ps1 | iex"

# With pip (any platform)
pip install uv
```

### Running Tests

```bash
# Run all tests
./scripts/run_tests.sh

# Direct pytest
uv run pytest -v

# With coverage
uv run pytest --cov=lib --cov-report=html
```

### Adding Features

**Modify Expert Pages**: Edit `templates/template.py`, then run `uv run python scripts/regenerate_pages.py` (rewrites all expert pages from the template; configs and chat history are kept)

**Modify Home/Settings/Help**: Edit `pages/1000_Home.py`, `pages/9998_Settings.py`, or `pages/9999_Help.py` directly

**Development Guide**: [Adding Features Documentation](docs/development/adding-features.md)

### Debug Page

A hidden diagnostics page for developers and operators. It is **not** linked in
the navigation — reach it by appending `/debug` to the app URL:

```
http://localhost:8501/debug
```

It has six tabs: **Dependencies** (declared vs. actually-installed versions from
`pyproject.toml`, with mismatches flagged), **Runtime** (Python/Streamlit
versions, platform, Git branch), **App status** (expert/config counts,
chat-history sizes, streaming-cache files), **Config** (API-key status and
default provider/model/language), **Session state** (a live `st.session_state`
dump), and **Actions** (cache-clear buttons that never touch chat history or
configs).

API keys and other secret-like values are always masked. The page is *unlisted*,
not access-controlled, so don't expose the app publicly without authentication.

**Details**: [Debug Page Reference](docs/reference/debug-page.md)

## License

This project is open source and available under the Apache License 2.0.

## Why Streamlit and Its Limitations

I chose Streamlit because it makes creating beautiful interfaces remarkably easy, and Streamlit itself actively promotes it for AI and LLM applications ([chat tutorials](https://docs.streamlit.io/develop/tutorials/chat-and-llm-apps), [30 Days of AI Challenge](https://discuss.streamlit.io/t/the-30-days-of-ai-challenge-starts-today/120455)). Since the framework is Python-based, it also gave me an opportunity to delve deeper into Python development. However, I wasn't aware of Streamlit's architectural limitations before starting this project, and they significantly shaped the implementation.

The three biggest challenges are:

1. **No Asynchronicity**: Streamlit doesn't support `async/await`, meaning all LLM streaming requests are blocking. I had to implement a file-based background streaming system with daemon threads just to allow responses to complete when users navigate away—a 250-line solution for what should be a simple async operation.

2. **Execution Model**: Streamlit reruns your entire script from top to bottom on every interaction. This means changing session state doesn't update the UI until you explicitly call `st.rerun()`. ExpertGPTs has 26 such calls—for everything from toggling dialogs to reloading API keys—because the script can't re-evaluate conditionals mid-execution.

3. **State Management Complexity**: Session state doesn't persist across app restarts, and external file changes (configs, API keys) aren't detected automatically. I built a multi-layered state system with manual cache invalidation to work around this.

Would I choose Streamlit again? For data dashboards and simple prototypes, absolutely—it's perfect for those. But for an AI chatbot with real-time streaming, complex state management, and background processing? I'd rather do a rewrite with a modern stack like **React and Bun**, which handle these requirements natively with better performance and developer experience.

## Acknowledgments

- Built with [Streamlit](https://streamlit.io/)
- Powered by [DeepSeek API](https://www.deepseek.com/), [OpenAI API](https://openai.com/), [Z.AI](https://z.ai/), and [KIMI](https://www.kimi.com/)
- Inspired by OpenAI's GPTs explore functionality
- Developed with [Z.AI](https://z.ai/subscribe?ic=JGTYCX7ZO7) - Advanced AI platform

## Support

For issues, questions, or contributions, visit the [GitHub repository](https://github.com/fossler/expertgpts-legacy).

---

## ☕ Buy Me a Coffee

If you find this project helpful and would like to support its development, consider buying me a coffee!

<a href="https://www.buymeacoffee.com/MirzetKadic" target="_blank"><img src="https://cdn.buymeacoffee.com/buttons/v2/default-yellow.png" alt="Buy Me A Coffee" style="height: 60px !important;width: 217px !important;" ></a>
