# Brahma AI - Lite

Source-available desktop AI assistant for Windows, built and maintained by Suryaansh Tiwari.

Brahma AI - Lite is a local-first assistant for voice commands, desktop automation, browser control, document generation, and screen-aware workflows. It is designed to help users interact with their computer in a natural way while keeping the experience lightweight and extensible.

## What It Does

- Voice input and spoken responses
- Text chat and command execution
- App launching and desktop control
- Browser automation and web search
- Screen analysis and visual understanding
- File handling and document workflows
- Presentation, spreadsheet, Word, and PDF creation
- Full-stack website and landing page generation
- Notifications and meeting assistant workflows
- Discord chat bridge for remote interaction

## Key Features

### Assistant

- Gemini-first conversation flow
- OpenRouter fallback for resilience
- Voice and text interaction
- Multi-step task execution

### Automation

- Open apps and control Windows tasks
- Manage files and folders
- Run browser actions with Playwright
- Analyze screenshots and camera input
- Handle reminders, weather, and utility workflows

### Office Tools

- Create PowerPoint presentations
- Create spreadsheets
- Create and edit Word documents
- Generate PDFs
- Build polished frontend and backend website apps

### Integrations

- Discord bot support
- Local configuration files for API keys and settings

## Getting Started

### Requirements

- Windows 10 or Windows 11
- Python 3.11 or 3.12
- Gemini API key
- Optional OpenRouter API key

### Install

Install dependencies with pip install -r requirements.txt
Then install browser support with playwright install

### Run

Start the app with python main.py

On Windows, use start_brahma.vbs for a no-console launch.

## Configuration

API keys are stored locally in config/api_keys.json

Discord bot settings are stored locally in config/discord_bot.json

## Project Structure

- main.py - assistant runtime and tool routing
- ui.py - desktop interface
- actions/ - automation and content-generation tools
- config/ - local settings and API key storage

## License

This project is distributed under the custom Brahma Source-Available License.
See the LICENSE file for the full terms and the Trademark Notice in TRADEMARK.md.

Summary:

- You may use and modify the software for personal or internal use.
- You may share unmodified copies with notices intact.
- You may not rebrand, rename, or republish the software as your own product.

## Maintainer

Suryaansh Tiwari

If you build on top of Brahma AI - Lite, please preserve attribution and keep secrets out of the repository.

## Recent updates (2026-07-09)

- Gesture HUD redesign: the gesture control widget was reworked into a premium-style HUD (no raw camera preview). Hand landmark input is mapped to desktop cursor movement with configurable sensitivity, smoothing, and dead-zone, and supports multi-monitor primary displays.
- Cursor mapping fixes: left/right/up/down mapping corrected and normalized hand coords map to full desktop extents (reach edges).
- Idle speech: Brahma will emit a short, friendly voice prompt when idle (every ~4–5 minutes) to regain attention.
- Removed the old `actions/website_builder.py` and its planner/executor references; website-building now uses an external workspace controller and scaffolding.
- New testing: `tests/test_buildonaut_controller.py` verifies the controller API for creating, listing, and starting a project preview.

## How to apply these changes to GitHub (example)

From the project root run:

```powershell
git add README.md
git commit -m "docs: add recent updates (Buildonaut integration, gesture HUD, idle speech)"
git push origin HEAD
```

If `git push` fails due to credentials, use your normal Git auth flow (SSH keys, PAT, or credential manager) and re-run the push command.

---

If you'd like, I can also:

- Wire the Buildonaut explorer to show the real project files and add in-UI editor actions.
- Add automated `npm install` when missing (ask before running long installs).
- Push the README change to the remote for you (I can attempt a `git push` now). 
