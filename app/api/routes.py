from fastapi import APIRouter, HTTPException, BackgroundTasks
from app.models.schemas import AgentRequest, AgentResponse
from app.services.agent import TwitterAgent
from app.core.logger import get_logger

router = APIRouter()
logger = get_logger(__name__)


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
