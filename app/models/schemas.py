from typing import List, Optional
from pydantic import BaseModel, Field


class AgentRequest(BaseModel):
    topic: str = Field(
        ...,
        min_length=3,
        max_length=200,
        description="The topic the agent should create content and engage around",
        examples=["The future of renewable energy in India"],
    )
    auth_storage_state_b64: Optional[str] = Field(
        default=None,
        description=(
            "Optional base64-encoded Playwright storage_state JSON for the user's "
            "authenticated X/Twitter session. Pass this for headless runs in Spaces."
        ),
    )
    username: Optional[str] = Field(default=None, max_length=200)
    password: Optional[str] = Field(default=None, max_length=200)
    two_factor_code: Optional[str] = Field(default=None, max_length=50)
    backup_code: Optional[str] = Field(default=None, max_length=50)


class AuthRunRequest(BaseModel):
    topic: str = Field(..., min_length=3, max_length=200)
    username: str = Field(..., min_length=1, max_length=200)
    password: str = Field(..., min_length=1, max_length=200)
    two_factor_code: Optional[str] = Field(default=None, max_length=50)
    backup_code: Optional[str] = Field(default=None, max_length=50)


class AuthRunResponse(BaseModel):
    success: bool
    job_id: Optional[str] = None
    status: str
    message: str
    requires_2fa: bool = False


class JobStatusResponse(BaseModel):
    job_id: str
    status: str
    message: str
    success: Optional[bool] = None


class ThreadResult(BaseModel):
    tweets: List[str]
    tweet_count: int
    posted: bool


class InteractionResult(BaseModel):
    tweet_url: str
    tweet_preview: str
    liked: bool
    replied: bool
    reply_text: Optional[str] = None


class FollowResult(BaseModel):
    handle: str
    bio: str
    relevance_score: float
    followed: bool


class AgentResponse(BaseModel):
    success: bool
    topic: str
    thread: Optional[ThreadResult]
    interactions: List[InteractionResult]
    follows: List[FollowResult]
    interactions_count: int
    follows_count: int
    elapsed_seconds: float
    message: str
