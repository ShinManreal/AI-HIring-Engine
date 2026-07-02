"""
User settings manager for REPP Talent AI Hiring Engine.

Stores per-user settings in Supabase so settings persist after Render redeploys.

Required Supabase table:
user_settings

SQL:
create table if not exists public.user_settings (
    username text primary key,
    display_name text,
    theme text default 'light',
    timezone text default 'America/New_York',
    character_size text default 'medium',
    password_hash text,
    updated_at timestamptz default now()
);
"""

from datetime import datetime, timezone

from supabase_database import supabase


US_TIMEZONE_OPTIONS = {
    "Eastern Time": "America/New_York",
    "Central Time": "America/Chicago",
    "Mountain Time": "America/Denver",
    "Pacific Time": "America/Los_Angeles",
    "Arizona Time": "America/Phoenix",
    "Alaska Time": "America/Anchorage",
    "Hawaii Time": "Pacific/Honolulu",
}

THEME_OPTIONS = {
    "Light Mode": "light",
    "Dark Mode": "dark",
}

CHARACTER_SIZE_OPTIONS = {
    "Small": "small",
    "Medium": "medium",
    "Large": "large",
    "Extra Large": "extra_large",
}

DEFAULT_USER_SETTINGS = {
    "display_name": "",
    "theme": "light",
    "timezone": "America/New_York",
    "character_size": "medium",
    "password_hash": "",
}


def normalize_theme(value):
    value = str(value or "").strip().lower()
    if value in ["dark", "dark mode"]:
        return "dark"
    return "light"


def normalize_character_size(value):
    value = str(value or "").strip().lower()

    if value in ["small", "medium", "large", "extra_large"]:
        return value

    if value in ["extra large", "xl", "x-large"]:
        return "extra_large"

    return "medium"


def normalize_timezone(value):
    value = str(value or "").strip()

    allowed_values = set(US_TIMEZONE_OPTIONS.values())

    if value in allowed_values:
        return value

    return "America/New_York"


def get_user_settings(username):
    username = str(username or "").strip()

    if not username:
        return dict(DEFAULT_USER_SETTINGS)

    try:
        response = (
            supabase.table("user_settings")
            .select("*")
            .eq("username", username)
            .limit(1)
            .execute()
        )

        rows = response.data or []

        if not rows:
            settings = dict(DEFAULT_USER_SETTINGS)
            settings["username"] = username
            return settings

        row = rows[0]

        return {
            "username": username,
            "display_name": row.get("display_name") or "",
            "theme": normalize_theme(row.get("theme")),
            "timezone": normalize_timezone(row.get("timezone")),
            "character_size": normalize_character_size(row.get("character_size")),
            "password_hash": row.get("password_hash") or "",
        }

    except Exception:
        settings = dict(DEFAULT_USER_SETTINGS)
        settings["username"] = username
        return settings


def save_user_settings(
    username,
    display_name=None,
    theme=None,
    timezone_name=None,
    character_size=None,
    password_hash=None,
):
    username = str(username or "").strip()

    if not username:
        return False, "Missing username."

    current_settings = get_user_settings(username)

    payload = {
        "username": username,
        "display_name": (
            str(display_name).strip()
            if display_name is not None
            else current_settings.get("display_name", "")
        ),
        "theme": normalize_theme(theme if theme is not None else current_settings.get("theme")),
        "timezone": normalize_timezone(
            timezone_name if timezone_name is not None else current_settings.get("timezone")
        ),
        "character_size": normalize_character_size(
            character_size if character_size is not None else current_settings.get("character_size")
        ),
        "password_hash": (
            str(password_hash).strip()
            if password_hash is not None
            else current_settings.get("password_hash", "")
        ),
        "updated_at": datetime.now(timezone.utc).isoformat(),
    }

    try:
        supabase.table("user_settings").upsert(payload, on_conflict="username").execute()
        return True, "Settings saved."

    except Exception as error:
        return False, str(error)


def get_label_from_value(options, value, fallback_label):
    for label, option_value in options.items():
        if option_value == value:
            return label

    return fallback_label
