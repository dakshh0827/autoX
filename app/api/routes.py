from fastapi import APIRouter, HTTPException, Body
from fastapi.responses import HTMLResponse, RedirectResponse
import json
import base64
from typing import Optional

from app.core.logger import get_logger
from app.models.schemas import AgentRequest, AgentResponse
from app.services.agent import TwitterAgent

router = APIRouter()
logger = get_logger(__name__)


@router.get("/", include_in_schema=False)
async def root() -> RedirectResponse:
    return RedirectResponse(url="/api/v1/auth", status_code=302)


@router.get("/auth", response_class=HTMLResponse, summary="Session data UI")
async def auth_ui() -> HTMLResponse:
    return HTMLResponse("""
<!doctype html>
<html lang="en">
<head>
  <meta charset="utf-8"/>
  <meta name="viewport" content="width=device-width, initial-scale=1"/>
  <title>AutoX — Session Data</title>
  <style>
    *, *::before, *::after { box-sizing: border-box; margin: 0; padding: 0; }
    body {
      min-height: 100vh;
      display: flex;
      align-items: center;
      justify-content: center;
      background: #000;
      font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, sans-serif;
      color: #e7e9ea;
      padding: 16px;
    }
    .card {
      background: #16181c;
      border: 1px solid #2f3336;
      border-radius: 16px;
      padding: 40px 36px;
      width: 100%;
      max-width: 520px;
      box-shadow: 0 8px 32px rgba(0,0,0,0.6);
    }
    .logo { display: flex; align-items: center; gap: 10px; margin-bottom: 28px; }
    .logo svg { width: 28px; height: 28px; fill: #e7e9ea; flex-shrink: 0; }
    .logo-text { font-size: 22px; font-weight: 700; letter-spacing: -0.5px; }
    h2 { font-size: 18px; font-weight: 600; margin-bottom: 6px; }
    .subtitle { font-size: 13px; color: #71767b; margin-bottom: 28px; line-height: 1.5; }
    .field { margin-bottom: 16px; }
    label {
      display: block; font-size: 12px; font-weight: 500; color: #71767b;
      margin-bottom: 6px; text-transform: uppercase; letter-spacing: 0.5px;
    }
    input, textarea {
      width: 100%; padding: 12px 14px; background: #000; border: 1px solid #2f3336;
      border-radius: 8px; color: #e7e9ea; font-size: 14px; outline: none;
      transition: border-color 0.2s; font-family: inherit;
    }
    textarea {
      min-height: 220px; resize: vertical; font-family: ui-monospace, SFMono-Regular, Menlo, Monaco, Consolas, monospace;
    }
    input:focus, textarea:focus { border-color: #1d9bf0; }
    input::placeholder, textarea::placeholder { color: #3d4147; }
    .btn {
      width: 100%; padding: 13px; background: #1d9bf0; border: none; border-radius: 9999px;
      color: #fff; font-size: 15px; font-weight: 700; cursor: pointer; margin-top: 8px;
    }
    .btn:hover { background: #1a8cd8; }
    .btn:disabled { opacity: 0.5; cursor: not-allowed; }
    .status {
      margin-top: 20px; padding: 12px 14px; border-radius: 8px; font-size: 14px; line-height: 1.5; display: none;
    }
    .status.info    { background: #1e2a3a; border: 1px solid #1d9bf0; color: #7ec8f7; display: block; }
    .status.error   { background: #2a1a1a; border: 1px solid #f4212e; color: #f4646e; display: block; }
    .status.success { background: #0d2118; border: 1px solid #00ba7c; color: #4dce9d; display: block; }
    .spinner {
      display: inline-block; width: 14px; height: 14px; border: 2px solid rgba(255,255,255,0.3);
      border-top-color: #fff; border-radius: 50%; animation: spin 0.7s linear infinite;
      vertical-align: middle; margin-right: 6px;
    }
    @keyframes spin { to { transform: rotate(360deg); } }
  </style>
</head>
<body>
<div class="card">
  <div class="logo">
    <svg viewBox="0 0 24 24" xmlns="http://www.w3.org/2000/svg">
      <path d="M18.244 2.25h3.308l-7.227 8.26 8.502 11.24H16.17l-4.714-6.231-5.401 6.231H2.746l7.73-8.835L1.254 2.25H8.08l4.259 5.631 5.905-5.631zm-1.161 17.52h1.833L7.084 4.126H5.117z"/>
    </svg>
    <span class="logo-text">AutoX</span>
  </div>

  <h2>Paste session data</h2>
  <p class="subtitle">Paste your base64-encoded Playwright storage state. The backend uses it to start the browser already authenticated.</p>

  <div class="field">
    <label for="topic">Topic</label>
    <input id="topic" type="text" placeholder="e.g. Current situation between China and Taiwan" autocomplete="off"/>
  </div>

  <div class="field">
    <label for="sessionData">Session Data (base64 storage_state)</label>
    <textarea id="sessionData" placeholder="Paste base64 storage_state here"></textarea>
  </div>

  <button class="btn" id="submitBtn" onclick="handleSubmit()">Start</button>
  <div id="status" class="status"></div>
</div>

<script>
  function setStatus(msg, type) {
    const el = document.getElementById('status');
    el.className = 'status ' + type;
    el.innerHTML = msg;
  }

  function setLoading(loading) {
    const btn = document.getElementById('submitBtn');
    btn.disabled = loading;
    btn.innerHTML = loading ? '<span class="spinner"></span> Working…' : 'Start';
  }

  async function handleSubmit() {
    const topic = document.getElementById('topic').value.trim();
    const sessionData = document.getElementById('sessionData').value.trim();

    if (!topic) { setStatus('Please enter a topic.', 'error'); return; }
    if (!sessionData) { setStatus('Please paste your session data.', 'error'); return; }

    setLoading(true);
    setStatus('<span class="spinner"></span> Starting headless run…', 'info');

    try {
      const res = await fetch('/api/v1/run', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ topic, auth_storage_state_b64: sessionData }),
      });
      const data = await res.json();

      if (!res.ok || !data.success) {
        setStatus('❌ ' + (data.detail || data.message || 'Run failed.'), 'error');
        setLoading(false);
        return;
      }

      setStatus('✅ Session accepted. The backend is running headless now.', 'success');
      setLoading(false);
    } catch (err) {
      setStatus('❌ Network error: ' + err.message, 'error');
      setLoading(false);
    }
  }
</script>
</body>
</html>
""")


@router.post(
    "/run",
    response_model=AgentResponse,
    summary="Run the Twitter AI Agent (session-data auth)",
)
async def run_agent(request: AgentRequest) -> AgentResponse:
    logger.info(f"POST /run — topic='{request.topic}'")
    try:
        # If no Playwright storage_state was provided, allow users to send
        # DevTools-extracted data (cookies/localStorage). Convert it to a
        # Playwright storage_state in-flight.
        if not request.auth_storage_state_b64:
            # require at least some devtools data
            if not (request.cookies or request.local_storage or request.session_storage):
                raise HTTPException(
                    status_code=400,
                    detail="Provide auth_storage_state_b64 or DevTools fields (cookies/local_storage).",
                )

            # Convert DevTools data into Playwright storage_state JSON
            try:
                cookies_list = []
                if request.cookies:
                    parts = [c.strip() for c in request.cookies.split(';') if c.strip()]
                    for p in parts:
                        if '=' not in p:
                            continue
                        name, value = p.split('=', 1)
                        cookie = {
                            'name': name,
                            'value': value,
                            'domain': request.origin.replace('https://', '').replace('http://', ''),
                            'path': '/',
                            'httpOnly': False,
                            'secure': request.origin.startswith('https'),
                            'sameSite': 'Lax',
                        }
                        cookies_list.append(cookie)

                def _parse_storage(s):
                    if not s:
                        return []
                    if isinstance(s, str):
                        try:
                            obj = json.loads(s)
                        except Exception:
                            return []
                    else:
                        obj = s
                    items = []
                    if isinstance(obj, dict):
                        for k, v in obj.items():
                            items.append({'name': k, 'value': str(v)})
                    return items

                origin_local = _parse_storage(request.local_storage)
                origin_session = _parse_storage(request.session_storage)

                storage_state = {'cookies': cookies_list, 'origins': []}
                if origin_local or origin_session:
                    storage_state['origins'].append({'origin': request.origin, 'localStorage': origin_local})

                raw = json.dumps(storage_state, ensure_ascii=False)
                b64 = base64.b64encode(raw.encode()).decode()

                # Build a new AgentRequest with the generated storage_state
                req_dict = request.model_dump()
                req_dict['auth_storage_state_b64'] = b64
                request = AgentRequest(**req_dict)
            except Exception as e:
                logger.error(f"Error converting DevTools data: {e}", exc_info=True)
                raise HTTPException(status_code=400, detail="Invalid DevTools data format")

        agent = TwitterAgent()
        result = await agent.run(request)
        if not result.success:
            raise HTTPException(status_code=500, detail=result.message)
        return result
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Unhandled error in /run: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))


@router.post(
    "/devtools-to-storage",
    summary="Convert browser DevTools export to Playwright storage_state (base64)",
)
async def devtools_to_storage(
    cookies: Optional[str] = Body(None, description="Value of document.cookie (e.g. 'a=1; b=2')"),
    local_storage: Optional[str] = Body(None, description="JSON string or object of localStorage contents"),
    session_storage: Optional[str] = Body(None, description="JSON string or object of sessionStorage contents"),
    origin: Optional[str] = Body("https://x.com", description="Origin to attach localStorage to (default https://x.com)"),
) -> dict:
    """Convert devtools-extracted `document.cookie` + local/session storage into a Playwright storage_state JSON and return it base64-encoded.

    NOTE: HttpOnly cookies are not available via `document.cookie` and will be missing. This converter helps non-technical users create a usable partial storage_state.
    """
    try:
        cookies_list = []
        if cookies:
            # parse document.cookie style string
            parts = [c.strip() for c in cookies.split(';') if c.strip()]
            for p in parts:
                if '=' not in p:
                    continue
                name, value = p.split('=', 1)
                cookie = {
                    'name': name,
                    'value': value,
                    'domain': origin.replace('https://', '').replace('http://', ''),
                    'path': '/',
                    'httpOnly': False,
                    'secure': origin.startswith('https'),
                    'sameSite': 'Lax',
                }
                cookies_list.append(cookie)

        def parse_storage(s):
            if not s:
                return []
            if isinstance(s, str):
                try:
                    obj = json.loads(s)
                except Exception:
                    # try to parse as JS object copied from console (fallback)
                    return []
            else:
                obj = s
            items = []
            if isinstance(obj, dict):
                for k, v in obj.items():
                    items.append({'name': k, 'value': str(v)})
            return items

        origin_local = parse_storage(local_storage)
        origin_session = parse_storage(session_storage)

        storage_state = {
            'cookies': cookies_list,
            'origins': []
        }
        if origin_local or origin_session:
            origin_entry = {'origin': origin, 'localStorage': origin_local}
            # Playwright storage_state does not have a sessionStorage field; sessionStorage will be ignored by Playwright.
            storage_state['origins'].append(origin_entry)

        # return base64-encoded JSON
        raw = json.dumps(storage_state, ensure_ascii=False)
        b64 = base64.b64encode(raw.encode()).decode()

        warning = None
        if cookies and not any(c.get('httpOnly', False) for c in cookies_list):
            warning = 'HttpOnly cookies are not captured from the browser console; some sites may require full storage_state from Playwright.'

        return {'storage_state_b64': b64, 'warning': warning}
    except Exception as e:
        logger.error(f"Error converting devtools data: {e}", exc_info=True)
        raise HTTPException(status_code=400, detail=str(e))