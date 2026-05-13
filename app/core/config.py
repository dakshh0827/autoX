from pydantic_settings import BaseSettings
from typing import Optional


class Settings(BaseSettings):
    # Server
    HOST: str = "0.0.0.0"
    PORT: int = 8000
    DEBUG: bool = False

    # Groq
    GROQ_API_KEY: str
    GROQ_MODEL: str = "llama-3.3-70b-versatile"

    # Playwright
    BROWSER_HEADLESS: bool = False  # Set True for server deployments
    BROWSER_SLOW_MO: int = 800       # ms between actions for human-like behaviour
    TWITTER_BASE_URL: str = "https://x.com"

    # Agent behaviour
    THREAD_MIN_TWEETS: int = 5
    THREAD_MAX_TWEETS: int = 8
    INTERACTIONS_TARGET: int = 10
    FOLLOWS_TARGET: int = 5
    ACTION_DELAY_MIN: float = 2.0    # seconds
    ACTION_DELAY_MAX: float = 5.0    # seconds

    class Config:
        env_file = ".env"
        env_file_encoding = "utf-8"


settings = Settings()
