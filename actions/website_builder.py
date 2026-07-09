"""
website_builder.py - Brahma AI website generation

Creates polished, responsive static websites from a brief or structured input.
The builder writes a real production-style site folder with HTML, CSS, and JS
instead of a throwaway prototype page.
"""

from __future__ import annotations

import html
import json
import os
import re
import subprocess
import sys
import time
import webbrowser
import socket
import urllib.error
import urllib.request
from pathlib import Path
from string import Template
from typing import Any

PROJECT_NAME = "Brahma AI - Lite"
DEFAULT_OUTPUT_DIR = Path.home() / "Desktop" / "BrahmaAI_Websites"


def _sanitize_filename(name: str, default: str) -> str:
    safe = re.sub(r"[^A-Za-z0-9._ -]+", "", (name or "").strip())
    safe = re.sub(r"\s+", " ", safe).strip().replace(" ", "_")
    return safe or default


def _safe_slug(value: str, default: str = "page") -> str:
    slug = re.sub(r"[^a-z0-9]+", "-", (value or "").lower()).strip("-")
    return slug or default


def _resolve_output_dir(output_dir: str | None, site_name: str) -> Path:
    if output_dir:
        path = Path(output_dir).expanduser()
        if not path.is_absolute():
            head = path.parts[0].lower() if path.parts else ""
            tail = Path(*path.parts[1:]) if len(path.parts) > 1 else Path(path.name)
            if head in {"downloads", "download"}:
                path = Path.home() / "Downloads" / tail
            elif head == "desktop":
                path = Path.home() / "Desktop" / tail
            else:
                path = Path.cwd() / path
        path.mkdir(parents=True, exist_ok=True)
        return path

    DEFAULT_OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    return DEFAULT_OUTPUT_DIR / _sanitize_filename(site_name, "website")


def _open_path(path: Path) -> None:
    try:
        if os.name == "nt":
            os.startfile(str(path))  # type: ignore[attr-defined]
        elif sys.platform == "darwin":
            subprocess.Popen(["open", str(path)])
        else:
            subprocess.Popen(["xdg-open", str(path)])
    except Exception:
        try:
            webbrowser.open(path.resolve().as_uri())
        except Exception:
            pass


def _find_free_port(start: int = 8787, end: int = 8899) -> int:
    for port in range(start, end + 1):
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
            sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
            try:
                sock.bind(("127.0.0.1", port))
                return port
            except OSError:
                continue
    raise RuntimeError("Could not find a free local port for the website preview.")


def _get_api_key() -> str:
    config_path = Path(__file__).resolve().parent.parent / "config" / "api_keys.json"
    with open(config_path, "r", encoding="utf-8") as f:
        return json.load(f)["gemini_api_key"]


def _ai_client():
    from google import genai

    return genai.Client(api_key=_get_api_key())


def _parse_json_arg(value: Any, fallback: Any):
    if value is None:
        return fallback
    if isinstance(value, (dict, list)):
        return value
    if isinstance(value, str):
        text = value.strip()
        if not text:
            return fallback
        try:
            return json.loads(text)
        except Exception:
            return fallback
    return fallback


def _normalize_list(value: Any) -> list:
    if value is None:
        return []
    if isinstance(value, list):
        return value
    parsed = _parse_json_arg(value, None)
    if isinstance(parsed, list):
        return parsed
    if isinstance(value, str):
        return [item.strip() for item in re.split(r"\n+", value) if item.strip()]
    return [value]


def _normalize_hex(value: str | None, default: str) -> str:
    raw = re.sub(r"[^0-9a-fA-F]", "", (value or "").strip())
    if len(raw) == 6:
        return raw.upper()
    if len(raw) == 3:
        return "".join(ch * 2 for ch in raw).upper()
    return default.upper()


def _extract_text(response) -> str:
    text = getattr(response, "text", "") or ""
    if text.strip():
        return text.strip()
    try:
        chunks = []
        for candidate in getattr(response, "candidates", []) or []:
            content = getattr(candidate, "content", None)
            if not content:
                continue
            for part in getattr(content, "parts", []) or []:
                part_text = getattr(part, "text", None)
                if part_text:
                    chunks.append(part_text)
        return "".join(chunks).strip()
    except Exception:
        return ""


def _fallback_spec(parameters: dict) -> dict:
    site_name = (parameters.get("site_name") or parameters.get("title") or "Brahma Studio").strip()
    style = (parameters.get("style") or "modern premium").strip()
    brief = (parameters.get("brief") or parameters.get("description") or "").strip()
    project_type = _classify_project_type(brief, site_name)

    app_shell = {
        "sidebar_items": ["Dashboard", "Workspace", "Prompts", "API", "Settings"],
        "top_actions": ["New Project", "Preview", "Deploy"],
        "workspace_panels": [
            {"title": "Prompt Workspace", "description": "Generate content, prototype flows, and ship pages from one place."},
            {"title": "Model Panel", "description": "Compare outputs, inspect tool calls, and keep the app responsive."},
            {"title": "Live Activity", "description": "Monitor tasks, requests, and generated assets in real time."},
        ],
    }

    spec = {
        "site_name": site_name,
        "tagline": brief or "Premium websites, built to convert.",
        "about": "A polished static website generated by Brahma AI - Lite.",
        "style": style,
        "theme": {
            "bg": "0A0D12",
            "surface": "111722",
            "surface_alt": "171E2C",
            "text": "F4F7FB",
            "muted": "9CA9B8",
            "accent": "7C5CFF",
            "accent_alt": "18D3C5",
        },
        "primary_cta": "Get Started",
        "secondary_cta": "See Features",
        "nav_links": [
            {"label": "Features", "href": "#features"},
            {"label": "Process", "href": "#process"},
            {"label": "Work", "href": "#work"},
            {"label": "FAQ", "href": "#faq"},
        ],
        "hero_metrics": [
            {"value": "Fast", "label": "Load times"},
            {"value": "Responsive", "label": "Every device"},
            {"value": "Clean", "label": "Modern UI"},
        ],
        "features": [
            {"title": "Strong visual hierarchy", "description": "Built to guide visitors toward the right action."},
            {"title": "Responsive layouts", "description": "Looks sharp on phones, tablets, and desktops."},
            {"title": "Conversion-friendly sections", "description": "Hero, features, proof, FAQ, and CTA blocks."},
            {"title": "Easy to customize", "description": "Generated as real HTML, CSS, and JavaScript files."},
        ],
        "showcase": {
            "title": "Built like a real product site",
            "description": "The builder creates a coherent site structure instead of a placeholder mockup.",
            "items": [
                "Premium hero and CTA flow",
                "Reusable cards and content sections",
                "Subtle motion and polished spacing",
            ],
        },
        "steps": [
            {"title": "Define the brief", "description": "Tell Brahma what the site should sell or present."},
            {"title": "Generate the structure", "description": "AI turns the brief into a full web-ready content plan."},
            {"title": "Render and open", "description": "The static site is written to disk and opened for review."},
        ],
        "testimonials": [
            {"quote": "It feels like a real launch-ready website, not a prototype.", "name": "Product Team", "role": "Early user"},
        ],
        "faq": [
            {"question": "Can I edit the files afterwards?", "answer": "Yes. The output is standard HTML, CSS, and JavaScript."},
            {"question": "Does it support multiple pages?", "answer": "Yes. If you provide page definitions, Brahma can generate them."},
        ],
        "contact": {
            "title": "Ready to ship",
            "text": "Use this as a landing page, portfolio, product site, or business homepage.",
        },
        "app_shell": app_shell if project_type == "app" else None,
    }
    return spec


def _classify_project_type(brief: str, site_name: str = "") -> str:
    text = f"{site_name} {brief}".lower()
    dashboard_terms = (
        "saas", "dashboard", "studio", "web app", "ai studio", "control panel",
        "admin", "platform", "portal", "app", "workspace", "builder", "tool",
    )
    if any(term in text for term in dashboard_terms):
        return "app"
    return "marketing"


def _ai_spec(parameters: dict) -> dict:
    brief = (parameters.get("brief") or parameters.get("description") or parameters.get("prompt") or "").strip()
    if not brief:
        return _fallback_spec(parameters)

    site_name = (parameters.get("site_name") or parameters.get("title") or "Brahma Studio").strip()
    style = (parameters.get("style") or "modern premium").strip()
    audience = (parameters.get("audience") or parameters.get("target_audience") or "").strip()
    tone = (parameters.get("tone") or "confident, premium, modern").strip()
    palette = parameters.get("palette") or {}
    project_type = _classify_project_type(brief, site_name)

    prompt = f"""
You are a senior web designer and frontend engineer.
Turn the user's brief into a JSON spec for a premium website app.
Return ONLY valid JSON and nothing else.

Rules:
- Make the site feel launch-ready, modern, premium, and trustworthy.
- Prefer strong conversion flow, clean hierarchy, and elegant section spacing.
- Avoid placeholder or generic copy.
- Use short, compelling headlines and realistic feature text.
- Include only content that would help a real website.
- If the brief describes a SaaS, dashboard, AI studio, platform, or app, design an app-style interface with sidebar, topbar, workspace, primary actions, and API/dashboard sections.

User brief:
{brief}

Context:
- Site name: {site_name}
- Style: {style}
- Audience: {audience or "general"}
- Tone: {tone}
- Project type: {project_type}
- Preferred palette: {json.dumps(palette) if palette else "auto"}

JSON schema:
{{
  "site_name": "string",
  "tagline": "string",
  "about": "string",
  "style": "string",
  "theme": {{
    "bg": "hex",
    "surface": "hex",
    "surface_alt": "hex",
    "text": "hex",
    "muted": "hex",
    "accent": "hex",
    "accent_alt": "hex"
  }},
  "primary_cta": "string",
  "secondary_cta": "string",
  "nav_links": [{{"label":"string","href":"#section"}}],
  "hero_metrics": [{{"value":"string","label":"string"}}],
  "features": [{{"title":"string","description":"string"}}],
  "showcase": {{
    "title": "string",
    "description": "string",
    "items": ["string"]
  }},
  "steps": [{{"title":"string","description":"string"}}],
  "testimonials": [{{"quote":"string","name":"string","role":"string"}}],
  "faq": [{{"question":"string","answer":"string"}}],
  "contact": {{
    "title": "string",
    "text": "string"
  }},
  "app_shell": {{
    "sidebar_items": ["string"],
    "top_actions": ["string"],
    "workspace_panels": [{{"title":"string","description":"string"}}]
  }},
  "pages": [{{"slug":"string","title":"string","summary":"string"}}]
}}
"""

    try:
        client = _ai_client()
        response = client.models.generate_content(
            model="gemini-2.5-flash",
            contents=prompt,
        )
        raw = _extract_text(response)
        raw = re.sub(r"```(?:json)?", "", raw).strip().rstrip("`").strip()
        spec = json.loads(raw)
        if not isinstance(spec, dict):
            raise ValueError("Invalid website spec")
        return spec
    except Exception:
        spec = _fallback_spec(parameters)
        if project_type == "app" and not spec.get("app_shell"):
            spec["app_shell"] = {
                "sidebar_items": ["Dashboard", "Workspace", "Prompts", "API", "Settings"],
                "top_actions": ["New Project", "Preview", "Deploy"],
                "workspace_panels": [
                    {"title": "Prompt Workspace", "description": "Generate content, prototype flows, and ship pages from one place."},
                    {"title": "Model Panel", "description": "Compare outputs, inspect tool calls, and keep the app responsive."},
                    {"title": "Live Activity", "description": "Monitor tasks, requests, and generated assets in real time."},
                ],
            }
        return spec


def _build_theme(spec: dict) -> dict:
    theme = dict(spec.get("theme") or {})
    return {
        "bg": _normalize_hex(theme.get("bg"), "0A0D12"),
        "surface": _normalize_hex(theme.get("surface"), "111722"),
        "surface_alt": _normalize_hex(theme.get("surface_alt"), "171E2C"),
        "text": _normalize_hex(theme.get("text"), "F4F7FB"),
        "muted": _normalize_hex(theme.get("muted"), "9CA9B8"),
        "accent": _normalize_hex(theme.get("accent"), "7C5CFF"),
        "accent_alt": _normalize_hex(theme.get("accent_alt"), "18D3C5"),
    }


def _render_nav_links(pages: list[dict], active_slug: str) -> str:
    links = []
    for page in pages:
        slug = page.get("slug") or "index"
        title = html.escape(str(page.get("title") or slug.title()))
        href = "index.html" if slug == "index" else f"{_safe_slug(slug)}.html"
        cls = "active" if slug == active_slug else ""
        links.append(f'<a class="{cls}" href="{href}">{title}</a>')
    return "\n".join(links)


def _render_stat_cards(stats: list[dict]) -> str:
    cards = []
    for stat in stats:
        value = html.escape(str(stat.get("value") or ""))
        label = html.escape(str(stat.get("label") or ""))
        cards.append(
            f'<article class="stat-card"><span>{label}</span><strong>{value}</strong></article>'
        )
    return "\n".join(cards)


def _render_feature_cards(features: list[dict]) -> str:
    cards = []
    for feature in features:
        title = html.escape(str(feature.get("title") or "Feature"))
        description = html.escape(str(feature.get("description") or ""))
        cards.append(
            f'<article class="feature-card"><h3>{title}</h3><p>{description}</p></article>'
        )
    return "\n".join(cards)


def _render_steps(steps: list[dict]) -> str:
    rows = []
    for idx, step in enumerate(steps, 1):
        title = html.escape(str(step.get("title") or f"Step {idx}"))
        description = html.escape(str(step.get("description") or ""))
        rows.append(
            f'<div class="step"><span>{idx:02d}</span><div><h3>{title}</h3><p>{description}</p></div></div>'
        )
    return "\n".join(rows)


def _render_testimonials(testimonials: list[dict]) -> str:
    cards = []
    for item in testimonials:
        quote = html.escape(str(item.get("quote") or ""))
        name = html.escape(str(item.get("name") or ""))
        role = html.escape(str(item.get("role") or ""))
        cards.append(
            f'<article class="testimonial-card"><p class="quote">"{quote}"</p><strong>{name}</strong><span>{role}</span></article>'
        )
    return "\n".join(cards)


def _render_faq(faq_items: list[dict]) -> str:
    blocks = []
    for item in faq_items:
        question = html.escape(str(item.get("question") or ""))
        answer = html.escape(str(item.get("answer") or ""))
        blocks.append(
            f'<details class="faq-item"><summary>{question}</summary><p>{answer}</p></details>'
        )
    return "\n".join(blocks)


def _render_showcase(showcase: dict) -> str:
    title = html.escape(str(showcase.get("title") or ""))
    description = html.escape(str(showcase.get("description") or ""))
    items = showcase.get("items") or []
    item_html = "".join(
        f'<li>{html.escape(str(item))}</li>' for item in items if str(item).strip()
    )
    return f"""
    <section class="showcase" id="work">
      <div class="section-heading">
        <span>Why it stands out</span>
        <h2>{title}</h2>
        <p>{description}</p>
      </div>
      <ul class="showcase-list">{item_html}</ul>
    </section>
    """


def _render_contact(contact: dict) -> str:
    title = html.escape(str(contact.get("title") or "Ready to ship"))
    text = html.escape(str(contact.get("text") or ""))
    return f"""
    <section class="contact-panel">
      <div>
        <span>Need a launch page?</span>
        <h2>{title}</h2>
        <p>{text}</p>
      </div>
      <a href="#top" class="button button-primary">Build another page</a>
    </section>
    """


def _render_app_shell(app_shell: dict, spec: dict, pages: list[dict]) -> str:
    sidebar_items = app_shell.get("sidebar_items") or []
    top_actions = app_shell.get("top_actions") or []
    panels = app_shell.get("workspace_panels") or []
    site_name = html.escape(str(spec.get("site_name") or "Brahma Studio"))
    tagline = html.escape(str(spec.get("tagline") or spec.get("about") or ""))

    sidebar_html = "".join(
        f'<button class="sidebar-item" type="button">{html.escape(str(item))}</button>'
        for item in sidebar_items
    )
    action_html = "".join(
        f'<button class="button button-secondary app-action" type="button">{html.escape(str(action))}</button>'
        for action in top_actions
    )
    panel_html = "".join(
        f'''
        <article class="workspace-card">
          <span>{html.escape(str(panel.get("title") or "Panel"))}</span>
          <h3>{html.escape(str(panel.get("title") or "Panel"))}</h3>
          <p>{html.escape(str(panel.get("description") or ""))}</p>
        </article>
        '''
        for panel in panels
    )
    nav_html = _render_nav_links(pages, "index")

    return f"""
    <div class="app-shell">
      <aside class="app-sidebar">
        <div class="brand brand-app">
          <span class="brand-mark">{html.escape((site_name[:1] or "B").upper())}</span>
          <div>
            <p>Brahma AI Studio</p>
            <h1>{site_name}</h1>
          </div>
        </div>
        <div class="sidebar-group">
          <span class="sidebar-label">Workspace</span>
          {sidebar_html}
        </div>
        <div class="sidebar-meta">
          <p>{tagline}</p>
        </div>
      </aside>
      <section class="app-main">
        <header class="app-topbar">
          <div>
            <span class="kicker">AI Studio</span>
            <h1>{site_name}</h1>
            <p>{tagline}</p>
          </div>
          <div class="app-top-actions">{action_html}</div>
        </header>
        <div class="app-nav">{nav_html}</div>
        <div class="app-hero">
          <div class="app-hero-copy">
            <span class="kicker">Build, preview, and ship</span>
            <h2>Create SaaS pages like Google AI Studio</h2>
            <p>Choose a brief and Brahma generates a front-end workspace plus backend APIs in a proper app structure, then launches the preview automatically.</p>
          </div>
          <div class="app-hero-panel">
            <div class="app-hero-stat"><strong>Frontend</strong><span>React-style UI or static dashboard pages</span></div>
            <div class="app-hero-stat"><strong>Backend</strong><span>Local API server with app routes</span></div>
            <div class="app-hero-stat"><strong>Preview</strong><span>Runs in browser immediately after generation</span></div>
          </div>
        </div>
        <div class="workspace-grid">
          {panel_html}
        </div>
        <section class="app-console">
          <div>
            <span>Prompt</span>
            <p>Tell Brahma what the SaaS app should do, who it is for, and what pages or features it needs.</p>
          </div>
          <div class="app-console-bar">Generate a landing page, dashboard, auth flow, pricing, and API surface.</div>
        </section>
      </section>
    </div>
    """


def _render_page_html(spec: dict, page: dict, pages: list[dict]) -> str:
    theme = _build_theme(spec)
    page_title = html.escape(str(page.get("title") or spec.get("site_name") or PROJECT_NAME))
    site_name = html.escape(str(spec.get("site_name") or PROJECT_NAME))
    tagline = html.escape(str(page.get("summary") or spec.get("tagline") or spec.get("about") or ""))
    about = html.escape(str(spec.get("about") or tagline))
    primary_cta = html.escape(str(spec.get("primary_cta") or "Get Started"))
    secondary_cta = html.escape(str(spec.get("secondary_cta") or "Learn More"))
    hero_metrics = spec.get("hero_metrics") or []
    features = spec.get("features") or []
    steps = spec.get("steps") or []
    testimonials = spec.get("testimonials") or []
    faq_items = spec.get("faq") or []
    showcase = spec.get("showcase") or {}
    contact = spec.get("contact") or {}
    app_shell = spec.get("app_shell") or {}
    nav_links = _render_nav_links(pages, page.get("slug") or "index")

    hero_metric_html = "".join(
        f'<div class="metric"><strong>{html.escape(str(item.get("value") or ""))}</strong><span>{html.escape(str(item.get("label") or ""))}</span></div>'
        for item in hero_metrics[:3]
    )

    feature_cards = _render_feature_cards(features[:8])
    step_rows = _render_steps(steps[:4])
    testimonial_cards = _render_testimonials(testimonials[:3])
    faq_html = _render_faq(faq_items[:6])

    if app_shell:
        hero_html = _render_app_shell(app_shell, spec, pages)
    else:
        hero_html = f"""
        <section class="hero">
          <div class="hero-copy">
            <span class="kicker">{html.escape(str(spec.get("style") or "Premium Web Design"))}</span>
            <h1>{page_title}</h1>
            <p>{tagline}</p>
            <p class="hero-note">{about}</p>
            <div class="hero-actions">
              <a class="button button-primary" href="#features">{primary_cta}</a>
              <a class="button button-secondary" href="#faq">{secondary_cta}</a>
            </div>
            <div class="hero-metrics">{hero_metric_html}</div>
          </div>
          <div class="hero-panel">
            <div class="orb"></div>
            <div class="panel-card">
              <span>Live preview</span>
              <h2>{site_name}</h2>
              <p>{html.escape(str(spec.get("tagline") or ""))}</p>
            </div>
          </div>
        </section>
        """

    html_template = Template(
        r"""<!doctype html>
<html lang="en">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <meta name="theme-color" content="#$accent">
  <title>$page_title</title>
  <meta name="description" content="$description">
  <link rel="preconnect" href="https://fonts.googleapis.com">
  <link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
  <link href="https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700;800&display=swap" rel="stylesheet">
  <link rel="stylesheet" href="styles.css">
</head>
<body id="top">
  <div class="ambient ambient-a"></div>
  <div class="ambient ambient-b"></div>
  <header class="site-header">
    <div class="brand">
      <span class="brand-mark">$brand_mark</span>
      <div>
        <p>$brand_kicker</p>
        <h1>$site_name</h1>
      </div>
    </div>
    <button class="nav-toggle" type="button" aria-label="Toggle navigation">Menu</button>
    <nav class="site-nav">
      $nav_links
    </nav>
  </header>

  <main>
    $hero_html

    <section class="stats-grid" id="stats">
      $stats_html
    </section>

    <section class="feature-section" id="features">
      <div class="section-heading">
        <span>Core highlights</span>
        <h2>Designed to feel premium, fast, and intentional</h2>
        <p>A practical website system with strong visuals and real conversion structure.</p>
      </div>
      <div class="feature-grid">
        $feature_cards
      </div>
    </section>

    <section class="split-layout" id="process">
      <div class="section-heading">
        <span>How it works</span>
        <h2>Built in a clear content flow</h2>
        <p>The layout helps users understand the offer quickly and keeps them moving toward action.</p>
      </div>
      <div class="steps">
        $step_rows
      </div>
    </section>

    $showcase_html

    <section class="testimonial-section">
      <div class="section-heading">
        <span>Social proof</span>
        <h2>Looks like a real brand site</h2>
      </div>
      <div class="testimonial-grid">
        $testimonial_cards
      </div>
    </section>

    <section class="faq-section" id="faq">
      <div class="section-heading">
        <span>FAQ</span>
        <h2>Questions, answered</h2>
      </div>
      <div class="faq-list">
        $faq_html
      </div>
    </section>

    $contact_html
  </main>

  <footer class="site-footer">
    <span>Created with Brahma AI - Lite</span>
    <span>$site_name</span>
  </footer>

  <script src="script.js"></script>
</body>
</html>
"""
    )

    showcase_html = _render_showcase(showcase)
    contact_html = _render_contact(contact)
    description = html.escape(str(spec.get("about") or spec.get("tagline") or ""))

    return html_template.substitute(
        accent=theme["accent"],
        page_title=page_title,
        description=description,
        brand_mark=html.escape((site_name[:1] or "B").upper()),
        brand_kicker="Brahma Web Builder",
        site_name=site_name,
        nav_links=nav_links,
        hero_html=hero_html,
        stats_html=_render_stat_cards(spec.get("hero_metrics") or []),
        feature_cards=feature_cards,
        step_rows=step_rows,
        showcase_html=showcase_html,
        testimonial_cards=testimonial_cards,
        faq_html=faq_html,
        contact_html=contact_html,
    )


def _render_styles(spec: dict) -> str:
    theme = _build_theme(spec)
    css = r"""
:root {{
  --bg: #{theme['bg']};
  --surface: #{theme['surface']};
  --surface-alt: #{theme['surface_alt']};
  --text: #{theme['text']};
  --muted: #{theme['muted']};
  --accent: #{theme['accent']};
  --accent-alt: #{theme['accent_alt']};
  --border: rgba(255, 255, 255, 0.08);
  --shadow: 0 24px 80px rgba(0, 0, 0, 0.42);
}

* {{
  box-sizing: border-box;
}}

html {{
  scroll-behavior: smooth;
}}

body {{
  margin: 0;
  font-family: "Inter", system-ui, sans-serif;
  background:
    radial-gradient(circle at top left, rgba(124, 92, 255, 0.18), transparent 36%),
    radial-gradient(circle at top right, rgba(24, 211, 197, 0.12), transparent 30%),
    linear-gradient(180deg, #05070b 0%, var(--bg) 100%);
  color: var(--text);
  min-height: 100vh;
  overflow-x: hidden;
}}

a {{
  color: inherit;
  text-decoration: none;
}}

.ambient {{
  position: fixed;
  inset: auto;
  width: 32rem;
  height: 32rem;
  border-radius: 50%;
  filter: blur(70px);
  opacity: 0.32;
  pointer-events: none;
  z-index: 0;
}}

.ambient-a {{
  top: -8rem;
  left: -10rem;
  background: rgba(124, 92, 255, 0.4);
}}

.ambient-b {{
  right: -10rem;
  bottom: -10rem;
  background: rgba(24, 211, 197, 0.28);
}}

.site-header,
main,
.site-footer {{
  position: relative;
  z-index: 1;
}}

.site-header {{
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 1rem;
  max-width: 1240px;
  margin: 0 auto;
  padding: 1.25rem 1.5rem;
}}

.brand {{
  display: flex;
  align-items: center;
  gap: 0.95rem;
}}

.brand-mark {{
  width: 3rem;
  height: 3rem;
  border-radius: 1rem;
  display: grid;
  place-items: center;
  background: linear-gradient(135deg, rgba(124, 92, 255, 0.28), rgba(24, 211, 197, 0.22));
  border: 1px solid var(--border);
  box-shadow: var(--shadow);
  font-weight: 800;
  letter-spacing: 0.06em;
}}

.brand p {{
  margin: 0;
  color: var(--muted);
  font-size: 0.78rem;
  letter-spacing: 0.16em;
  text-transform: uppercase;
}}

.brand h1 {{
  margin: 0.15rem 0 0;
  font-size: 1.05rem;
}}

.nav-toggle {{
  display: none;
  background: transparent;
  color: var(--text);
  border: 1px solid var(--border);
  border-radius: 999px;
  padding: 0.7rem 1rem;
}}

.site-nav {{
  display: flex;
  gap: 0.6rem;
  align-items: center;
  flex-wrap: wrap;
}}

.site-nav a {{
  padding: 0.7rem 1rem;
  border-radius: 999px;
  color: var(--muted);
  border: 1px solid transparent;
  transition: 180ms ease;
}}

.site-nav a:hover,
.site-nav a.active {{
  color: var(--text);
  border-color: var(--border);
  background: rgba(255, 255, 255, 0.03);
}}

main {{
  max-width: 1240px;
  margin: 0 auto;
  padding: 1rem 1.5rem 4rem;
}}

.hero {{
  display: grid;
  grid-template-columns: 1.3fr 0.9fr;
  gap: 1.5rem;
  min-height: 36rem;
  align-items: center;
}}

.hero-copy,
.hero-panel,
.feature-card,
.stat-card,
.step,
.testimonial-card,
.faq-item,
.contact-panel {{
  background: linear-gradient(180deg, rgba(255, 255, 255, 0.04), rgba(255, 255, 255, 0.02));
  border: 1px solid var(--border);
  border-radius: 1.5rem;
  box-shadow: var(--shadow);
}}

.hero-copy {{
  padding: 2.2rem;
}}

.kicker,
.section-heading span,
.contact-panel span {{
  display: inline-flex;
  width: fit-content;
  margin-bottom: 1rem;
  padding: 0.45rem 0.8rem;
  border-radius: 999px;
  border: 1px solid rgba(255, 255, 255, 0.08);
  color: var(--accent-alt);
  background: rgba(255, 255, 255, 0.03);
  letter-spacing: 0.08em;
  text-transform: uppercase;
  font-size: 0.72rem;
  font-weight: 700;
}

.hero h1 {{
  margin: 0;
  font-size: clamp(3rem, 5vw, 5.4rem);
  line-height: 0.95;
  letter-spacing: -0.05em;
}}

.hero p {{
  color: var(--muted);
  font-size: 1.06rem;
  line-height: 1.7;
  max-width: 62ch;
}}

.hero-note {{
  max-width: 52ch;
}}

.hero-actions {{
  display: flex;
  flex-wrap: wrap;
  gap: 0.8rem;
  margin: 1.6rem 0 1.9rem;
}}

.button {{
  display: inline-flex;
  align-items: center;
  justify-content: center;
  min-height: 3rem;
  padding: 0.85rem 1.25rem;
  border-radius: 999px;
  border: 1px solid var(--border);
  transition: transform 160ms ease, border-color 160ms ease, background 160ms ease;
}}

.button:hover {{
  transform: translateY(-1px);
}}

.button-primary {{
  background: linear-gradient(135deg, var(--accent), var(--accent-alt));
  color: #06111b;
  font-weight: 800;
}}

.button-secondary {{
  background: rgba(255, 255, 255, 0.04);
  color: var(--text);
}}

.hero-metrics {{
  display: grid;
  grid-template-columns: repeat(3, minmax(0, 1fr));
  gap: 0.8rem;
}}

.metric {{
  padding: 0.95rem 1rem;
  border-radius: 1rem;
  background: rgba(255, 255, 255, 0.03);
  border: 1px solid rgba(255, 255, 255, 0.06);
}}

.metric strong {{
  display: block;
  font-size: 1.1rem;
}}

.metric span {{
  color: var(--muted);
  font-size: 0.82rem;
}}

.hero-panel {{
  position: relative;
  min-height: 28rem;
  display: grid;
  place-items: center;
  overflow: hidden;
}}

.orb {{
  position: absolute;
  width: 18rem;
  height: 18rem;
  border-radius: 50%;
  background:
    radial-gradient(circle at 35% 35%, rgba(255, 255, 255, 0.38), transparent 18%),
    radial-gradient(circle at center, rgba(124, 92, 255, 0.48), rgba(24, 211, 197, 0.18) 42%, rgba(0, 0, 0, 0) 64%);
  filter: blur(0.5px);
  animation: float 8s ease-in-out infinite;
}}

.panel-card {{
  position: relative;
  width: min(22rem, calc(100% - 2rem));
  padding: 1.4rem;
  border-radius: 1.3rem;
  background: rgba(6, 10, 18, 0.75);
  backdrop-filter: blur(14px);
  border: 1px solid rgba(255, 255, 255, 0.08);
}}

.panel-card span {{
  color: var(--muted);
  font-size: 0.82rem;
  text-transform: uppercase;
  letter-spacing: 0.14em;
}}

.panel-card h2 {{
  margin: 0.45rem 0 0.35rem;
  font-size: 2rem;
}}

.panel-card p {{
  margin: 0;
  color: var(--muted);
}}

.stats-grid {{
  display: grid;
  grid-template-columns: repeat(3, minmax(0, 1fr));
  gap: 1rem;
  margin: 1.2rem 0 2.4rem;
}}

.stat-card {{
  padding: 1.2rem 1.25rem;
}}

.stat-card span {{
  display: block;
  color: var(--muted);
  font-size: 0.78rem;
  text-transform: uppercase;
  letter-spacing: 0.15em;
}}

.stat-card strong {{
  display: block;
  margin-top: 0.35rem;
  font-size: 1.5rem;
}}

.section-heading {{
  max-width: 44rem;
  margin-bottom: 1.2rem;
}}

.section-heading h2 {{
  margin: 0;
  font-size: clamp(1.7rem, 2.6vw, 2.8rem);
  letter-spacing: -0.04em;
}}

.section-heading p {{
  margin: 0.7rem 0 0;
  color: var(--muted);
  line-height: 1.7;
}}

.feature-section,
.split-layout,
.testimonial-section,
.faq-section {{
  margin-top: 1rem;
  padding: 1rem 0 2rem;
}}

.feature-grid {{
  display: grid;
  grid-template-columns: repeat(4, minmax(0, 1fr));
  gap: 1rem;
}}

.feature-card {{
  padding: 1.25rem;
  min-height: 11rem;
}}

.feature-card h3 {{
  margin: 0 0 0.65rem;
  font-size: 1.05rem;
}}

.feature-card p {{
  margin: 0;
  color: var(--muted);
  line-height: 1.65;
}}

.steps {{
  display: grid;
  grid-template-columns: repeat(3, minmax(0, 1fr));
  gap: 1rem;
}}

.step {{
  display: grid;
  grid-template-columns: auto 1fr;
  gap: 1rem;
  padding: 1.25rem;
}}

.step span {{
  width: 2.6rem;
  height: 2.6rem;
  border-radius: 0.9rem;
  display: grid;
  place-items: center;
  font-weight: 800;
  color: #07121a;
  background: linear-gradient(135deg, var(--accent), var(--accent-alt));
}}

.step h3 {{
  margin: 0;
  font-size: 1.02rem;
}}

.step p {{
  margin: 0.4rem 0 0;
  color: var(--muted);
  line-height: 1.6;
}}

.showcase {{
  margin: 2rem 0;
  padding: 1.4rem 1.2rem 1.6rem;
  border-radius: 1.5rem;
  background:
    linear-gradient(180deg, rgba(255, 255, 255, 0.04), rgba(255, 255, 255, 0.02)),
    radial-gradient(circle at top right, rgba(24, 211, 197, 0.12), transparent 30%);
  border: 1px solid var(--border);
}}

.showcase-list {{
  display: grid;
  grid-template-columns: repeat(3, minmax(0, 1fr));
  gap: 0.8rem;
  list-style: none;
  padding: 0;
  margin: 1rem 0 0;
}}

.showcase-list li {{
  padding: 1rem 1rem 1rem 1.1rem;
  border-radius: 1rem;
  background: rgba(255, 255, 255, 0.03);
  border: 1px solid rgba(255, 255, 255, 0.06);
}}

.testimonial-grid {{
  display: grid;
  grid-template-columns: repeat(3, minmax(0, 1fr));
  gap: 1rem;
}}

.testimonial-card {{
  padding: 1.25rem;
}}

.testimonial-card .quote {{
  margin: 0 0 1rem;
  color: var(--text);
  line-height: 1.7;
}}

.testimonial-card strong,
.testimonial-card span {{
  display: block;
}}

.testimonial-card span {{
  color: var(--muted);
  margin-top: 0.25rem;
}}

.faq-list {{
  display: grid;
  gap: 0.8rem;
}}

.faq-item {{
  padding: 0.95rem 1.05rem;
}}

.faq-item summary {{
  cursor: pointer;
  list-style: none;
  font-weight: 700;
}}

.faq-item summary::-webkit-details-marker {{
  display: none;
}}

.faq-item p {{
  margin: 0.8rem 0 0;
  color: var(--muted);
  line-height: 1.65;
}}

.app-shell {{
  display: grid;
  grid-template-columns: 18rem 1fr;
  gap: 1.25rem;
  min-height: 100vh;
}}

.app-sidebar {{
  padding: 1.25rem;
  border-radius: 1.4rem;
  background: rgba(255, 255, 255, 0.03);
  border: 1px solid var(--border);
  box-shadow: var(--shadow);
  display: flex;
  flex-direction: column;
  gap: 1.2rem;
  position: sticky;
  top: 1rem;
  height: fit-content;
}}

.brand-app {{
  align-items: flex-start;
}}

.sidebar-group {{
  display: grid;
  gap: 0.6rem;
}}

.sidebar-label {{
  color: var(--muted);
  text-transform: uppercase;
  letter-spacing: 0.14em;
  font-size: 0.72rem;
}}

.sidebar-item {{
  width: 100%;
  text-align: left;
  padding: 0.9rem 1rem;
  border-radius: 1rem;
  border: 1px solid rgba(255, 255, 255, 0.06);
  background: rgba(255, 255, 255, 0.03);
  color: var(--text);
}}

.sidebar-meta {{
  margin-top: auto;
  padding-top: 0.75rem;
  border-top: 1px solid rgba(255, 255, 255, 0.06);
}}

.sidebar-meta p {{
  margin: 0;
  color: var(--muted);
  line-height: 1.6;
}}

.app-main {{
  display: grid;
  gap: 1rem;
}}

.app-topbar {{
  display: flex;
  justify-content: space-between;
  gap: 1rem;
  align-items: center;
  padding: 1.2rem 1.25rem;
  border-radius: 1.4rem;
  border: 1px solid var(--border);
  background: rgba(255, 255, 255, 0.03);
}}

.app-topbar h1 {{
  margin: 0.2rem 0 0;
  font-size: 2rem;
}}

.app-topbar p {{
  margin: 0.35rem 0 0;
  color: var(--muted);
}}

.app-top-actions {{
  display: flex;
  flex-wrap: wrap;
  gap: 0.65rem;
}}

.app-action {{
  min-width: 6.5rem;
}}

.app-nav {{
  display: flex;
  flex-wrap: wrap;
  gap: 0.6rem;
  padding: 0 0.25rem;
}

.app-nav a {{
  padding: 0.55rem 0.85rem;
  border-radius: 999px;
  color: var(--muted);
  border: 1px solid rgba(255, 255, 255, 0.06);
  background: rgba(255, 255, 255, 0.02);
}}

.app-nav a.active {{
  color: #07111b;
  background: linear-gradient(135deg, var(--accent), var(--accent-alt));
}}

.app-hero {{
  display: grid;
  grid-template-columns: 1.1fr 0.9fr;
  gap: 1rem;
}}

.app-hero-copy,
.app-hero-panel,
.workspace-card,
.app-console {{
  border-radius: 1.3rem;
  border: 1px solid var(--border);
  background: rgba(255, 255, 255, 0.03);
  box-shadow: var(--shadow);
}}

.app-hero-copy {{
  padding: 1.35rem;
}}

.app-hero-copy h2 {{
  margin: 0.35rem 0 0.55rem;
  font-size: clamp(1.8rem, 3vw, 3rem);
}}

.app-hero-copy p {{
  margin: 0;
  color: var(--muted);
  line-height: 1.7;
}}

.app-hero-panel {{
  padding: 1rem;
  display: grid;
  gap: 0.75rem;
}}

.app-hero-stat {{
  padding: 1rem;
  border-radius: 1rem;
  background: rgba(255, 255, 255, 0.03);
}

.app-hero-stat strong {{
  display: block;
  margin-bottom: 0.25rem;
}}

.app-hero-stat span {{
  color: var(--muted);
}}

.workspace-grid {{
  display: grid;
  grid-template-columns: repeat(3, minmax(0, 1fr));
  gap: 1rem;
}}

.workspace-card {{
  padding: 1.2rem;
}}

.workspace-card span {{
  color: var(--muted);
  text-transform: uppercase;
  letter-spacing: 0.12em;
  font-size: 0.72rem;
}}

.workspace-card h3 {{
  margin: 0.5rem 0 0.4rem;
  font-size: 1.1rem;
}}

.workspace-card p {{
  margin: 0;
  color: var(--muted);
  line-height: 1.6;
}}

.app-console {{
  display: flex;
  justify-content: space-between;
  gap: 1rem;
  align-items: center;
  padding: 1.2rem 1.25rem;
}}

.app-console span {{
  color: var(--muted);
  text-transform: uppercase;
  letter-spacing: 0.12em;
  font-size: 0.72rem;
}}

.app-console p {{
  margin: 0.35rem 0 0;
  color: var(--muted);
}}

.app-console-bar {{
  padding: 0.95rem 1rem;
  border-radius: 1rem;
  background: linear-gradient(135deg, rgba(124, 92, 255, 0.18), rgba(24, 211, 197, 0.12));
  border: 1px solid rgba(255, 255, 255, 0.08);
  color: var(--text);
}

.contact-panel {{
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 1rem;
  padding: 1.4rem;
  margin-top: 2rem;
}}

.contact-panel h2 {{
  margin: 0.3rem 0 0.5rem;
  font-size: clamp(1.5rem, 2vw, 2.2rem);
}}

.contact-panel p {{
  margin: 0;
  color: var(--muted);
  line-height: 1.65;
}}

.site-footer {{
  max-width: 1240px;
  margin: 0 auto;
  padding: 1rem 1.5rem 2.5rem;
  display: flex;
  justify-content: space-between;
  gap: 1rem;
  color: var(--muted);
  border-top: 1px solid rgba(255, 255, 255, 0.06);
}}

.site-footer span:last-child {{
  color: var(--text);
}}

.reveal {{
  opacity: 0;
  transform: translateY(18px);
  transition: opacity 520ms ease, transform 520ms ease;
}}

.reveal.visible {{
  opacity: 1;
  transform: translateY(0);
}}

@keyframes float {{
  0%, 100% {{ transform: translateY(0); }}
  50% {{ transform: translateY(-12px); }}
}}

@media (max-width: 1100px) {{
  .hero,
  .feature-grid,
  .steps,
  .testimonial-grid,
  .showcase-list,
  .stats-grid {{
    grid-template-columns: 1fr 1fr;
  }}

  .contact-panel,
  .site-header {{
    flex-direction: column;
    align-items: stretch;
  }}

  .nav-toggle {{
    display: inline-flex;
    align-self: flex-start;
  }}

  .site-nav {{
    display: none;
    flex-direction: column;
    align-items: stretch;
    width: 100%;
  }}

  body.nav-open .site-nav {{
    display: flex;
  }}
}}

@media (max-width: 720px) {{
  main {{
    padding-inline: 1rem;
  }}

  .hero,
  .feature-grid,
  .steps,
  .testimonial-grid,
  .showcase-list,
  .stats-grid {{
    grid-template-columns: 1fr;
  }}

  .hero-copy,
  .hero-panel,
  .contact-panel {{
    padding: 1.2rem;
  }}

  .hero-metrics {{
    grid-template-columns: 1fr;
  }}
}}
"""
    css = (
        css
        .replace("#{theme['bg']}", f"#{theme['bg']}")
        .replace("#{theme['surface']}", f"#{theme['surface']}")
        .replace("#{theme['surface_alt']}", f"#{theme['surface_alt']}")
        .replace("#{theme['text']}", f"#{theme['text']}")
        .replace("#{theme['muted']}", f"#{theme['muted']}")
        .replace("#{theme['accent']}", f"#{theme['accent']}")
        .replace("#{theme['accent_alt']}", f"#{theme['accent_alt']}")
    )
    return css.replace("{{", "{").replace("}}", "}")


def _render_site_data(spec: dict, pages: list[dict]) -> str:
    payload = dict(spec or {})
    payload["pages"] = pages
    return json.dumps(payload, indent=2, ensure_ascii=False)


def _render_backend_server(frontend_dir_name: str) -> str:
    return f"""from __future__ import annotations

import argparse
import json
from functools import partial
from http import HTTPStatus
from http.server import ThreadingHTTPServer, SimpleHTTPRequestHandler
from pathlib import Path
from urllib.parse import urlparse

BASE_DIR = Path(__file__).resolve().parent.parent
FRONTEND_DIR = BASE_DIR / {frontend_dir_name!r}
DATA_PATH = Path(__file__).resolve().parent / "site_data.json"


class BrahmaHandler(SimpleHTTPRequestHandler):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, directory=str(FRONTEND_DIR), **kwargs)

    def _send_json(self, payload, status=HTTPStatus.OK):
        body = json.dumps(payload, ensure_ascii=False, indent=2).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Cache-Control", "no-store")
        self.end_headers()
        self.wfile.write(body)

    def do_GET(self):
        parsed = urlparse(self.path)
        if parsed.path == "/api/health":
            return self._send_json({{"ok": True, "app": "Brahma Website Builder"}})
        if parsed.path == "/api/dashboard":
            try:
                payload = json.loads(DATA_PATH.read_text(encoding="utf-8"))
            except Exception as exc:
                return self._send_json({{"error": str(exc)}}, status=HTTPStatus.INTERNAL_SERVER_ERROR)
            shell = payload.get("app_shell") or {{}}
            return self._send_json({{
                "site_name": payload.get("site_name"),
                "tagline": payload.get("tagline"),
                "style": payload.get("style"),
                "sidebar_items": shell.get("sidebar_items", []),
                "workspace_panels": shell.get("workspace_panels", []),
                "top_actions": shell.get("top_actions", []),
            }})
        if parsed.path == "/api/site-data":
            try:
                payload = json.loads(DATA_PATH.read_text(encoding="utf-8"))
            except Exception as exc:
                return self._send_json({{"error": str(exc)}}, status=HTTPStatus.INTERNAL_SERVER_ERROR)
            return self._send_json(payload)
        if parsed.path == "/api/chat":
            try:
                payload = json.loads(DATA_PATH.read_text(encoding="utf-8"))
            except Exception:
                payload = {{}}
            return self._send_json({{
                "reply": f"Brahma Studio is ready to build {{payload.get('site_name', 'your app')}}.",
                "status": "online",
            }})
        return super().do_GET()

    def do_POST(self):
        parsed = urlparse(self.path)
        if parsed.path != "/api/contact":
            return super().do_POST()
        length = int(self.headers.get("Content-Length", "0") or "0")
        raw = self.rfile.read(length).decode("utf-8") if length else ""
        try:
            payload = json.loads(raw) if raw else {{}}
        except Exception:
            payload = {{"raw": raw}}
        return self._send_json({{"ok": True, "received": payload}})


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--port", type=int, default=8787)
    args = parser.parse_args()
    server = ThreadingHTTPServer(("127.0.0.1", args.port), BrahmaHandler)
    print(f"Serving Brahma website at http://127.0.0.1:{{args.port}}", flush=True)
    server.serve_forever()


if __name__ == "__main__":
    main()
"""


def _launch_preview(server_path: Path, port: int) -> None:
    try:
        creationflags = 0
        if os.name == "nt":
            creationflags = subprocess.CREATE_NEW_PROCESS_GROUP | subprocess.DETACHED_PROCESS  # type: ignore[attr-defined]
        subprocess.Popen(
            [sys.executable, str(server_path), "--port", str(port)],
            cwd=str(server_path.parent),
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            creationflags=creationflags,
        )
        webbrowser.open(f"http://127.0.0.1:{port}")
    except Exception:
        _open_path(server_path)


def _preview_url(port: int) -> str:
    return f"http://127.0.0.1:{port}"


def _health_url(port: int) -> str:
    return f"http://127.0.0.1:{port}/api/health"


def _wait_for_health(port: int, timeout: int = 25) -> tuple[bool, str]:
    deadline = time.time() + timeout
    last_error = ""
    while time.time() < deadline:
        try:
            with urllib.request.urlopen(_health_url(port), timeout=2) as resp:
                if resp.status == 200:
                    return True, ""
                last_error = f"Health check returned {resp.status}"
        except Exception as e:
            last_error = str(e)
        time.sleep(0.5)
    return False, last_error or "Timed out waiting for preview server."


def _compile_python(path: Path) -> tuple[bool, str]:
    try:
        result = subprocess.run(
            [sys.executable, "-m", "py_compile", str(path)],
            capture_output=True,
            text=True,
            cwd=str(path.parent),
        )
        if result.returncode == 0:
            return True, ""
        return False, (result.stderr or result.stdout or "Unknown compile failure").strip()
    except Exception as e:
        return False, str(e)


def _write_backend_stack(backend_dir: Path, spec: dict, frontend_dir_name: str = "frontend") -> None:
    backend_dir.mkdir(parents=True, exist_ok=True)
    (backend_dir / "server.py").write_text(_render_backend_server(frontend_dir_name), encoding="utf-8")
    pages = spec.get("pages") or []
    (backend_dir / "site_data.json").write_text(_render_site_data(spec, pages), encoding="utf-8")


def _repair_launch_failure(output_dir: Path, spec: dict, failure_text: str) -> list[str]:
    notes: list[str] = []
    backend_dir = output_dir / "backend"
    frontend_dir = output_dir / "frontend"
    low = (failure_text or "").lower()

    if any(token in low for token in ("syntaxerror", "indentationerror", "unexpected indent", "invalid syntax", "nameerror", "importerror")):
        _write_backend_stack(backend_dir, spec)
        notes.append("Rewrote backend/server.py after a Python syntax/import failure.")

    if "address already in use" in low or "port" in low and "in use" in low:
        notes.append("Port conflict detected; a fresh port will be selected on retry.")

    index_path = frontend_dir / "index.html"
    if not index_path.exists():
        pages = spec.get("pages") or []
        if not pages:
            pages = [{"slug": "index", "title": spec.get("site_name") or "Brahma Studio", "summary": spec.get("tagline") or ""}]
        for page in pages:
            _write_page(frontend_dir, spec, page, pages)
        (frontend_dir / "styles.css").write_text(_render_styles(spec), encoding="utf-8")
        (frontend_dir / "script.js").write_text(_render_script(), encoding="utf-8")
        notes.append("Rebuilt the frontend files because they were missing.")

    return notes


def _ai_debug_patch(output_dir: Path, spec: dict, failure_text: str) -> list[str]:
    try:
        client = _ai_client()
        prompt = f"""
You are a senior debugging agent inside a website builder.
The generated web app failed to start. Diagnose the root cause and return ONLY JSON.

Allowed file targets:
- backend/server.py
- backend/site_data.json
- frontend/index.html
- frontend/styles.css
- frontend/script.js

Return JSON in this exact shape:
{{
  "summary": "short explanation",
  "fixes": [
    {{"path": "backend/server.py", "content": "full file content"}},
    {{"path": "frontend/script.js", "content": "full file content"}}
  ]
}}

Guidelines:
- Fix the actual startup blocker first.
- Keep the architecture simple and resilient.
- If a file does not need changing, omit it.
- Do not include markdown.

Project spec:
{json.dumps(spec, indent=2, ensure_ascii=False)[:10000]}

Failure log:
{(failure_text or "No failure log provided.")[:12000]}
"""
        response = client.models.generate_content(model="gemini-2.5-flash", contents=prompt)
        raw = _extract_text(response)
        raw = re.sub(r"```(?:json)?", "", raw).strip().rstrip("`").strip()
        data = json.loads(raw)
        fixes = data.get("fixes") if isinstance(data, dict) else None
        if not isinstance(fixes, list):
            return []

        applied: list[str] = []
        for fix in fixes:
            if not isinstance(fix, dict):
                continue
            rel_path = str(fix.get("path") or "").replace("\\", "/").strip()
            content = fix.get("content")
            if not rel_path or not isinstance(content, str):
                continue
            target = (output_dir / rel_path).resolve()
            if output_dir.resolve() not in target.parents and target != output_dir.resolve():
                continue
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_text(content, encoding="utf-8")
            applied.append(rel_path)

        if applied:
            backend_dir = output_dir / "backend"
            pages = spec.get("pages") or []
            (backend_dir / "site_data.json").write_text(_render_site_data(spec, pages), encoding="utf-8")
        return applied
    except Exception:
        return []


def _start_and_verify_preview(output_dir: Path, spec: dict, auto_open: bool) -> str:
    backend_dir = output_dir / "backend"
    server_path = backend_dir / "server.py"
    if not server_path.exists():
        _write_backend_stack(backend_dir, spec)

    compile_ok, compile_error = _compile_python(server_path)
    if not compile_ok:
        notes = _repair_launch_failure(output_dir, spec, compile_error)
        if not notes:
            notes = _ai_debug_patch(output_dir, spec, compile_error)
        compile_ok, compile_error = _compile_python(server_path)
        if not compile_ok:
            return f"Website created, but backend could not compile: {compile_error}"

    attempts: list[str] = []
    for attempt in range(1, 4):
        port = _find_free_port(8787 + (attempt - 1) * 10, 8899)
        creationflags = 0
        if os.name == "nt":
            creationflags = subprocess.CREATE_NEW_PROCESS_GROUP | subprocess.DETACHED_PROCESS  # type: ignore[attr-defined]

        proc = subprocess.Popen(
            [sys.executable, str(server_path), "--port", str(port)],
            cwd=str(backend_dir),
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            encoding="utf-8",
            errors="replace",
            creationflags=creationflags,
        )

        ok, err = _wait_for_health(port, timeout=25)
        if ok:
            if auto_open:
                webbrowser.open(_preview_url(port))
            return f"Website app created and running: {_preview_url(port)}"

        failure_text = err
        try:
            if proc.poll() is None:
                proc.terminate()
                try:
                    proc.wait(timeout=5)
                except Exception:
                    proc.kill()
            stdout = proc.stdout.read() if proc.stdout else ""
            stderr = proc.stderr.read() if proc.stderr else ""
            failure_text = "\n".join(part for part in [err, stdout, stderr] if part).strip()
        except Exception:
            pass

        attempts.append(f"Attempt {attempt}: {failure_text[:300]}")
        repair_notes = _repair_launch_failure(output_dir, spec, failure_text)
        if repair_notes:
            compile_ok, compile_error = _compile_python(server_path)
            if not compile_ok:
                attempts.append(f"Repair compile failed: {compile_error[:300]}")
                continue
            continue

        ai_fixes = _ai_debug_patch(output_dir, spec, failure_text)
        if ai_fixes:
            compile_ok, compile_error = _compile_python(server_path)
            if not compile_ok:
                attempts.append(f"AI repair compile failed: {compile_error[:300]}")
                continue
            continue

    details = " | ".join(attempts[-3:]) if attempts else "Unknown launch failure."
    return f"Website created, but preview could not start automatically. Debug log: {details}"


def _render_script() -> str:
    return """
const navToggle = document.querySelector('.nav-toggle');
const body = document.body;

if (navToggle) {
  navToggle.addEventListener('click', () => {
    body.classList.toggle('nav-open');
  });
}

const observer = new IntersectionObserver((entries) => {
  entries.forEach((entry) => {
    if (entry.isIntersecting) {
      entry.target.classList.add('visible');
    }
  });
}, { threshold: 0.12 });

document.querySelectorAll('section, .hero-copy, .hero-panel, .stat-card, .feature-card, .step, .testimonial-card, .faq-item, .contact-panel').forEach((el) => {
  el.classList.add('reveal');
  observer.observe(el);
});

async function hydrateDashboard() {
  const appShell = document.querySelector('.app-shell');
  if (!appShell) return;

  try {
    const res = await fetch('/api/dashboard', { cache: 'no-store' });
    if (!res.ok) return;
    const data = await res.json();
    const title = document.querySelector('.app-topbar h1');
    const desc = document.querySelector('.app-topbar p');
    if (title && data.site_name) title.textContent = data.site_name;
    if (desc && data.tagline) desc.textContent = data.tagline;
  } catch (err) {
    console.warn('Dashboard hydration failed', err);
  }
}

hydrateDashboard();
"""


def _write_page(frontend_dir: Path, spec: dict, page: dict, pages: list[dict]) -> Path:
    slug = _safe_slug(page.get("slug") or "index")
    filename = "index.html" if slug == "index" else f"{slug}.html"
    html_path = frontend_dir / filename
    html_path.write_text(_render_page_html(spec, page, pages), encoding="utf-8")
    return html_path


def website_builder(parameters: dict, player=None) -> str:
    params = parameters or {}
    action = (params.get("action") or "create").lower().strip()
    site_name = (params.get("site_name") or params.get("title") or "Brahma Studio").strip()
    output_dir = _resolve_output_dir(params.get("output_dir"), site_name)
    auto_open = bool(params.get("auto_open", True))
    pages_input = _parse_json_arg(params.get("pages"), None)

    if action in {"open", "launch"}:
        index_path = output_dir / "index.html"
        if not index_path.exists():
            return f"Website not found: {index_path}"
        _open_path(index_path)
        return f"Opened website preview: {index_path}"

    spec = _ai_spec(params)
    spec.setdefault("site_name", site_name)
    spec.setdefault("pages", [])

    pages = pages_input if isinstance(pages_input, list) else spec.get("pages") or []
    if not pages:
        pages = [{
            "slug": "index",
            "title": spec.get("site_name") or site_name,
            "summary": spec.get("tagline") or spec.get("about") or "",
        }]
    else:
        normalized_pages = []
        for idx, page in enumerate(pages):
            if isinstance(page, dict):
                normalized_pages.append({
                    "slug": page.get("slug") or ("index" if idx == 0 else f"page-{idx+1}"),
                    "title": page.get("title") or page.get("name") or f"Page {idx+1}",
                    "summary": page.get("summary") or page.get("description") or "",
                })
            else:
                normalized_pages.append({
                    "slug": "index" if idx == 0 else f"page-{idx+1}",
                    "title": str(page),
                    "summary": "",
                })
        pages = normalized_pages
        if not any((p.get("slug") or "").lower() == "index" for p in pages):
            pages.insert(0, {
                "slug": "index",
                "title": spec.get("site_name") or site_name,
                "summary": spec.get("tagline") or spec.get("about") or "",
            })

    frontend_dir = output_dir / "frontend"
    backend_dir = output_dir / "backend"
    frontend_dir.mkdir(parents=True, exist_ok=True)
    backend_dir.mkdir(parents=True, exist_ok=True)
    index_path = None
    for page in pages:
        page_path = _write_page(frontend_dir, spec, page, pages)
        if page_path.name == "index.html":
            index_path = page_path

    (frontend_dir / "styles.css").write_text(_render_styles(spec), encoding="utf-8")
    (frontend_dir / "script.js").write_text(_render_script(), encoding="utf-8")
    (backend_dir / "site_data.json").write_text(_render_site_data(spec, pages), encoding="utf-8")
    (backend_dir / "server.py").write_text(_render_backend_server("frontend"), encoding="utf-8")

    readme = output_dir / "README.txt"
    readme.write_text(
        f"{site_name}\n\nGenerated by Brahma AI - Lite.\n"
        f"Frontend: {frontend_dir}\n"
        f"Backend: {backend_dir}\n"
        f"Run backend/server.py to start the local preview server.\n",
        encoding="utf-8",
    )

    if auto_open:
        return _start_and_verify_preview(output_dir, spec, auto_open=True)

    return f"Website app created: {output_dir}"
