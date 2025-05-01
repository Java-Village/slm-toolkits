# Local-LM Proxy

FastAPI service that **proxies** the OpenAI-style `/v1/chat/completions`
endpoint to a configurable Large-Language-Model (LLM).

## Features
* Drop-in OpenAI chat API compatibility  
* Hot-swappable upstream: local, Grok, OpenAI, etc.  
* Configuration via `config/configure.json` (no code change required)  
* System prompts in multiple languages (`config/system-prompt.json`)  
* Lightweight: only `fastapi`, `httpx`, and `pydantic` dependencies  

## Quick Start

```bash
# 1. Create virtual environment
python -m venv .venv
source .venv/bin/activate      # Windows: .venv\Scripts\activate

# 2. Install dependencies
pip install -r requirements.txt

# 3. Edit configure.json to match your upstream LLM
nano config/configure.json

# 4. Run the proxy
uvicorn app.main:app --reload --port 8000
