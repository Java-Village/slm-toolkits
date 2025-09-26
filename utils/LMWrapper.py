

# This file is for the LMStudioWrapper to interact with the user and the database.
# The bot will use the LMStudio, OpenAI-like api and Gemini (TODO: Gemini 2.0)

from re import I
import openai
import requests
import json
import time
import random

from typing import Protocol, List, Dict, Optional
from types import SimpleNamespace


def gemini_to_openai_like(response_json) -> SimpleNamespace:
    try:
        # 更詳細的錯誤處理和調試信息
        if not isinstance(response_json, dict):
            raise RuntimeError(
                f"Expected dict, got {type(response_json)}: {response_json}")

        # 檢查是否有錯誤信息
        if "error" in response_json:
            error_msg = response_json["error"].get(
                "message", "Unknown Gemini API error")
            raise RuntimeError(f"Gemini API error: {error_msg}")

        if "candidates" not in response_json:
            # 檢查是否有 promptFeedback 指示被阻止
            if "promptFeedback" in response_json:
                feedback = response_json["promptFeedback"]
                if "blockReason" in feedback:
                    block_reason = feedback["blockReason"]
                    raise RuntimeError(
                        f"Content blocked by Gemini: {block_reason}")

            # 如果只有使用統計信息，表示生成失敗但沒有具體錯誤
            if "usageMetadata" in response_json and len(response_json) <= 3:
                raise RuntimeError(
                    "Gemini generated no content - likely content policy block or generation failure")

            raise RuntimeError(f"No 'candidates' in response: {response_json}")

        candidates = response_json["candidates"]
        if not candidates:
            raise RuntimeError(f"Empty 'candidates' array: {response_json}")

        candidate = candidates[0]

        # 檢查是否被安全過濾器阻止
        if "finishReason" in candidate and candidate["finishReason"] in ["SAFETY", "PROHIBITED_CONTENT"]:
            finish_reason = candidate["finishReason"]
            raise RuntimeError(
                f"Content blocked by safety filter: {finish_reason}")

        if "content" not in candidate:
            raise RuntimeError(f"No 'content' in candidate: {candidate}")

        content = candidate["content"]
        parts = content.get("parts", [])

        if not parts:
            raise RuntimeError(f"No 'parts' in content: {content}")

        text = ""
        for part in parts:
            if "text" in part:
                text += part["text"]

        if not text.strip():
            raise RuntimeError(f"No text content found in parts: {parts}")

        return SimpleNamespace(
            choices=[SimpleNamespace(
                message=SimpleNamespace(
                    role="assistant",
                    content=text.strip()
                )
            )]
        )
    except Exception as e:
        print(f"[DEBUG] Gemini response: {response_json}")
        raise RuntimeError(f"Invalid Gemini response: {e}")


class IChatBackend(Protocol):
    def chat(self, messages: List[Dict], parameters: Optional[Dict] = None, stream: bool = False) -> Dict:
        pass


# use lm studio api to interact with the user and the database.

class LMWrapper:
    def __init__(self, backend: IChatBackend):
        self.backend = backend

    def chat(self, messages: List[Dict], parameters: Dict = None, stream: bool = False) -> Dict:
        return self.backend.chat(messages, parameters, stream)


class OpenAIWrapper:
    def __init__(self, api_key: str, base_url: str = "https://api.openai.com/v1", model: str = "gpt-4.1"):
        self.client = openai.OpenAI(api_key=api_key, base_url=base_url)
        self.model = model

    def chat(self, messages, parameters=None, stream=False):
        parameters = parameters or {}
        return self.client.chat.completions.create(
            model=self.model,
            messages=messages,
            temperature=parameters.get("temperature", 0.5),
            stream=stream,
        )


class GeminiWrapper:
    def __init__(self, api_key: str, model: str = "gemini-1.5-flash", max_retries: int = 3):
        self.api_key = api_key
        self.model = model
        self.max_retries = max_retries

    def chat(self, messages, parameters=None, stream=False):
        parameters = parameters or {}

        # TODO: Streaming the response
        if stream:
            raise NotImplementedError(
                "Streaming not yet supported for GeminiWrapper")

        system_prompt = "\n\n".join(m["content"]
                                    for m in messages if m["role"] == "system")
        contents = []
        system_added = False

        for m in messages:
            if m["role"] == "user":
                content = m["content"]
                if system_prompt and not system_added:
                    content = f"{system_prompt}\n\n{content}"
                    system_added = True
                contents.append({"role": "user", "parts": [
                                {"text": "\n\nContent: " + content}]})
            elif m["role"] == "assistant":
                contents.append(
                    {"role": "model", "parts": [{"text": m["content"]}]})
            # system message has already been processed

        # Generate the payload
        payload = {
            "contents": contents,
            "generationConfig": {
                "temperature": parameters.get("temperature", 0.8),
                "topP": parameters.get("top_p", 0.8),
                "topK": parameters.get("top_k", 40),
                "maxOutputTokens": parameters.get("max_tokens", 100240),
            }
        }
        headers = {"Content-Type": "application/json",
                   "X-goog-api-key": self.api_key}
        url = f"https://generativelanguage.googleapis.com/v1beta/models/{self.model}:generateContent"

        # 實施重試機制處理頻率限制
        for attempt in range(self.max_retries):
            try:
                resp = requests.post(url, headers=headers,
                                     data=json.dumps(payload))
                resp.raise_for_status()
                data = resp.json()

                print(f"[DEBUG] Gemini raw response: {data}")
                break  # 成功，退出重試迴圈

            except requests.exceptions.HTTPError as e:
                if e.response.status_code == 429:  # Too Many Requests
                    if attempt < self.max_retries - 1:
                        # 指數退避策略：基礎延遲 + 隨機抖動
                        base_delay = 2 ** attempt  # 1, 2, 4 秒
                        jitter = random.uniform(0.5, 1.5)  # 隨機抖動
                        delay = base_delay * jitter

                        print(
                            f"[WARNING] Gemini API rate limit hit. Retrying in {delay:.2f}s (attempt {attempt + 1}/{self.max_retries})")
                        time.sleep(delay)
                        continue
                    else:
                        print(
                            f"[ERROR] Gemini API rate limit exceeded. Max retries ({self.max_retries}) reached.")
                        return {"choices": [], "error": "Rate limit exceeded after maximum retries"}
                else:
                    # 其他 HTTP 錯誤，不重試
                    print(f"[ERROR] Gemini API HTTP error: {e}")
                    if hasattr(e, 'response') and e.response:
                        print(f"[ERROR] Response text: {e.response.text}")
                    return {"choices": [], "error": str(e)}

            except Exception as e:
                print(f"[ERROR] Gemini API call failed: {e}")
                if hasattr(e, 'response') and e.response:
                    print(f"[ERROR] Response text: {e.response.text}")
                return {"choices": [], "error": str(e)}

        text = data.get("candidates", [{}])[0].get(
            "content", {}).get("parts", [{}])[0].get("text", "")

        # 檢查是否有錯誤
        if "error" in data:
            error_msg = data["error"].get("message", "Unknown error")
            print(f"[ERROR] Gemini API error: {error_msg}")
            return {"choices": [], "error": error_msg}

        # 檢查是否被阻止
        if "candidates" in data and data["candidates"]:
            candidate = data["candidates"][0]
            if "finishReason" in candidate and candidate["finishReason"] in ["SAFETY", "RECITATION", "OTHER"]:
                finish_reason = candidate["finishReason"]
                print(f"[WARNING] Gemini response blocked: {finish_reason}")
                return {"choices": [], "error": f"Response blocked due to: {finish_reason}"}

        # Convert the response to the format
        fmt = parameters.get("format", "openai")

        try:
            if fmt == "openai":
                return gemini_to_openai_like(data)
            elif fmt == "gemini":
                return data
            else:
                raise ValueError(
                    f"Invalid format: {parameters.get('format', 'openai')}")
        except Exception as e:
            print(f"[ERROR] Failed to convert Gemini response: {e}")
            return {"choices": [], "error": str(e)}


