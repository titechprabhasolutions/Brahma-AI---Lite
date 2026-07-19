<p align="center">
  <img src="assets/Brahma_Lite_Logo.png" alt="Brahma AI - Lite" width="260" />
</p>

<h1 align="center">Brahma AI - Lite</h1>

<p align="center">
  <strong>Premium Windows desktop AI assistant</strong> for voice, automation, productivity, and intelligent workflows.
</p>

<p align="center">
  <a href="#overview"><img src="https://img.shields.io/badge/experience-premium-blue?style=for-the-badge" alt="Premium Experience" /></a>
  <a href="#getting-started"><img src="https://img.shields.io/badge/platform-Windows%2010%2F11-lightgrey?style=for-the-badge" alt="Windows" /></a>
  <a href="#how-it-works"><img src="https://img.shields.io/badge/ai-voice%20%2B%20automation-green?style=for-the-badge" alt="AI + Automation" /></a>
</p>

---

## Overview

Brahma AI - Lite is a premium desktop assistant designed for Windows power users. It unites voice and text input with intelligent automation, productivity workflows, document generation, and adaptive screen-aware actions.

- Live voice and text interaction via Gemini with OpenRouter fallback
- Automatic daily briefing with interruption-aware audio playback
- Desktop automation for apps, windows, files, and browser workflows
- Office content generation for PowerPoint, Word, spreadsheets, and PDF
- Built-in website creation support through Buildonaut studio
- Discord collaboration, reminders, meeting assistant, and notifications

## Why It’s Premium

- Responsive UI with rich task/workspace feedback
- Seamless AI and voice integration for desktop productivity
- Modular tool-driven architecture for clean extension
- Robust fallback handling to keep the assistant available
- Local-first configuration with secure credentials storage

## Features

### Intelligent Assistant

- Unified voice + typed conversation experience
- Startup daily briefing with premium Edge TTS delivery
- Instant briefing interruption when a new message arrives
- Gemini-first live AI with OpenRouter fallback support

### Automation & Productivity

- Open and control Windows applications and system actions
- Browser automation with Playwright for web workflows
- Screen inspection and contextual content extraction
- File and document automation for fast productivity

### Office & Content Tools

- Generate PowerPoint decks and presentation content
- Create spreadsheets and Word documents quickly
- Export polished reports as PDF files
- Build landing pages and websites from within the app

### Integrations

- Discord bridge for remote commands and chat
- Local credential management for Gemini and OpenRouter
- Configurable voice, notifications, startup, and UI preferences

## How It Works

Brahma AI - Lite is built on a layered desktop architecture that separates UI, AI session management, and tool execution.

- `main.py` initializes the application, launches the UI, and manages the AI runtime.
- `BrahmaLive` owns the live AI session, audio queues, and command routing.
- `actions/` contains modular tools for automation, document generation, notifications, meetings, and search.
- `AttentionMonitor` captures external events and notification text, then speaks alerts using Edge TTS.
- `daily_briefing.py` constructs the morning briefing text and triggers playback after startup.
- `ui.py` provides a polished Qt-based interface with command entry, workspace cards, and status feedback.
- `or_client.py` provides OpenRouter fallback support when Gemini is unavailable or rate-limited.

## Getting Started

### Prerequisites

- Windows 10 or Windows 11
- Python 3.11 or 3.12
- Git installed
- Gemini API key
- OpenRouter API key (optional, recommended for fallback resilience)

### 1. Clone the repository

```powershell
git clone https://github.com/titechprabhasolutions/Brahma-AI---Lite.git
cd "Brahma AI - Lite"
```

### 2. Create a virtual environment

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
```

### 3. Install dependencies

```powershell
pip install -r requirements.txt
playwright install
```

### 4. Configure API keys

The app loads keys from `config/api_keys.json`. Create this file if it does not already exist.

```json
{
  "gemini_api_key": "YOUR_GEMINI_API_KEY",
  "openrouter_api_key": "YOUR_OPENROUTER_API_KEY"
}
```

#### Gemini API Key

- Create a Google Cloud or Gemini account
- Enable Gemini API access for your project
- Generate an API key and add it under `gemini_api_key`

#### OpenRouter API Key (recommended)

- Register at https://openrouter.ai
- Generate an `sk-or-` API key
- Add it under `openrouter_api_key`

### 5. Optional: Configure Discord integration

To enable Discord bridging, populate `config/discord_bot.json` with your bot credentials and connection settings.

### 6. Start the app

```powershell
python main.py
```

For a cleaner Windows launch without console output:

```powershell
start_brahma.vbs
```

## Configuration

- `config/api_keys.json` — Gemini and OpenRouter credentials
- `config/app_settings.json` — voice, UI, startup, and automation settings
- `config/discord_bot.json` — Discord bridge settings

## Project Structure

- `main.py` — core runtime, AI session orchestration, and startup flow
- `ui.py` — polished Qt interface, workspace cards, and controls
- `actions/` — modular tools for automation and AI workflows
- `config/` — local settings, API keys, and runtime configuration
- `tests/` — validation and integration tests for core features

## Recent Updates

### 2026-07-19

- Restored automatic daily briefing playback at startup.
- Unified local TTS output to the same premium male Edge voice.
- Added briefing interruption support for immediate user response.
- Redesigned gesture HUD for premium hand landmark control.
- Improved cursor mapping for better desktop reach and direction.
- Added idle speech prompts for proactive engagement.
- Enhanced controller tests for Buildonaut workflow coverage.

## Community

- Discord: https://discord.gg/gEYmJKKtq3
- YouTube: https://www.youtube.com/@Buildonaut-AI

## License

This project is licensed under a custom source-available license. See `LICENSE` for full terms and `TRADEMARK.md` for branding details.

## Maintained by

- Suryaansh Tiwari

Please preserve attribution and keep credentials secure when building on top of Brahma AI - Lite.

