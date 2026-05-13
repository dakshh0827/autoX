"""
agent.py
~~~~~~~~
Orchestrates the full Twitter automation workflow:
  1. Generate thread via Groq
  2. Open browser → user logs in
  3. Post thread
  4. Interact with 10 feed posts
  5. Follow 5 relevant accounts
"""

import time
from app.services.groq_service import GroqService
# TwitterBrowser imports Playwright; import lazily inside `run()` to avoid
# blocking application startup during module import in environments where
# Playwright setup is slow or unavailable.
from app.models.schemas import AgentRequest, AgentResponse, ThreadResult, InteractionResult, FollowResult
from app.core.logger import get_logger

logger = get_logger(__name__)


class TwitterAgent:
    def __init__(self):
        self.groq = GroqService()

    async def run(self, request: AgentRequest) -> AgentResponse:
        topic = request.topic.strip()
        logger.info(f"🚀 Agent starting — topic: '{topic}'")
        start_time = time.time()

        # Lazy import to avoid importing Playwright at app import time
        from app.services.twitter_browser import TwitterBrowser

        browser = TwitterBrowser()
        try:
            # ── Step 1: Generate content with Groq ────────────────────────────
            logger.info("Step 1/4 — Generating content with Groq")
            tweets = self.groq.generate_thread(topic)
            search_queries = self.groq.extract_search_queries(topic)
            logger.info(
                f"  Generated {len(tweets)} tweets | "
                f"Search queries: {search_queries}"
            )

            # ── Step 2: Launch browser & authenticate ─────────────────────────
            logger.info("Step 2/4 — Launching browser for user authentication")
            await browser.start()
            await browser.navigate_to_login()

            # ── Step 3: Post the thread ───────────────────────────────────────
            logger.info("Step 3/4 — Posting thread")
            await browser.post_thread(tweets)
            thread_result = ThreadResult(
                tweets=tweets,
                tweet_count=len(tweets),
                posted=True,
            )

            # ── Step 4a: Interact with feed ───────────────────────────────────
            logger.info("Step 4a/4 — Interacting with feed posts")
            raw_interactions = await browser.interact_with_feed(
                topic=topic,
                groq_svc=self.groq,
                target=10,
            )
            interactions = [
                InteractionResult(
                    tweet_url=i["tweet_url"],
                    tweet_preview=i["tweet_preview"],
                    liked=i["liked"],
                    replied=i["replied"],
                    reply_text=i.get("reply_text"),
                )
                for i in raw_interactions
            ]

            # ── Step 4b: Follow relevant accounts ─────────────────────────────
            logger.info("Step 4b/4 — Following relevant accounts")
            raw_follows = await browser.follow_relevant_accounts(
                topic=topic,
                groq_svc=self.groq,
                queries=search_queries,
                target=5,
            )
            follows = [
                FollowResult(
                    handle=f["handle"],
                    bio=f["bio"],
                    relevance_score=f["relevance_score"],
                    followed=f["followed"],
                )
                for f in raw_follows
            ]

            elapsed = round(time.time() - start_time, 1)
            logger.info(f"✅ Agent completed in {elapsed}s")

            return AgentResponse(
                success=True,
                topic=topic,
                thread=thread_result,
                interactions=interactions,
                follows=follows,
                interactions_count=len(interactions),
                follows_count=len(follows),
                elapsed_seconds=elapsed,
                message=(
                    f"Successfully posted {len(tweets)}-tweet thread, "
                    f"interacted with {len(interactions)} posts, "
                    f"followed {len(follows)} accounts."
                ),
            )

        except Exception as e:
            elapsed = round(time.time() - start_time, 1)
            logger.error(f"Agent failed after {elapsed}s: {e}", exc_info=True)
            return AgentResponse(
                success=False,
                topic=topic,
                thread=None,
                interactions=[],
                follows=[],
                interactions_count=0,
                follows_count=0,
                elapsed_seconds=elapsed,
                message=f"Agent failed: {str(e)}",
            )
        finally:
            await browser.close()
