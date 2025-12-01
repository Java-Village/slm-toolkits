"""
Configuration helper module for loading service URLs from configure.json.
Supports environment variable override for flexibility.
"""
import json
import os
from pathlib import Path
from dotenv import load_dotenv
from typing import Dict, Optional


def load_service_config() -> Dict[str, Optional[str]]:
    """
    Load service URLs from configure.json with environment variable override.
    
    Environment variables take precedence over config file values.
    Falls back to defaults if neither config file nor env vars are set.
    
    Returns:
        Dictionary containing:
        - go_server_url: Go backend server base URL
        - slm_url: SLM server URL (default: http://localhost:8000)
        - rover_http_url: Rover HTTP endpoint URL (default: http://localhost:5001/start_route)
    """
    load_dotenv()
    
    config_path = Path(__file__).parent.parent / "config" / "configure.json"
    services = {}
    
    # Try to load from config file
    if config_path.exists():
        try:
            with open(config_path, "r", encoding="utf-8") as f:
                config = json.load(f)
                services = config.get("services", {})
        except Exception as e:
            print(f"[WARN] Failed to load config file: {e}")
    
    # Return with environment variable override (env vars take precedence)
    return {
        "go_server_url": os.getenv("GO_SERVER_URL", services.get("go_server_url")),
        "slm_url": os.getenv("SLM_URL", services.get("slm_url", "http://localhost:8000")),
        "rover_http_url": os.getenv("ROVER_HTTP_URL", services.get("rover_http_url", "http://localhost:5001/start_route"))
    }

