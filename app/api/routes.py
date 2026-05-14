import asyncio

from fastapi import APIRouter, HTTPException, BackgroundTasks
from fastapi.responses import HTMLResponse, RedirectResponse

from app.models.schemas import (
    AgentRequest,
    AgentResponse,
    AuthRunRequest,
    AuthRunResponse,
    JobStatusResponse,
)
from app.services.agent import TwitterAgent
from app.core.logger import get_logger
from app.services.auth_service import AuthService
from app.services.job_manager import job_manager

router = APIRouter()
logger = get_logger(__name__)


@router.get("/", include_in_schema=False)
async def root() -> RedirectResponse:
    return RedirectResponse(url="/api/v1/auth", status_code=302)


@router.get("/auth", response_class=HTMLResponse, summary="Login UI")
async def auth_ui() -> HTMLResponse:
    return HTMLResponse("""
<!doctype html>
<html lang="en">
<head>
  <meta charset="utf-8"/>
  <meta name="viewport" content="width=device-width, initial-scale=1"/>
  <title>AutoX — Login</title>
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
      max-width: 400px;
      box-shadow: 0 8px 32px rgba(0,0,0,0.6);
    }

    .logo {
      display: flex;
      align-items: center;
      gap: 10px;
      margin-bottom: 28px;
    }

    .logo svg { width: 28px; height: 28px; fill: #e7e9ea; flex-shrink: 0; }

    .logo-text {
      font-size: 22px;
      font-weight: 700;
      letter-spacing: -0.5px;
    }

    h2 {
      font-size: 18px;
      font-weight: 600;
      margin-bottom: 6px;
    }

    .subtitle {
      font-size: 13px;
      color: #71767b;
      margin-bottom: 28px;
      line-height: 1.5;
    }

    .field { margin-bottom: 16px; }

    label {
      display: block;
      font-size: 12px;
      font-weight: 500;
      color: #71767b;
      margin-bottom: 6px;
      text-transform: uppercase;
      letter-spacing: 0.5px;
    }

    input {
      width: 100%;
      padding: 12px 14px;
      background: #000;
      border: 1px solid #2f3336;
      border-radius: 8px;
      color: #e7e9ea;
      font-size: 15px;
      outline: none;
      transition: border-color 0.2s;
    }

    input:focus { border-color: #1d9bf0; }
    input::placeholder { color: #3d4147; }

    .btn {
      width: 100%;
      padding: 13px;
      background: #1d9bf0;
      border: none;
      border-radius: 9999px;
      color: #fff;
      font-size: 15px;
      font-weight: 700;
      cursor: pointer;
      margin-top: 8px;
      transition: background 0.2s, opacity 0.2s;
    }

    .btn:hover { background: #1a8cd8; }
    .btn:disabled { opacity: 0.5; cursor: not-allowed; }

    .status {
      margin-top: 20px;
      padding: 12px 14px;
      border-radius: 8px;
      font-size: 14px;
      line-height: 1.5;
      display: none;
    }

    .status.info    { background: #1e2a3a; border: 1px solid #1d9bf0; color: #7ec8f7; display: block; }
    .status.error   { background: #2a1a1a; border: 1px solid #f4212e; color: #f4646e; display: block; }
    .status.success { background: #0d2118; border: 1px solid #00ba7c; color: #4dce9d; display: block; }

    .spinner {
      display: inline-block;
      width: 14px; height: 14px;
      border: 2px solid rgba(255,255,255,0.3);
      border-top-color: #fff;
      border-radius: 50%;
      animation: spin 0.7s linear infinite;
      vertical-align: middle;
      margin-right: 6px;
    }
    @keyframes spin { to { transform: rotate(360deg); } }

    .hidden { display: none !important; }

    #jobSection { margin-top: 24px; }
    .job-id {
      font-size: 11px;
      color: #71767b;
      word-break: break-all;
      margin-top: 8px;
    }
    .poll-bar {
      height: 3px;
      background: #1d9bf0;
      border-radius: 2px;
      width: 0%;
      transition: width 0.5s;
      margin-top: 12px;
    }
  </style>
</head>
<body>
<div class="card">
  <div class="logo">
    <!-- X logo -->
    <svg viewBox="0 0 24 24" xmlns="http://www.w3.org/2000/svg">
      <path d="M18.244 2.25h3.308l-7.227 8.26 8.502 11.24H16.17l-4.714-6.231-5.401 6.231H2.746l7.73-8.835L1.254 2.25H8.08l4.259 5.631 5.905-5.631zm-1.161 17.52h1.833L7.084 4.126H5.117z"/>
    </svg>
    <span class="logo-text">AutoX</span>
  </div>

  <h2>Sign in to get started</h2>
  <p class="subtitle">Enter your X / Twitter credentials. Your password is used only to authenticate — it is never stored.</p>

  <div class="field">
    <label for="topic">Topic</label>
    <input id="topic" type="text" placeholder="e.g. AI in healthcare" autocomplete="off"/>
  </div>

  <div class="field">
    <label for="username">Username or Email</label>
    <input id="username" type="text" placeholder="@handle or email" autocomplete="username"/>
  </div>

  <div class="field">
    <label for="password">Password</label>
    <input id="password" type="password" placeholder="••••••••" autocomplete="current-password"/>
  </div>

  <div id="twoFactorField" class="field hidden">
    <label for="twoFactor">2FA / Verification Code</label>
    <input id="twoFactor" type="text" placeholder="6-digit code or backup code" autocomplete="one-time-code" inputmode="numeric"/>
  </div>

  <button class="btn" id="submitBtn" onclick="handleSubmit()">Start</button>

  <div id="status" class="status"></div>

  <div id="jobSection" class="hidden">
    <div class="poll-bar" id="pollBar"></div>
    <div class="job-id" id="jobIdLabel"></div>
  </div>
</div>

<script>
  let jobId = null;
  let pollInterval = null;
  let pollProgress = 0;

  function setStatus(msg, type) {
    const el = document.getElementById('status');
    el.className = 'status ' + type;
    el.innerHTML = msg;
  }

  function setLoading(loading) {
    const btn = document.getElementById('submitBtn');
    btn.disabled = loading;
    btn.innerHTML = loading
      ? '<span class="spinner"></span> Working…'
      : 'Start';
  }

  async function handleSubmit() {
    const topic    = document.getElementById('topic').value.trim();
    const username = document.getElementById('username').value.trim();
    const password = document.getElementById('password').value;
    const twoFactor = document.getElementById('twoFactor').value.trim();

    if (!topic)    { setStatus('Please enter a topic.', 'error'); return; }
    if (!username) { setStatus('Please enter your username or email.', 'error'); return; }
    if (!password) { setStatus('Please enter your password.', 'error'); return; }

    setLoading(true);
    setStatus('<span class="spinner"></span> Authenticating with X…', 'info');

    const payload = { topic, username, password };
    if (twoFactor) payload.two_factor_code = twoFactor;

    try {
      const res  = await fetch('/api/v1/auth-run', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(payload),
      });
      const data = await res.json();

      if (data.requires_2fa) {
        document.getElementById('twoFactorField').classList.remove('hidden');
        setStatus('Two-factor authentication required. Enter your code above and click Start again.', 'info');
        setLoading(false);
        return;
      }

      if (!data.success) {
        setStatus('❌ ' + (data.message || 'Authentication failed.'), 'error');
        setLoading(false);
        return;
      }

      // Successfully queued
      jobId = data.job_id;
      document.getElementById('jobSection').classList.remove('hidden');
      document.getElementById('jobIdLabel').textContent = 'Job ID: ' + jobId;
      setStatus('✅ Authenticated! Background job is running…', 'success');
      startPolling();

    } catch (err) {
      setStatus('❌ Network error: ' + err.message, 'error');
      setLoading(false);
    }
  }

  function startPolling() {
    pollProgress = 5;
    pollInterval = setInterval(pollJob, 4000);
  }

  async function pollJob() {
    if (!jobId) return;
    try {
      const res  = await fetch('/api/v1/jobs/' + jobId);
      const data = await res.json();

      pollProgress = Math.min(pollProgress + 8, 90);
      document.getElementById('pollBar').style.width = pollProgress + '%';

      if (data.status === 'completed') {
        clearInterval(pollInterval);
        document.getElementById('pollBar').style.width = '100%';
        setStatus('🎉 Done! ' + (data.message || 'Thread posted successfully.'), 'success');
        setLoading(false);
      } else if (data.status === 'failed') {
        clearInterval(pollInterval);
        document.getElementById('pollBar').style.width = '100%';
        setStatus('❌ Job failed: ' + (data.message || 'Unknown error.'), 'error');
        setLoading(false);
      } else {
        setStatus('<span class="spinner"></span> ' + (data.message || 'Running…'), 'info');
      }
    } catch (e) {
      // Network blip — keep polling
    }
  }

  // Allow Enter key to submit
  document.addEventListener('keydown', e => {
    if (e.key === 'Enter' && !document.getElementById('submitBtn').disabled) {
      handleSubmit();
    }
  });
</script>
</body>
</html>
""")


@router.post(
    "/run",
    response_model=AgentResponse,
    summary="Run the Twitter AI Agent (direct, blocking)",
)
async def run_agent(request: AgentRequest) -> AgentResponse:
    logger.info(f"POST /run — topic='{request.topic}'")
    try:
        if not request.auth_storage_state_b64 and not (request.username and request.password):
            raise HTTPException(
                status_code=400,
                detail="Provide username+password or auth_storage_state_b64.",
            )
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


@router.post("/auth-run", response_model=AuthRunResponse)
async def auth_run(request: AuthRunRequest) -> AuthRunResponse:
    logger.info(f"POST /auth-run — topic='{request.topic}' user='{request.username}'")
    auth_service = AuthService()
    result = await auth_service.authenticate(
        username=request.username,
        password=request.password,
        two_factor_code=request.two_factor_code,
        backup_code=request.backup_code,
    )

    if result.requires_2fa:
        return AuthRunResponse(
            success=False,
            status="requires_2fa",
            message=result.message,
            requires_2fa=True,
        )

    if not result.success or not result.storage_state_b64:
        return AuthRunResponse(
            success=False,
            status="failed",
            message=result.message or "Authentication failed.",
        )

    job = job_manager.create_job(message="Authentication successful. Starting headless work.")

    async def _run_background() -> None:
        try:
            job_manager.update(job.job_id, status="running", message="Running agent…")
            agent = TwitterAgent()
            response = await agent.run(
                AgentRequest(
                    topic=request.topic,
                    auth_storage_state_b64=result.storage_state_b64,
                )
            )
            if response.success:
                job_manager.update(
                    job.job_id,
                    status="completed",
                    message=response.message,
                    success=True,
                    result=response.model_dump(),
                )
            else:
                job_manager.update(
                    job.job_id,
                    status="failed",
                    message=response.message,
                    success=False,
                    error=response.message,
                )
        except Exception as exc:
            job_manager.update(
                job.job_id,
                status="failed",
                message=str(exc),
                success=False,
                error=str(exc),
            )

    asyncio.create_task(_run_background())

    return AuthRunResponse(
        success=True,
        job_id=job.job_id,
        status="queued",
        message="Authenticated. Background job started.",
    )


@router.get("/jobs/{job_id}", response_model=JobStatusResponse)
async def get_job_status(job_id: str) -> JobStatusResponse:
    job = job_manager.get(job_id)
    if not job:
        raise HTTPException(status_code=404, detail="Job not found")
    return JobStatusResponse(
        job_id=job.job_id,
        status=job.status,
        message=job.message,
        success=job.success,
    )