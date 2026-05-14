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
from app.core.logger import get_logger

router = APIRouter()
logger = get_logger(__name__)


@router.get("/", include_in_schema=False)
async def root() -> RedirectResponse:
    return RedirectResponse(url="/api/v1/auth", status_code=302)


@router.get(
        "/auth",
        response_class=HTMLResponse,
        summary="Open the credential UI",
)
async def auth_ui() -> HTMLResponse:
        return HTMLResponse(
                """
<!doctype html>
<html>
<head>
    <meta charset="utf-8" />
    <meta name="viewport" content="width=device-width, initial-scale=1" />
    <title>AutoX Login</title>
    <style>
        body { font-family: system-ui, sans-serif; max-width: 560px; margin: 40px auto; padding: 0 16px; }
        input, button { width: 100%; padding: 12px; margin: 8px 0; font-size: 16px; }
        button { cursor: pointer; }
        .hidden { display: none; }
        .status { margin-top: 12px; white-space: pre-wrap; }
    </style>
</head>
<body>
    <h2>Authenticate to X / Twitter</h2>
    <p>Enter your own credentials. After success, the UI closes and the backend runs headless.</p>
    <form id="authForm">
        <input name="topic" placeholder="Topic" required />
        <input name="username" placeholder="X username or email" autocomplete="username" required />
        <input name="password" placeholder="Password" type="password" autocomplete="current-password" required />
        <input name="two_factor_code" id="twoFactorCode" class="hidden" placeholder="2FA code or backup code" autocomplete="one-time-code" />
        <button type="submit">Start</button>
    </form>
    <div id="status" class="status"></div>
    <script>
        const form = document.getElementById('authForm');
        const statusEl = document.getElementById('status');
        const twoFactorInput = document.getElementById('twoFactorCode');

        form.addEventListener('submit', async (event) => {
            event.preventDefault();
            statusEl.textContent = 'Working...';
            const payload = Object.fromEntries(new FormData(form).entries());
            const response = await fetch('/api/v1/auth-run', {
                method: 'POST',
                headers: {'Content-Type': 'application/json'},
                body: JSON.stringify(payload),
            });
            const data = await response.json();

            if (data.requires_2fa) {
                twoFactorInput.classList.remove('hidden');
                statusEl.textContent = data.message || 'Enter your 2FA or backup code.';
                return;
            }

            if (!data.success) {
                statusEl.textContent = data.message || 'Authentication failed.';
                return;
            }

            statusEl.textContent = 'Queued. Closing window...';
            setTimeout(() => window.close(), 800);
        });
    </script>
</body>
</html>
                """
        )


@router.post(
    "/run",
    response_model=AgentResponse,
    summary="Run the Twitter AI Agent",
    description=(
        "Launches a Playwright browser session, waits for the user to log in to Twitter, "
        "then autonomously posts a thread, interacts with 10 feed posts, and follows 5 "
        "topic-relevant accounts — all in a single call."
    ),
)
async def run_agent(request: AgentRequest) -> AgentResponse:
    logger.info(f"POST /run — topic='{request.topic}'")
    try:
        if not request.auth_storage_state_b64:
            raise HTTPException(
                status_code=400,
                detail=(
                    "This endpoint now requires user auth data. Open /api/v1/auth "
                    "or send auth_storage_state_b64 in the request."
                ),
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
            job_manager.update(job.job_id, status="running", message="Running agent...")
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
