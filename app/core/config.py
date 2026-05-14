from typing import Optional

from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    # Server
    HOST: str = "0.0.0.0"
    # Default to the common Hugging Face Spaces port so the container
    # listens correctly when the platform does not inject `PORT`.
    PORT: int = 7860
    DEBUG: bool = False

    # Groq
    GROQ_API_KEY: Optional[str] = None
    GROQ_MODEL: str = "llama-3.3-70b-versatile"

    # Playwright
    BROWSER_HEADLESS: bool = False  # Set True for server deployments
    BROWSER_SLOW_MO: int = 800       # ms between actions for human-like behaviour
    TWITTER_BASE_URL: str = "https://x.com"
    # Optional path to a Playwright storage_state.json file containing an
    # authenticated user session. Use this to reuse a logged-in session in
    # headless server environments (e.g., Hugging Face Spaces).
    STORAGE_STATE_FILE: Optional[str] = None
    # Alternatively, provide the storage state as a base64-encoded JSON string
    # in an environment variable (useful for Secrets). If both are present,
    # STORAGE_STATE_FILE takes precedence.
    STORAGE_STATE_B64: Optional[str] = None

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
