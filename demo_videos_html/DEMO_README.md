# How to Run Demo with ROVER API & External LLM or Local SLM

## Prerequisites

1. Install Python dependencies:

```bash
pip install -r requirements.txt
```

2. Ensure you have the following services available:
   - Coordinate Server (this project)
   - Go Backend Server (optional, for drone/rover coordination)
   - Rover HTTP API (optional, for rover control)

---

## 1. Setup Environment (OpenAI Version)

### a. Set up `.env` file with your OpenAI API key

Create a `.env` file in the project root:

```bash
API_OPEN_API_AI=your_openai_api_key
```

### b. Configure `config/configure.json`

The configuration file now includes both LLM settings and service URLs:

```json
{
  "lm_api_url": "https://api.openai.com/v1",
  "provider": "openai",
  "model": "gpt-4o-mini",
  "request_options": {
    "temperature": 0.7,
    "max_tokens": 1024
  },
  "services": {
    "go_server_url": "http://localhost:8080",
    "slm_url": "http://localhost:8000",
    "rover_http_url": "http://localhost:5001/start_route"
  }
}
```

**Configuration Notes:**

- `lm_api_url`: LLM API endpoint (OpenAI, local SLM, etc.)
- `provider`: LLM provider type (`openai`, `local`, `gemini`, etc.)
- `model`: Model name to use
- `services.go_server_url`: Go backend server URL (for drone/rover coordination)
- `services.slm_url`: Coordinate Server URL (default: `http://localhost:8000`)
- `services.rover_http_url`: Rover HTTP endpoint URL

**Environment Variable Override:**
You can override any service URL using environment variables:

- `GO_SERVER_URL` - Overrides `services.go_server_url`
- `SLM_URL` - Overrides `services.slm_url`
- `ROVER_HTTP_URL` - Overrides `services.rover_http_url`

### c. Run the Coordinate Server

**Option 1: Direct execution (Recommended)**

```bash
python app/CoordinateServer.py
```

**Option 2: As a Python module**

```bash
python -m app.CoordinateServer
```

The server will start on `http://0.0.0.0:8000` (accessible at `http://localhost:8000`).

### d. Run the Demo HTML File

**Option 1: Using Python HTTP Server (Recommended)**

Start a simple HTTP server on a different port (e.g., 8080):

```bash
cd demo_videos_html
python -m http.server 8080
```

Then access:

- `http://localhost:8080/index_LIVE.html` - Live demo with voice features
- `http://localhost:8080/index_DEMO.html` - Static demo

**Option 2: Direct file access**

You can directly open the HTML files in your browser, but note:

- CORS restrictions may apply
- Microphone permissions may need to be granted repeatedly
- Some features may not work without a web server

### e. Configure API URL in Browser (for index_LIVE.html)

The `index_LIVE.html` includes a built-in configuration panel:

1. Scroll down to find the **"Configure"** section (below "Test TTS")
2. Click the header to expand it
3. You can either:
   - **Upload `configure.json`**: Click "Choose File" and select your config file
   - **Manually enter API URL**: Type the URL and click "Apply"
4. The configuration is saved to browser localStorage and persists across sessions

**Default API URL**: `http://localhost:8000`

---

## 2. Setup Environment (Local SLM Version)

### a. Configure Local SLM

Update `config/configure.json` for your local SLM:

```json
{
  "lm_api_url": "http://localhost:1234/v1",
  "provider": "local",
  "model": "your-local-model-name",
  "request_options": {
    "temperature": 0.7,
    "max_tokens": 1024
  },
  "services": {
    "go_server_url": "http://localhost:8080",
    "slm_url": "http://localhost:8000",
    "rover_http_url": "http://localhost:5001/start_route"
  }
}
```

### b. Start Local SLM Server

Follow the instructions in the main `README.md` to set up and start your local SLM server.

### c. Run Coordinate Server

Same as step 1.c above:

```bash
python app/CoordinateServer.py
```

---

## Quick Start (TL;DR)

**1. Start Coordinate Server:**

```bash
python app/CoordinateServer.py
```

**2. Start Demo HTML Server (in a new terminal):**

```bash
cd demo_videos_html
python -m http.server 8080
```

**3. Open Browser:**

- Navigate to `http://localhost:8080/index_LIVE.html`
- Configure API URL if needed (default: `http://localhost:8000`)

---

## Troubleshooting

### Port Already in Use

If port 8000 is already in use:

1. Change the port in `CoordinateServer.py` (line 882), or
2. Use environment variable: `SLM_URL=http://localhost:8001`
3. Update the HTML configuration panel accordingly

### CORS Issues

If you encounter CORS errors:

- Make sure you're accessing the HTML through a web server (not `file://`)
- Check that `CoordinateServer.py` has CORS enabled (it should by default)

### Configuration Not Loading

- Verify `config/configure.json` exists and is valid JSON
- Check that environment variables are set correctly (if using `.env`, ensure `load_dotenv()` is called)
- Check browser console for JavaScript errors

---

## File Structure

```
slm-toolkits/
├── app/
│   └── CoordinateServer.py    # Main Flask server
├── config/
│   └── configure.json         # Configuration file
├── demo_videos_html/
│   ├── index_LIVE.html        # Live demo with voice
│   ├── index_DEMO.html        # Static demo
│   └── DEMO_README.md         # This file
├── utils/
│   └── ConfigHelper.py        # Configuration loader
└── requirements.txt           # Python dependencies
```
