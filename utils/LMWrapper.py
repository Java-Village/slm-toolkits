import openai
import requests
import json
import time
import random
from pathlib import Path
from typing import Protocol, List, Dict, Optional
from types import SimpleNamespace


# --- Gemini to OpenAI Conversion (remains the same) ---
def gemini_to_openai_like(response_json) -> SimpleNamespace:
    # This function is kept as is from the original file.
    try:
        if "candidates" not in response_json:
            # Handle cases where there are no candidates, possibly due to safety filters
            if "promptFeedback" in response_json and "blockReason" in response_json["promptFeedback"]:
                raise RuntimeError(f"Content blocked by Gemini: {response_json['promptFeedback']['blockReason']}")
            raise RuntimeError(f"No 'candidates' in Gemini response: {response_json}")

        content = response_json["candidates"][0]["content"]
        text_parts = [part.get("text", "") for part in content.get("parts", [])]
        full_text = "".join(text_parts).strip()

        return SimpleNamespace(
            choices=[SimpleNamespace(
                message=SimpleNamespace(
                    role="assistant",
                    content=full_text
                )
            )]
        )
    except (KeyError, IndexError, TypeError) as e:
        print(f"[DEBUG] Error parsing Gemini response: {response_json}")
        raise RuntimeError(f"Invalid Gemini response structure: {e}")

        # --- Backend Protocol (remains the same) ---
class IChatBackend(Protocol):
    def chat(self, messages: List[Dict], system_prompt: Optional[str] = None) -> str:
        """
        The chat method that all backend wrappers must implement.
        It should return the string content of the response.
        """
        pass

# --- OpenAI Wrapper (Slightly modified to return string) ---
class OpenAIWrapper:
    def __init__(self, api_key: str, base_url: str, model: str, request_options: Dict):
        self.client = openai.OpenAI(api_key=api_key, base_url=base_url)
        self.model = model
        self.request_options = request_options

    def chat(self, messages: List[Dict], system_prompt: Optional[str] = None) -> str:
        if system_prompt:
            messages = [{"role": "system", "content": system_prompt}] + messages
        
        try:
            completion = self.client.chat.completions.create(
                model=self.model,
                messages=messages,
                **self.request_options
            )
            if completion.choices and completion.choices[0].message:
                return completion.choices[0].message.content or ""
            return ""
        except Exception as e:
            print(f"[ERROR] OpenAI API call failed: {e}")
            return f"Error: Model call failed. Details: {e}"


# --- Gemini Wrapper (Slightly modified to align with protocol) ---
class GeminiWrapper:
    def __init__(self, api_key: str, model: str, request_options: Dict, max_retries: int = 3):
        self.api_key = api_key
        self.model = model
        self.request_options = request_options
        self.max_retries = max_retries

    def chat(self, messages: List[Dict], system_prompt: Optional[str] = None) -> str:
        # Gemini API has a specific format for system instructions.
        system_instruction = system_prompt or ""
        
        # Filter out any system messages from the main list as it's handled separately
        contents = []
        for m in messages:
            if m["role"] == "user":
                contents.append({"role": "user", "parts": [{"text": m["content"]}]})
            elif m["role"] == "assistant":
                 contents.append({"role": "model", "parts": [{"text": m["content"]}]})

        payload = {
            "contents": contents,
            "systemInstruction": {"parts": [{"text": system_instruction}]},
            "generationConfig": {
                "temperature": self.request_options.get("temperature", 0.7),
                "maxOutputTokens": self.request_options.get("max_tokens", 8192),
            }
        }
        
        headers = {"Content-Type": "application/json"}
        url = f"https://generativelanguage.googleapis.com/v1beta/models/{self.model}:generateContent?key={self.api_key}"
        
        # Using a simple requests call for now, retry logic can be added back if needed.
        try:
            resp = requests.post(url, headers=headers, data=json.dumps(payload))
            resp.raise_for_status()
            data = resp.json()
            
            # Use the conversion function to get an OpenAI-like object, then extract text
            openai_like_response = gemini_to_openai_like(data)
            return openai_like_response.choices[0].message.content

        except Exception as e:
            print(f"[ERROR] Gemini API call failed: {e}")
            return f"Error: Model call failed. Details: {e}"



# --- Main LMWrapper (Refactored) ---
class LMWrapper:
    def __init__(self):
        self.backend: Optional[IChatBackend] = None
        self.system_prompt: Optional[str] = None
        self._load_config()

    def _load_config(self):
        try:
            config_path = Path(__file__).parent.parent / "config" / "configure.json"
            if not config_path.exists():
                raise FileNotFoundError(f"Config file not found at {config_path}")
            
            with open(config_path, "r", encoding="utf-8") as f:
                config = json.load(f)

            provider = config.get("provider", "local").lower()
            api_key = config.get("api_key", "")
            model = config["model"]
            request_options = config.get("request_options", {})

            if provider in ["local", "openai", "grok"]:
                self.backend = OpenAIWrapper(
                    api_key=api_key,
                    base_url=config["lm_api_url"],
                    model=model,
                    request_options=request_options
                )
            elif provider == "gemini":
                self.backend = GeminiWrapper(
                    api_key=api_key,
                    model=model,
                    request_options=request_options
                )
            else:
                raise ValueError(f"Unsupported LLM provider: {provider}")

            print(f"--- LMWrapper initialized with '{provider}' provider ---")

        except Exception as e:
            print(f"[ERROR] Failed to initialize LMWrapper: {e}")
            raise e

    def set_system_prompt(self, system_prompt: str):
        self.system_prompt = system_prompt
        print("--- System prompt has been set in LMWrapper ---")

    def get_completion(self, messages: List[Dict]) -> str:
        if not self.backend:
            return "Error: LMWrapper backend is not initialized."
        if not self.system_prompt:
            print("[WARNING] System prompt has not been set. Continuing without it.")

        # The backend's `chat` method is responsible for handling the system prompt
        return self.backend.chat(messages, system_prompt=self.system_prompt)
