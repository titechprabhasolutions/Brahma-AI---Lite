<p align="center">
  <img src="assets/Brahma_Lite_Logo.png" alt="Brahma AI - Lite" width="240" />
</p>

<h1 align="center">Brahma AI - Lite</h1>

<p align="center">
  <strong>Source-available Windows desktop AI assistant</strong> for voice, automation, productivity, and real-time workflows.
</p>

<p align="center">
  <a href="#features"><img src="https://img.shields.io/badge/features-voice%20AI%20%7C%20automation-blue?style=for-the-badge" alt="Features" /></a>
  <a href="#getting-started"><img src="https://img.shields.io/badge/platform-Windows%2010%2F11-lightgrey?style=for-the-badge" alt="Windows" /></a>
  <a href="https://github.com/titechprabhasolutions/Brahma-AI---Lite/actions"><img src="https://img.shields.io/badge/build-Manual-yellow?style=for-the-badge" alt="Build" /></a>
</p>

---

## Overview

Brahma AI - Lite is a premium-feeling local-first assistant for desktop users. It combines voice chat, automation, browser control, document workflows, and AI-driven screen analysis into a polished Windows application.

- Voice and text interaction with Gemini + OpenRouter fallback
- Startup daily briefing with live audio and interruption support
- Full PC automation: launch apps, control windows, manage files
- Office workflow generation for PowerPoint, Sheets, Word, and PDF
- Website and landing page builder embedded in the workspace
- Discord bridge, reminder workflows, meeting assistant, and notifications

## Features

### Intelligent Assistant

- Real-time voice conversation and typed chat
- Automatically speaks daily briefing on launch
- Accepts interruption commands during briefing
- Live AI backend with fallback handling for resilience

### Productivity & Automation

- Open and control Windows apps and system actions
- Run browser automation flows with Playwright
- Summarize screens, extract data, and generate content
- Build documents, presentations, and exports on demand

### Office & Content Tools

- Create and edit PowerPoint slides
- Generate spreadsheets and Word documents
- Produce PDFs and templated reports
- Build polished front-end and full-stack website apps

### Integrations

- Discord support for remote interaction
- Local API key management for Gemini and OpenRouter
- Config-driven settings for voice, notifications, and automation

## Getting Started

### Requirements

- Windows 10 or Windows 11
- Python 3.11 or 3.12
- Gemini API key
- Optional OpenRouter API key

### Install

```powershell
pip install -r requirements.txt
playwright install
```

### Run

```powershell
python main.py
```

For a no-console Windows launch, use:

```powershell
start_brahma.vbs
```

## Configuration

- `config/api_keys.json` stores your API credentials
- `config/discord_bot.json` stores Discord bot settings
- `config/app_settings.json` stores app preferences and voice settings

## Project Structure

- `main.py` — main runtime, AI session, and command routing
- `ui.py` — desktop interface and visual controls
- `actions/` — automation, voice, and workflow tools
- `config/` — local settings, API keys, and app state
- `tests/` — automated controller and integration tests

## Recent Updates

### 2026-07-19

- Daily briefing now plays automatically at startup.
- Local TTS unified to the same male Edge voice for alerts, briefing, and notifications.
- User messages sent during briefing now interrupt the audio and receive immediate attention.
- Gesture HUD redesigned for premium control with hand landmark navigation.
- Cursor mapping fixes improved desktop reach and direction accuracy.
- Idle speech prompts added for better engagement.
- Updated testing for Buildonaut controller workflows.

## License

This project is distributed under the custom Brahma Source-Available License. See `LICENSE` for full terms and `TRADEMARK.md` for branding rules.

## Maintainer

Suryaansh Tiwari

If you build on top of Brahma AI - Lite, please preserve attribution and keep secrets out of the repository.

