```markdown
# Local-LM Proxy

A modular and lightweight FastAPI-based proxy for serving OpenAI-compatible `/v1/chat/completions` requests to a locally hosted or third-party Large Language Model (LLM) backend. Designed to facilitate integration, model switching, and prompt management without altering core logic.

## Overview

This project enables:

- Local testing of small language models (SLMs) via an OpenAI-compatible API
- Seamless switching between local, Grok, or OpenAI endpoints
- Custom system prompts in multiple languages
- Simple, transparent configuration and dependency structure

## Features

- OpenAI-compatible `/v1/chat/completions` proxy
- Centralized configuration via `config/configure.json`
- Multi-language and task-specific prompts via `config/system-prompt.json`
- Clean separation between interface, logic, and configuration
- Lightweight and self-contained (no external databases or queues)

## Project Structure
```

slm-toolkits/
├── app/
│ ├── main.py # FastAPI app with core routing and logic
│ └── settings.py # Configuration loader and cache
├── config/
│ ├── configure.json # LLM provider and parameters
│ └── system-prompt.json # Task-specific and language-based system prompts
├── requirements.txt # Python dependencies
├── .gitignore # Common exclusions
└── README.md # Project documentation

````

## Configuration

### `config/configure.json`

Defines the upstream LLM service and related parameters:

```json
{
  "lm_api_url": "http://localhost:1234/v1/chat/completions",
  "provider": "local",
  "api_key": "",
  "model": "grok-3-mini-beta",
  "request_options": {
    "temperature": 0.7,
    "max_tokens": 1024,
    "stream": false
  }
}
````

### `config/system-prompt.json`

Defines reusable system prompts for different roles or tasks. Example:

```json
{
  "default": "You are a helpful assistant.",
  "zh-TW": "你是一個有幫助且專業的助理。",
  "ja": "あなたは有能で専門的なアシスタントです。",
  "drone-task": "You are a task-oriented assistant in a smart drone-based solar panel maintenance system..."
}
```

## Getting Started

```bash
# Step 1: Create virtual environment
python -m venv .venv
source .venv/bin/activate     # On Windows: .venv\Scripts\activate

# Step 2: Install dependencies
pip install -r requirements.txt

# Step 3: Modify configuration for your target LLM
nano config/configure.json

# Step 4: Launch the API server
uvicorn app.main:app --reload --port 8000
```

## API Usage

### Endpoint

```
POST /v1/chat/completions
```

### Request Format

```json
{
  "messages": [
    { "role": "system", "content": "You are a helpful assistant." },
    { "role": "user", "content": "Hello, who are you?" }
  ],
  "stream": false
}
```

### Response Format

```json
{
  "id": "...",
  "object": "chat.completion",
  "created": 1714413517,
  "choices": [
    {
      "index": 0,
      "message": {
        "role": "assistant",
        "content": "Hello! I'm your assistant."
      },
      "finish_reason": "stop"
    }
  ],
  "usage": {
    "prompt_tokens": 18,
    "completion_tokens": 10,
    "total_tokens": 28
  },
  "proxy_request_id": "abc123-...",
  "latency_ms": 215.7
}
```

## Customization

To use a different system prompt, inject it into the first `system` message or create a dedicated endpoint using the value from `system-prompt.json`.

Example:

```python
from app.settings import get_settings
settings = get_settings()
prompt = settings.prompts["drone-task"]
```

## License

This project is licensed under the MIT License.

```

```
