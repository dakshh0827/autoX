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
