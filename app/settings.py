"""
settings.py
-----------
Load and cache project-wide configuration.  
No external dependencies beyond the Python standard library.
"""

from functools import lru_cache
from pathlib import Path
import json

BASE_DIR = Path(__file__).resolve().parent.parent
CONFIG_PATH = BASE_DIR / "config" / "configure.json"
PROMPT_PATH = BASE_DIR / "config" / "system-prompt.json"


class Settings:
    """
    Load parameters once and expose them as attributes.
    Using a lightweight class avoids the runtime cost of Pydantic.
    """
    def __init__(self) -> None:
        with CONFIG_PATH.open("r", encoding="utf-8") as f:
            cfg: dict = json.load(f)

        with PROMPT_PATH.open("r", encoding="utf-8") as f:
            self.prompts: dict = json.load(f)

        # Upstream LLM endpoint and provider
        self.lm_api_url: str = cfg["lm_api_url"]
        self.provider: str = cfg["provider"]

        # Credentials and model
        self.api_key: str = cfg.get("api_key", "")
        self.model: str = cfg.get("model", "")

        # Default request options forwarded to the upstream API
        self.request_opts: dict = cfg.get("request_options", {})


@lru_cache
def get_settings() -> Settings:
    """
    Return a singleton Settings instance.  
    The lru_cache decorator guarantees only one object is created.
    """
    return Settings()
