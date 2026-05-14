import uvicorn
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from app.api.routes import router
from app.core.config import settings
import os
from app.core.logger import get_logger

logger = get_logger(__name__)

app = FastAPI(
    title="Twitter AI Agent",
    description="AI-powered Twitter automation agent using Playwright and Groq",
    version="1.0.0",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(router, prefix="/api/v1")


@app.get("/health")
async def health_check():
    return {"status": "healthy", "service": "Twitter AI Agent"}


@app.on_event("startup")
async def _log_runtime_info():
    # Log effective port and host to help debug deployment environments
    env_port = os.environ.get("PORT")
    logger.info(f"Effective settings.PORT={settings.PORT} env PORT={env_port}")


if __name__ == "__main__":
    uvicorn.run(
        "main:app",
        host=settings.HOST,
        port=settings.PORT,
        reload=settings.DEBUG,
    )
