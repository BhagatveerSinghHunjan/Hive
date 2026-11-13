"""HIVE configuration — paths, settings, env vars."""

import os
from pathlib import Path
from dotenv import load_dotenv

load_dotenv()

# Paths
HIVE_HOME = Path(
    os.environ.get("HIVE_HOME", Path.home() / ".hive")
).expanduser()
HIVE_DB = HIVE_HOME / "hive.db"
AGENTS_DIR = HIVE_HOME / "agents" / "generated"
SKILLS_DIR = HIVE_HOME / "skills"

# LLM — any OpenAI-compatible endpoint (DashScope, OpenRouter, Gemini, Groq,
# OpenCode Zen, Ollama). HIVE_LLM_* wins; the QWEN_* names remain as defaults
# so existing installs keep working unchanged.
DASHSCOPE_API_KEY = os.environ.get("DASHSCOPE_API_KEY", "")
QWEN_MODEL = os.environ.get("QWEN_MODEL", "qwen3.7-plus")
QWEN_BASE_URL = "https://dashscope-intl.aliyuncs.com/compatible-mode/v1"

LLM_BASE_URL = os.environ.get("HIVE_LLM_BASE_URL", "").strip() or QWEN_BASE_URL
LLM_API_KEY = os.environ.get("HIVE_LLM_API_KEY", "").strip() or DASHSCOPE_API_KEY
LLM_MODEL = os.environ.get("HIVE_LLM_MODEL", "").strip() or QWEN_MODEL

# Browser automation
BROWSER_SCREENSHOT_DIR = Path(
    os.environ.get("HIVE_SCREENSHOT_DIR", str(HIVE_HOME / "screenshots"))
)
CHROME_AUTOMATION_PROFILE = Path(
    os.environ.get("HIVE_CHROME_PROFILE", str(HIVE_HOME / "chrome-automation"))
)

# Reuse the user's REAL Chrome login state (cookies/sessions). When enabled,
# HIVE snapshots the real Chrome profile (read-only copy — your original is
# never touched) so the automated browser inherits sites you're already
# logged into (Spotify, Google, etc.) and can skip the login form entirely.
HIVE_CHROME_PROFILE_REUSE = os.environ.get(
    "HIVE_CHROME_PROFILE_REUSE", "false"
).lower() in ("1", "true", "yes")
# Which Chrome profile to copy from (display/dir name, e.g. "Default", "Profile 1")
HIVE_CHROME_SOURCE_PROFILE = os.environ.get("HIVE_CHROME_SOURCE_PROFILE", "Default")
# Optional explicit path to Chrome's "User Data" dir (auto-detected if empty)
HIVE_CHROME_USER_DATA_DIR = os.environ.get("HIVE_CHROME_USER_DATA_DIR", "")

# Which browser binary Playwright drives:
#   "chromium" (default) — Playwright's bundled Chromium
#   "chrome"             — your REAL installed Google Chrome (better fingerprint,
#                          higher chance of passing login/bot challenges on hard
#                          sites like Spotify). Requires Chrome to be installed.
HIVE_BROWSER_CHANNEL = os.environ.get("HIVE_BROWSER_CHANNEL", "chromium").strip().lower()

# Checkout / payments guardrails
HIVE_CHECKOUT_AUTONOMOUS = os.environ.get("HIVE_CHECKOUT_AUTONOMOUS", "false").lower() in ("1", "true", "yes")
HIVE_MAX_ORDER_AMOUNT = float(os.environ.get("HIVE_MAX_ORDER_AMOUNT", "500"))
HIVE_MAX_DAILY_SPEND = float(os.environ.get("HIVE_MAX_DAILY_SPEND", "1000"))
HIVE_CHECKOUT_ALLOWED_MERCHANTS = [
    m.strip().lower()
    for m in os.environ.get("HIVE_CHECKOUT_ALLOWED_MERCHANTS", "").split(",")
    if m.strip()
]

# Exa — Web Search
EXA_API_KEY = os.environ.get("EXA_API_KEY", "")

# Runtime
MAX_AGENTS = int(os.environ.get("HIVE_MAX_AGENTS", "4"))
MAX_MESSAGES = int(os.environ.get("HIVE_MAX_MESSAGES", "50"))
MAX_TOOL_CACHE = int(os.environ.get("HIVE_MAX_TOOL_CACHE", "20"))
AGENT_TIMEOUT = int(os.environ.get("HIVE_AGENT_TIMEOUT", "60"))
MAX_TOKENS = int(os.environ.get("HIVE_MAX_TOKENS", "4000"))
MAX_ITERATIONS = int(os.environ.get("HIVE_MAX_ITERATIONS", "20"))
HIVE_AGENT_PROFILE = os.environ.get("HIVE_AGENT_PROFILE", "full").strip().lower()
HIVE_TIMEZONE = os.environ.get("HIVE_TIMEZONE", "Asia/Kolkata")

# Integrations — Google (Gmail + Calendar)
GOOGLE_CLIENT_ID = os.environ.get("GOOGLE_CLIENT_ID", "").strip()
GOOGLE_CLIENT_SECRET = os.environ.get("GOOGLE_CLIENT_SECRET", "").strip()
GOOGLE_OAUTH_CLIENT_FILE = os.environ.get("GOOGLE_OAUTH_CLIENT_FILE", "").strip()
_google_token_env = os.environ.get("GOOGLE_TOKEN_FILE", "").strip()
GOOGLE_TOKEN_FILE = (
    Path(_google_token_env).expanduser()
    if _google_token_env
    else HIVE_HOME / "google_token.json"
)
# Use the canonical userinfo URLs rather than the "email"/"profile" aliases.
# Google expands the aliases in its token response, and oauthlib treats that
# expansion as a scope change and refuses the token.
GOOGLE_OAUTH_SCOPES = [
    "openid",
    "https://www.googleapis.com/auth/userinfo.email",
    "https://www.googleapis.com/auth/userinfo.profile",
    "https://www.googleapis.com/auth/gmail.modify",
    "https://www.googleapis.com/auth/gmail.send",
    "https://www.googleapis.com/auth/calendar",
    "https://www.googleapis.com/auth/tasks",
]

# Google Calendar defaults
GOOGLE_CALENDAR_ID = os.environ.get("GOOGLE_CALENDAR_ID", "primary").strip() or "primary"

# Google Tasks sync (local task store remains the source of truth)
HIVE_GOOGLE_TASKS_SYNC = os.environ.get(
    "HIVE_GOOGLE_TASKS_SYNC", "false"
).lower() in ("1", "true", "yes")
GOOGLE_TASKS_LIST_ID = os.environ.get("GOOGLE_TASKS_LIST_ID", "@default").strip() or "@default"
HIVE_TASKS_FILE = Path(
    os.environ.get("HIVE_TASKS_FILE", str(HIVE_HOME / "tasks.json"))
).expanduser()

# Integrations — Slack (status only for now)
SLACK_BOT_TOKEN = os.environ.get("SLACK_BOT_TOKEN", "").strip()
SLACK_DEFAULT_CHANNEL = os.environ.get("SLACK_DEFAULT_CHANNEL", "").strip()

# Personas (digital twins)
HIVE_PERSONA = os.environ.get("HIVE_PERSONA", "").strip()
HIVE_PERSONA_FILE = HIVE_HOME / "personas.json"

# Trust ladder (browser autonomy per domain; outbound actions always ask)
HIVE_TRUST_DEFAULT_LEVEL = int(os.environ.get("HIVE_TRUST_DEFAULT_LEVEL", "0"))

# CAPTCHA solving (human handoff by default; optional external provider)
HIVE_CAPTCHA_PROVIDER = os.environ.get("HIVE_CAPTCHA_PROVIDER", "human").strip().lower()
HIVE_CAPTCHA_API_KEY = os.environ.get("HIVE_CAPTCHA_API_KEY", "").strip()
HIVE_CAPTCHA_TIMEOUT = int(os.environ.get("HIVE_CAPTCHA_TIMEOUT", "180"))

# Security
ALLOWED_DOMAINS = [
    "api.dashscope.aliyuncs.com",
    "dashscope-intl.aliyuncs.com",
    "registry.npmjs.org",
    "pypi.org",
    "api.github.com",
    "raw.githubusercontent.com",
    "httpbin.org",
    "localhost",
    "127.0.0.1",
    # Google integrations
    "accounts.google.com",
    "oauth2.googleapis.com",
    "gmail.googleapis.com",
    "www.googleapis.com",
    # Slack integration
    "slack.com",
    "app.slack.com",
    "api.slack.com",
]

DENIED_PATTERNS = [
    r"rm\s+-rf",
    r"curl.*\|\s*bash",
    r"wget.*\|\s*bash",
    r"eval\s*\(",
    r"exec\s*\(",
    r">\s*/dev/sd",
    r"chmod\s+777",
    r"sudo\s+.*",
]

BLOCKED_ENV_VARS = [
    "DASHSCOPE_API_KEY",
    "HIVE_LLM_API_KEY",
    "ANTHROPIC_API_KEY",
    "OPENAI_API_KEY",
    "OPENROUTER_API_KEY",
    "GEMINI_API_KEY",
    "GOOGLE_API_KEY",
    "GROQ_API_KEY",
    "AWS_SECRET_ACCESS_KEY",
    "GITHUB_TOKEN",
    "SLACK_BOT_TOKEN",
]

CREDENTIAL_PATTERNS = [
    "*.env", "*.key", "*.pem", "*.p12", "*.pfx",
    "*credentials*", "*secret*", "*token*", "*oauth*client*",
]

DENIED_PATHS = [
    "~/.ssh", "~/.aws", "~/.gnupg",
    "/etc", "/usr", "/bin", "/sbin", "/proc", "/sys",
]

THEME_BANNER = os.environ.get("HIVE_COLOR_BANNER", "gold1")
THEME_ACCENT = os.environ.get("HIVE_COLOR_ACCENT", "cyan")


def ensure_dirs():
    """Create HIVE directories if they don't exist."""
    HIVE_HOME.mkdir(parents=True, exist_ok=True)
    AGENTS_DIR.mkdir(parents=True, exist_ok=True)
    SKILLS_DIR.mkdir(parents=True, exist_ok=True)
    BROWSER_SCREENSHOT_DIR.mkdir(parents=True, exist_ok=True)
    CHROME_AUTOMATION_PROFILE.mkdir(parents=True, exist_ok=True)


def get_sanitized_context():
    """Context safe to send to LLM (no secrets)."""
    return {
        "project_dir": os.getcwd(),
        "platform": os.name,
    }
