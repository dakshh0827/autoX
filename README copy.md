# 🐦 Twitter AI Agent

An AI-powered Twitter automation agent that:
1. Generates a multi-tweet thread on any topic using **Groq (LLaMA 3.3 70B)**
2. Opens a real browser with **Playwright** and waits for your login
3. Posts the full thread
4. Interacts (like + reply) with **10 feed posts**
5. Follows **5 accounts** relevant to the topic

All triggered via a single FastAPI endpoint.

---

## 📁 Folder Structure

```
twitter_agent/
├── main.py                        # FastAPI entry point
├── requirements.txt
├── .env.example                   # Copy to .env and fill in
├── .gitignore
│
└── app/
    ├── __init__.py
    │
    ├── api/
    │   ├── __init__.py
    │   └── routes.py              # POST /api/v1/run
    │
    ├── core/
    │   ├── __init__.py
    │   ├── config.py              # All settings via .env
    │   └── logger.py              # File + console logging
    │
    ├── models/
    │   ├── __init__.py
    │   └── schemas.py             # Pydantic request/response models
    │
    └── services/
        ├── __init__.py
        ├── groq_service.py        # Groq API: thread, replies, scoring
        ├── twitter_browser.py     # Playwright browser controller
        └── agent.py               # Orchestrator tying everything together
```

---

## ⚙️ Setup

### 1. Clone & create a virtual environment

```bash
git clone <your-repo>
cd twitter_agent
python -m venv .venv
source .venv/bin/activate        # Windows: .venv\Scripts\activate
```

### 2. Install dependencies

```bash
pip install -r requirements.txt
```

### 3. Install Playwright browsers

```bash
playwright install chromium
```

> This downloads the Chromium binary Playwright uses. Only needs to be run once.

### 4. Configure environment

```bash
cp .env.example .env
```

Open `.env` and fill in:

```env
GROQ_API_KEY=gsk_your_key_here
BROWSER_HEADLESS=false          # Must be false for interactive login
```

Get your Groq API key at: https://console.groq.com/keys

### 5. Start the server

```bash
python main.py
```

Or with uvicorn directly:

```bash
uvicorn main:app --host 0.0.0.0 --port 8000 --reload
```

---

## 🚀 API Usage

### Endpoint

```
POST /api/v1/run
Content-Type: application/json
```

### Request Body

```json
{
  "topic": "The future of AI in healthcare"
}
```

Only one field. That's it.

### Example — curl

```bash
curl -X POST http://localhost:8000/api/v1/run \
  -H "Content-Type: application/json" \
  -d '{"topic": "The future of AI in healthcare"}'
```

### Example — Python

```python
import requests

response = requests.post(
    "http://localhost:8000/api/v1/run",
    json={"topic": "The future of AI in healthcare"},
    timeout=600   # Give it up to 10 minutes
)
print(response.json())
```

### Response

```json
{
  "success": true,
  "topic": "The future of AI in healthcare",
  "thread": {
    "tweets": [
      "AI isn't just changing healthcare — it's rewriting the rules entirely. Here's what the next 5 years look like 🧵",
      "Diagnostic AI now catches cancers radiologists miss. Stanford's model outperforms specialists on skin cancer detection...",
      "..."
    ],
    "tweet_count": 6,
    "posted": true
  },
  "interactions": [
    {
      "tweet_url": "https://x.com/user/status/...",
      "tweet_preview": "AI is transforming drug discovery...",
      "liked": true,
      "replied": true,
      "reply_text": "The protein folding breakthrough is the real unlock here — what's your take on timeline to clinical use?"
    }
  ],
  "follows": [
    {
      "handle": "@example_handle",
      "bio": "AI researcher | Healthcare innovation | ...",
      "relevance_score": 0.92,
      "followed": true
    }
  ],
  "interactions_count": 10,
  "follows_count": 5,
  "elapsed_seconds": 342.5,
  "message": "Successfully posted 6-tweet thread, interacted with 10 posts, followed 5 accounts."
}
```

---

## 🔄 What Happens During a Run

```
POST /api/v1/run  ──► Groq generates thread + search queries
                       │
                       ▼
                  Browser opens (Chromium)
                       │
                       ▼
                  Twitter login page shown
                  [USER LOGS IN MANUALLY — up to 3 min]
                       │
                       ▼
                  Thread posted (tweet by tweet)
                       │
                       ▼
                  Home feed: like + AI reply × 10 posts
                       │
                       ▼
                  Search for topic accounts, score via Groq
                  Follow top 5 relevant accounts
                       │
                       ▼
                  Browser closes
                       │
                       ▼
                  JSON response returned
```

---

## ⚠️ Important Notes

### Login
- The browser opens a **real Chromium window** for you to log in.
- You have **3 minutes** to complete login (including 2FA if enabled).
- The agent waits until it detects the home feed before proceeding.

### Rate Limits & Detection
- Human-like delays (2–5 seconds) are injected between every action.
- Slow typing (40–130ms per character) mimics real users.
- The webdriver flag is masked.
- Do **not** spam this — Twitter/X will detect automated behaviour if you run it repeatedly in quick succession.

### Headless Mode (Servers)
To run without a visible browser (e.g. on a VPS), you need to handle authentication differently:

1. Run once locally with `BROWSER_HEADLESS=false` and log in.
2. Save auth state: add `await context.storage_state(path="auth_state.json")` after login in `twitter_browser.py`.
3. Load that state on subsequent runs: `context = await browser.new_context(storage_state="auth_state.json")`.
4. Set `BROWSER_HEADLESS=true` in `.env`.

---

## 🔧 Configuration Reference

| Variable | Default | Description |
|---|---|---|
| `GROQ_API_KEY` | — | **Required.** Your Groq API key |
| `GROQ_MODEL` | `llama-3.3-70b-versatile` | Groq model to use |
| `HOST` | `0.0.0.0` | Server bind host |
| `PORT` | `8000` | Server port |
| `BROWSER_HEADLESS` | `false` | Run browser without UI |
| `BROWSER_SLOW_MO` | `800` | ms delay between Playwright actions |
| `THREAD_MIN_TWEETS` | `5` | Minimum tweets in thread |
| `THREAD_MAX_TWEETS` | `8` | Maximum tweets in thread |
| `INTERACTIONS_TARGET` | `10` | Feed posts to interact with |
| `FOLLOWS_TARGET` | `5` | Accounts to follow |
| `ACTION_DELAY_MIN` | `2.0` | Min seconds between major actions |
| `ACTION_DELAY_MAX` | `5.0` | Max seconds between major actions |

---

## 🩺 Health Check

```bash
curl http://localhost:8000/health
# {"status": "healthy", "service": "Twitter AI Agent"}
```

## 📖 Interactive Docs

Visit `http://localhost:8000/docs` for the Swagger UI after starting the server.

---

## 🐛 Troubleshooting

| Problem | Fix |
|---|---|
| `TimeoutError: User did not complete login` | Increase timeout in `navigate_to_login()` or log in faster |
| `Tweet textarea not found` | Twitter changed DOM — update selectors in `SEL` dict in `twitter_browser.py` |
| Browser closes immediately | Check your `.env` — `GROQ_API_KEY` must be set |
| `groq.AuthenticationError` | Invalid API key — check https://console.groq.com/keys |
| Replies not posting | Twitter rate-limited you — increase `ACTION_DELAY_MIN` to 5+ |

---

## 📜 Logs

All logs are written to `logs/agent.log` and printed to stdout.

```bash
tail -f logs/agent.log
```
