from __future__ import annotations

import json
import time
import urllib.error
import urllib.parse
import urllib.request
from pathlib import Path


BASE_DIR = Path(__file__).resolve().parent.parent
CONFIG_DIR = BASE_DIR / "config"
FIREBASE_CONFIG_PATH = CONFIG_DIR / "firebase_config.json"
SESSION_PATH = CONFIG_DIR / "firebase_session.json"

DEFAULT_FIREBASE_CONFIG = {
    "apiKey": "AIzaSyCNOc0L6Uo1aE9Nvi7iRbsBRn0PWXkUGv4",
    "authDomain": "brahma-ai-7b982.firebaseapp.com",
    "projectId": "brahma-ai-7b982",
    "storageBucket": "brahma-ai-7b982.firebasestorage.app",
    "messagingSenderId": "450124119082",
    "appId": "1:450124119082:web:68a48dd73f456d70695753",
    "measurementId": "G-4P31CQ2S3X",
}


class FirebaseAuthError(RuntimeError):
    pass


def load_firebase_config() -> dict:
    try:
        if FIREBASE_CONFIG_PATH.exists():
            data = json.loads(FIREBASE_CONFIG_PATH.read_text(encoding="utf-8"))
            if isinstance(data, dict) and data.get("apiKey"):
                return data
    except Exception:
        pass
    return dict(DEFAULT_FIREBASE_CONFIG)


def _api_key() -> str:
    return (load_firebase_config().get("apiKey") or "").strip()


def _extract_message(payload: str) -> str:
    try:
        data = json.loads(payload)
        err = data.get("error", {})
        msg = err.get("message") or err.get("status")
        if msg:
            return str(msg).replace("_", " ").title()
    except Exception:
        pass
    return payload.strip() or "Firebase request failed"


def _post_json(url: str, payload: dict, headers: dict | None = None) -> dict:
    body = json.dumps(payload).encode("utf-8")
    req = urllib.request.Request(
        url,
        data=body,
        headers={"Content-Type": "application/json", **(headers or {})},
        method="POST",
    )
    try:
        with urllib.request.urlopen(req, timeout=20) as resp:
            raw = resp.read().decode("utf-8")
        return json.loads(raw or "{}")
    except urllib.error.HTTPError as exc:
        body = exc.read().decode("utf-8", "replace")
        raise FirebaseAuthError(_extract_message(body)) from exc
    except Exception as exc:
        raise FirebaseAuthError(str(exc)) from exc


def _post_form(url: str, payload: dict, headers: dict | None = None) -> dict:
    body = urllib.parse.urlencode(payload).encode("utf-8")
    req = urllib.request.Request(
        url,
        data=body,
        headers={"Content-Type": "application/x-www-form-urlencoded", **(headers or {})},
        method="POST",
    )
    try:
        with urllib.request.urlopen(req, timeout=20) as resp:
            raw = resp.read().decode("utf-8")
        return json.loads(raw or "{}")
    except urllib.error.HTTPError as exc:
        body = exc.read().decode("utf-8", "replace")
        raise FirebaseAuthError(_extract_message(body)) from exc
    except Exception as exc:
        raise FirebaseAuthError(str(exc)) from exc


def _normalize_session(data: dict, email: str | None = None, setup_complete: bool = False) -> dict:
    expires_in = int(float(data.get("expiresIn") or data.get("expires_in") or 3600))
    now = time.time()
    refresh = data.get("refreshToken") or data.get("refresh_token") or ""
    return {
        "email": data.get("email") or email or "",
        "localId": data.get("localId") or data.get("user_id") or "",
        "idToken": data.get("idToken") or data.get("id_token") or "",
        "refreshToken": refresh,
        "expiresAt": now + max(0, expires_in - 60),
        "savedAt": now,
        "setup_complete": setup_complete,
        "remember_me": False,
    }


def save_session(session: dict) -> None:
    CONFIG_DIR.mkdir(parents=True, exist_ok=True)
    SESSION_PATH.write_text(json.dumps(session, indent=4), encoding="utf-8")


def clear_session() -> None:
    try:
        if SESSION_PATH.exists():
            SESSION_PATH.unlink()
    except Exception:
        pass


def load_session() -> dict | None:
    if not SESSION_PATH.exists():
        return None
    try:
        data = json.loads(SESSION_PATH.read_text(encoding="utf-8"))
        if not isinstance(data, dict):
            clear_session()
            return None
        refresh_token = (data.get("refreshToken") or "").strip()
        if not refresh_token:
            clear_session()
            return None
        if not bool(data.get("remember_me")):
            clear_session()
            return None
        expires_at = float(data.get("expiresAt") or 0)
        if expires_at and expires_at > time.time() + 120:
            return data
        refreshed = refresh_session(refresh_token)
        refreshed["email"] = data.get("email") or refreshed.get("email") or ""
        refreshed["localId"] = data.get("localId") or refreshed.get("localId") or ""
        refreshed["setup_complete"] = bool(data.get("setup_complete"))
        refreshed["remember_me"] = True
        save_session(refreshed)
        return refreshed
    except Exception:
        clear_session()
        return None


def sign_up(email: str, password: str) -> dict:
    key = _api_key()
    if not key:
        raise FirebaseAuthError("Firebase API key is missing.")
    url = f"https://identitytoolkit.googleapis.com/v1/accounts:signUp?key={urllib.parse.quote(key)}"
    data = _post_json(url, {
        "email": email.strip(),
        "password": password,
        "returnSecureToken": True,
    })
    return _normalize_session(data, email=email, setup_complete=False)


def sign_in(email: str, password: str) -> dict:
    key = _api_key()
    if not key:
        raise FirebaseAuthError("Firebase API key is missing.")
    url = f"https://identitytoolkit.googleapis.com/v1/accounts:signInWithPassword?key={urllib.parse.quote(key)}"
    data = _post_json(url, {
        "email": email.strip(),
        "password": password,
        "returnSecureToken": True,
    })
    return _normalize_session(data, email=email, setup_complete=False)


def refresh_session(refresh_token: str) -> dict:
    key = _api_key()
    if not key:
        raise FirebaseAuthError("Firebase API key is missing.")
    url = f"https://securetoken.googleapis.com/v1/token?key={urllib.parse.quote(key)}"
    data = _post_form(url, {
        "grant_type": "refresh_token",
        "refresh_token": refresh_token.strip(),
    })
    # Refresh endpoint uses snake_case response keys.
    normalized = {
        "email": "",
        "localId": data.get("user_id") or "",
        "idToken": data.get("id_token") or "",
        "refreshToken": data.get("refresh_token") or refresh_token.strip(),
        "expiresAt": time.time() + max(0, int(float(data.get("expires_in") or 3600)) - 60),
        "savedAt": time.time(),
        "setup_complete": False,
    }
    return normalized
