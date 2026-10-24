"""Runtime configuration. All secrets come from env vars (optionally loaded from backend/.env)."""
import os
from pathlib import Path
from dotenv import load_dotenv

BACKEND_DIR = Path(__file__).resolve().parent.parent
load_dotenv(BACKEND_DIR / ".env", override=False)  # real env vars win over .env


def _int(name, default):
    try:
        return int(os.getenv(name, default))
    except ValueError:
        return default


class Settings:
    def __init__(self):
        self.xai_api_key = os.getenv("XAI_API_KEY", "").strip()
        self.x_bearer_token = os.getenv("X_BEARER_TOKEN", "").strip()
        self.data_source = os.getenv("DATA_SOURCE", "auto").strip().lower()
        self.search_model = os.getenv("GROK_SEARCH_MODEL", "grok-4.7")
        self.label_model = os.getenv("GROK_LABEL_MODEL", "grok-4.20-0309-non-reasoning")
        self.base_url = os.getenv("XAI_BASE_URL", "https://api.x.ai/v1")
        self.search_calls = _int("XAI_SEARCH_CALLS", 3)
        self.lookback_days = _int("LOOKBACK_DAYS", 30)
        self.max_posts = _int("MAX_POSTS", 200)
        self.label_batch = _int("LABEL_BATCH", 20)
        self.cache_dir = Path(os.getenv("CACHE_DIR", BACKEND_DIR / "data" / "cache"))

    @property
    def resolved_source(self):
        if self.data_source in ("xai_x_search", "x_api_v2"):
            return self.data_source
        if self.xai_api_key:
            return "xai_x_search"
        if self.x_bearer_token:
            return "x_api_v2"
        return None

    @property
    def live_enabled(self):
        src = self.resolved_source
        if not self.xai_api_key:  # Grok is always needed for labeling
            return False
        if src == "x_api_v2" and not self.x_bearer_token:
            return False
        return src is not None


def get_settings():
    return Settings()
