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
    # If users cannot produce a Playwright storage_state, they can provide values
    # copied from the browser DevTools. The server will convert them into a
    # Playwright storage_state in-flight.
    cookies: Optional[str] = Field(
        default=None,
        description="The `document.cookie` string copied from DevTools (e.g. 'a=1; b=2')",
    )
    local_storage: Optional[str] = Field(
        default=None,
        description="A JSON string representing `localStorage` (copy via DevTools)",
    )
    session_storage: Optional[str] = Field(
        default=None,
        description="A JSON string representing `sessionStorage` (optional)",
    )
    origin: Optional[str] = Field(
        default="https://x.com",
        description="Origin to attach the storage to (default https://x.com)",
    )


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
