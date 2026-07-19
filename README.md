<p align="center">
  <img src="assets/Brahma_Lite_Logo.png" alt="Brahma AI - Lite" width="240" />
</p>

<h1 align="center">Brahma AI - Lite</h1>

<p align="center">
  <strong>Source-available Windows desktop AI assistant</strong> for voice, automation, productivity, and premium desktop workflows.
</p>

<p align="center">
  <a href="#features"><img src="https://img.shields.io/badge/features-voice%20AI%20%7C%20automation-blue?style=for-the-badge" alt="Features" /></a>
  <a href="#getting-started"><img src="https://img.shields.io/badge/platform-Windows%2010%2F11-lightgrey?style=for-the-badge" alt="Windows" /></a>
  <a href="#how-it-works"><img src="https://img.shields.io/badge/architecture-modern-green?style=for-the-badge" alt="Architecture" /></a>
</p>

---

## Overview

Brahma AI - Lite delivers a polished AI assistant experience for Windows power users. It blends voice and typed chat with automation, productivity, office workflows, and intelligent screen-aware actions.

- Voice & text chat with Gemini and OpenRouter fallback
- Startup daily briefing with seamless interruption support
- Windows automation for apps, files, browser actions, and system control
- Office workflow generation for PowerPoint, spreadsheets, Word, and PDF
- Built-in website generation and Buildonaut studio support
- Discord collaboration, notifications, reminders, and meeting assistance

## Features

### Intelligent Assistant

- Voice and typed conversation in one desktop experience
- Daily briefing playback at startup, delivered with premium TTS
- Briefing interruption: new user commands stop audio instantly
- Gemini-first live AI with OpenRouter fallback for reliability

### Automation & Productivity

- Open apps, control windows, and automate desktop tasks
- Browser automation using Playwright for web workflows
- Screen analysis and content extraction from screenshots or camera
- File handling, document generation, and utility workflows

### Office & Content Tools

- Create PowerPoint slides and templated presentations
- Generate spreadsheets and Word documents on demand
- Export reports as PDFs with polished layouts
- Launch website and landing page generation from the same app

### Integrations

- Discord bridge for remote input and chat
- Local API key management for Gemini + OpenRouter
- Configurable app settings for voice, notifications, and startup

## How It Works

Brahma AI - Lite is built around a desktop runtime, a responsive UI, and an AI-backed session handler.

- `main.py` starts the app, shows the UI, and runs `BrahmaLive`.
- `BrahmaLive` connects to Gemini live audio sessions and sends typed or spoken commands.
- The app uses `actions/` as tool modules for automation, document creation, web search, meeting support, and system control.
- `AttentionMonitor` listens for notifications, toasts, and external events, then speaks alerts through Edge TTS.
- `daily_briefing.py` composes the morning briefing text and plays it after boot.
- The UI in `ui.py` provides the command bar, workspace results, and interactive dashboard controls.
- If Gemini fails or rate-limits, OpenRouter is used as a fallback so the assistant stays responsive.

## Getting Started

### Prerequisites

- Windows 10 or Windows 11
- Python 3.11 or 3.12
- `git` installed
- Gemini API key
- Optional OpenRouter API key

### 1. Clone the repository

```powershell
git clone https://github.com/titechprabhasolutions/Brahma-AI---Lite.git
cd "Brahma AI - Lite"
```

### 2. Create and activate a Python virtual environment

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
```

### 3. Install dependencies

```powershell
pip install -r requirements.txt
playwright install
```

### 4. Add your API keys

Create `config/api_keys.json` with your keys:

```json
{
  "gemini_api_key": "YOUR_GEMINI_API_KEY",
  "openrouter_api_key": "YOUR_OPENROUTER_API_KEY"
}
```

#### Gemini API Key

- Create a Google Cloud or Gemini account
- Enable Gemini API access and generate an API key
- Paste the key into `gemini_api_key`

#### OpenRouter API Key (optional)

- Sign up at https://openrouter.ai
- Generate an API key starting with `sk-or-`
- Add it to `openrouter_api_key`

### 5. Configure optional Discord integration

If you want Discord support, fill `config/discord_bot.json` with your bot credentials and server settings.

### 6. Launch the app

```powershell
python main.py
```

For a silent Windows launch, run:

```powershell
start_brahma.vbs
```

## Configuration

- `config/api_keys.json` — Gemini and OpenRouter credentials
- `config/app_settings.json` — app preferences, voice settings, startup behavior
- `config/discord_bot.json` — Discord bridge settings

## Premium Setup Notes

- Keep your `.venv` environment active when running the app
- Use `start_brahma.vbs` for a cleaner Windows startup experience
- Update `app_settings.json` to enable startup briefing, auto-launch, and voice preferences

## Project Structure

- `main.py` — core runtime, AI session management, and engine glue
- `ui.py` — desktop interface and workspace controls
- `actions/` — modular tools for automation, messaging, document workflows, and more
- `config/` — local key storage, app preferences, and runtime state
- `tests/` — automated test coverage for controller and workflow behavior

## Recent Updates

### 2026-07-19

- Daily briefing now plays automatically at startup.
- Local TTS unified to the same male Edge voice for alerts, briefing, and notifications.
- User messages sent during briefing now interrupt the audio and receive immediate attention.
- Gesture HUD redesigned for premium control with hand landmark navigation.
- Cursor mapping fixes improved desktop reach and direction accuracy.
- Idle speech prompts added for better engagement.
- Updated testing for Buildonaut controller workflows.

## Community

- Discord: https://discord.gg/gEYmJKKtq3
- YouTube: https://www.youtube.com/@Buildonaut-AI

## License

This project is distributed under the custom Brahma Source-Available License. See `LICENSE` for full terms and `TRADEMARK.md` for branding rules.

## Maintainer

Suryaansh Tiwari

If you build on top of Brahma AI - Lite, preserve attribution and keep any secrets out of the repository.

