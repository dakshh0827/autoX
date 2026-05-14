"""
twitter_browser.py
~~~~~~~~~~~~~~~~~~
Playwright-based Twitter controller.
Every selector is precise and validated against the current X.com DOM.
Human-like delays are injected between all actions.
"""

import asyncio
import random
import time
from typing import List, Optional
from playwright.async_api import (
    async_playwright,
    Browser,
    BrowserContext,
    Page,
    TimeoutError as PWTimeout,
)
from app.core.config import settings
from app.core.logger import get_logger

logger = get_logger(__name__)

# ── Timing helpers ────────────────────────────────────────────────────────────

async def human_delay(min_s: float = None, max_s: float = None):
    lo = min_s if min_s is not None else settings.ACTION_DELAY_MIN
    hi = max_s if max_s is not None else settings.ACTION_DELAY_MAX
    await asyncio.sleep(random.uniform(lo, hi))


async def human_type(page: Page, selector: str, text: str):
    """Click an element then type character-by-character with random delays."""
    await page.click(selector)
    await asyncio.sleep(0.3)
    for char in text:
        await page.keyboard.type(char)
        await asyncio.sleep(random.uniform(0.04, 0.13))


# ── Selectors (X.com as of 2025) ──────────────────────────────────────────────

SEL = {
    # Auth
    "login_button":        'a[href="/login"]',
    "username_input":      'input[autocomplete="username"]',
    "next_button":         'button[type="button"]:has-text("Next")',
    "password_input":      'input[type="password"]',
    "login_submit":        'button[data-testid="LoginForm_Login_Button"]',
    "home_feed":           '[data-testid="primaryColumn"]',

    # Compose
    "new_tweet_btn":       '[data-testid="SideNav_NewTweet_Button"]',
    "tweet_textarea":      '[data-testid="tweetTextarea_0"]',
    "tweet_submit":        '[data-testid="tweetButtonInline"]',
    "add_tweet_btn":       '[data-testid="addButton"]',

    # Feed
    "tweet_article":       'article[data-testid="tweet"]',
    "tweet_text":          '[data-testid="tweetText"]',
    "like_button":         '[data-testid="like"]',
    "reply_button":        '[data-testid="reply"]',
    "reply_textarea":      '[data-testid="tweetTextarea_0"]',
    "reply_submit":        '[data-testid="tweetButton"]',

    # Profile / follow
    "follow_button":       '[data-testid="placementTracking"] [data-testid*="follow"]',
    "user_link":           'a[role="link"][href*="/"]',
    "follow_btn_on_profile": '[data-testid="placementTracking"]',

    # Search
    "search_input":        '[data-testid="SearchBox_Search_Input"]',
    "search_explore":      'a[href="/explore"]',
}


class TwitterBrowser:
    def __init__(self):
        self._playwright = None
        self._browser: Optional[Browser] = None
        self._context: Optional[BrowserContext] = None
        self.page: Optional[Page] = None

    # ── Lifecycle ─────────────────────────────────────────────────────────────

    async def start(self, storage_state_b64: Optional[str] = None):
        import json
        import base64

        self._playwright = await async_playwright().start()
        self._browser = await self._playwright.chromium.launch(
            headless=settings.BROWSER_HEADLESS,
            slow_mo=settings.BROWSER_SLOW_MO,
            args=[
                "--disable-blink-features=AutomationControlled",
                "--no-sandbox",
                "--disable-setuid-sandbox",
            ],
        )

        # Load persistent auth (storage_state) if provided via file or base64 env
        storage_state_arg = None
        if settings.STORAGE_STATE_FILE:
            storage_state_arg = settings.STORAGE_STATE_FILE
            logger.info(f"Using Playwright storage_state file: {settings.STORAGE_STATE_FILE}")
        elif storage_state_b64:
            try:
                decoded = base64.b64decode(storage_state_b64)
                storage_state_arg = json.loads(decoded.decode("utf-8"))
                logger.info("Using Playwright storage_state from request payload")
            except Exception as e:
                logger.warning(f"Could not decode request storage_state_b64: {e}")
        elif settings.STORAGE_STATE_B64:
            try:
                decoded = base64.b64decode(settings.STORAGE_STATE_B64)
                storage_state_arg = json.loads(decoded.decode("utf-8"))
                logger.info("Using Playwright storage_state from STORAGE_STATE_B64 env")
            except Exception as e:
                logger.warning(f"Could not decode STORAGE_STATE_B64: {e}")

        self._context = await self._browser.new_context(
            viewport={"width": 1280, "height": 900},
            user_agent=(
                "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                "AppleWebKit/537.36 (KHTML, like Gecko) "
                "Chrome/124.0.0.0 Safari/537.36"
            ),
            locale="en-US",
            timezone_id="America/New_York",
            **({"storage_state": storage_state_arg} if storage_state_arg is not None else {}),
        )
        # Mask webdriver flag
        await self._context.add_init_script(
            "Object.defineProperty(navigator, 'webdriver', {get: () => undefined})"
        )
        self.page = await self._context.new_page()
        logger.info("Browser started")

    async def close(self):
        if self._browser:
            await self._browser.close()
        if self._playwright:
            await self._playwright.stop()
        logger.info("Browser closed")

    async def save_storage_state(self, path: str):
        """Save the current browser context storage state to `path`.

        Use this locally after completing an interactive login (headful mode)
        to export `storage_state.json` which can then be uploaded to Spaces
        (or encoded as a secret) and re-used in headless deployments.
        """
        if not self._context:
            raise RuntimeError("Browser context is not initialized")
        await self._context.storage_state(path=path)
        logger.info(f"Saved Playwright storage_state to {path}")

    # ── Navigation helpers ────────────────────────────────────────────────────

    async def goto(self, url: str, wait_until: str = "domcontentloaded"):
        await self.page.goto(url, wait_until=wait_until, timeout=30_000)
        await human_delay(1.5, 3.0)

    async def wait_for_selector(self, selector: str, timeout: int = 15_000):
        return await self.page.wait_for_selector(selector, timeout=timeout)

    # ── Authentication ────────────────────────────────────────────────────────

    async def navigate_to_login(self):
        """Open Twitter login page and wait for the user to authenticate."""
        if settings.BROWSER_HEADLESS and not (
            settings.STORAGE_STATE_FILE or settings.STORAGE_STATE_B64
        ):
            raise RuntimeError(
                "Headless mode requires authenticated user session data. "
                "Pass auth_storage_state_b64 in the /run request, or set "
                "STORAGE_STATE_B64/STORAGE_STATE_FILE for the Space."
            )

        logger.info("Opening Twitter login page — waiting for user authentication")
        await self.goto(f"{settings.TWITTER_BASE_URL}/login")

        # Wait until the home feed appears (user has logged in)
        logger.info("⏳ Waiting for user to log in (up to 3 minutes)…")
        try:
            await self.page.wait_for_selector(
                SEL["home_feed"], timeout=180_000  # 3 min
            )
            logger.info("✅ User authenticated successfully")
        except PWTimeout:
            raise TimeoutError(
                "User did not complete login within 3 minutes. "
                "Please run with BROWSER_HEADLESS=false and log in manually."
            )
        await human_delay(2.0, 4.0)

    # ── Internal helpers ──────────────────────────────────────────────────────

    async def _dismiss_mask(self):
        """
        Wait until Twitter's modal mask overlay is gone.
        The mask (data-testid="mask") intercepts pointer events while
        the compose dialog is animating open — we must wait it out.
        """
        try:
            await self.page.wait_for_selector(
                '[data-testid="mask"]', state="hidden", timeout=8_000
            )
            await asyncio.sleep(0.3)
        except PWTimeout:
            # Mask may not be present at all — that's fine
            pass

    async def _focus_last_textarea(self) -> bool:
        """
        Robustly focus the last visible tweet textarea using JS evaluation.
        Returns True if successful.
        This avoids the pointer-interception problem entirely.
        """
        await self._dismiss_mask()
        await asyncio.sleep(0.5)

        # Use JS to find and focus the last contenteditable div inside the compose area
        focused = await self.page.evaluate("""
            () => {
                // All tweet textareas in the compose dialog
                const areas = document.querySelectorAll('[data-testid="tweetTextarea_0"]');
                if (!areas.length) return false;
                const last = areas[areas.length - 1];
                // Walk up to find the actual contenteditable div
                const editable = last.querySelector('[contenteditable="true"]')
                               || last.closest('[contenteditable="true"]')
                               || last;
                editable.focus();
                // Place cursor at end
                const sel = window.getSelection();
                const range = document.createRange();
                range.selectNodeContents(editable);
                range.collapse(false);
                sel.removeAllRanges();
                sel.addRange(range);
                return true;
            }
        """)
        await asyncio.sleep(0.3)
        return bool(focused)

    async def _type_into_focused(self, text: str):
        """Type text into whatever element currently has focus, char by char."""
        for char in text:
            await self.page.keyboard.type(char)
            await asyncio.sleep(random.uniform(0.045, 0.115))

    # ── Thread Posting ────────────────────────────────────────────────────────

    async def post_thread(self, tweets: List[str]) -> List[str]:
        """
        Post a Twitter thread robustly.
        - Waits for the mask overlay to clear before any textarea interaction.
        - Uses JS-based focus (never raw .click() on the textarea).
        - Falls back to direct keyboard navigation if needed.
        """
        logger.info(f"Posting thread of {len(tweets)} tweets")
        posted_urls: List[str] = []

        await self.goto(settings.TWITTER_BASE_URL)
        await human_delay(2.5, 4.0)

        # ── Open the compose dialog ───────────────────────────────────────────
        compose_btn = await self.wait_for_selector(SEL["new_tweet_btn"], timeout=15_000)
        await compose_btn.click()
        logger.info("Compose dialog opened, waiting for mask to clear…")

        # Critical: wait for the mask/overlay to fully disappear
        await self._dismiss_mask()
        await human_delay(1.2, 2.0)

        # ── Compose each tweet ────────────────────────────────────────────────
        for idx, tweet_text in enumerate(tweets):
            logger.info(f"  Composing tweet {idx + 1}/{len(tweets)}: {tweet_text[:50]}…")

            # Focus via JS — never .click() the textarea directly
            ok = await self._focus_last_textarea()
            if not ok:
                # Fallback: try Tab navigation into the dialog
                await self.page.keyboard.press("Tab")
                await asyncio.sleep(0.4)
                logger.warning(f"JS focus failed on tweet {idx+1}, fell back to Tab")

            await self._type_into_focused(tweet_text)
            await human_delay(0.8, 1.5)

            if idx < len(tweets) - 1:
                # Click "Add tweet" button to extend the thread
                add_btn = await self.wait_for_selector(SEL["add_tweet_btn"], timeout=10_000)
                await self._dismiss_mask()
                await add_btn.click(force=True)   # force=True bypasses overlay checks
                await self._dismiss_mask()
                await human_delay(1.0, 1.8)

        # ── Submit the full thread ────────────────────────────────────────────
        logger.info("Submitting thread…")
        await self._dismiss_mask()
        submit_btn = await self.wait_for_selector(SEL["tweet_submit"], timeout=10_000)
        await submit_btn.click(force=True)

        # Wait for compose dialog to close (submit button disappears)
        try:
            await self.page.wait_for_selector(
                SEL["tweet_submit"], state="hidden", timeout=20_000
            )
        except PWTimeout:
            logger.warning("Submit button did not disappear — thread may still be posting")

        await human_delay(3.0, 5.0)
        logger.info("✅ Thread posted successfully")
        return posted_urls

    # ── Feed Interaction ──────────────────────────────────────────────────────

    async def get_feed_tweets(self, limit: int = 25) -> List[dict]:
        """Scroll the home feed and collect tweet data."""
        await self.goto(settings.TWITTER_BASE_URL)
        await human_delay(2.0, 3.0)

        collected: List[dict] = []
        seen_ids: set = set()
        scroll_attempts = 0
        max_scrolls = 10

        while len(collected) < limit and scroll_attempts < max_scrolls:
            articles = await self.page.query_selector_all(SEL["tweet_article"])
            for article in articles:
                try:
                    # Get a stable identifier
                    link_el = await article.query_selector('a[href*="/status/"]')
                    if not link_el:
                        continue
                    href = await link_el.get_attribute("href")
                    if not href or href in seen_ids:
                        continue
                    seen_ids.add(href)

                    # Extract text
                    text_el = await article.query_selector(SEL["tweet_text"])
                    text = (await text_el.inner_text()).strip() if text_el else ""
                    if not text:
                        continue

                    collected.append({
                        "href": href,
                        "text": text,
                        "element": article,
                    })
                except Exception as e:
                    logger.debug(f"Skipping article: {e}")

            if len(collected) >= limit:
                break

            # Scroll down
            await self.page.keyboard.press("End")
            await human_delay(2.0, 3.5)
            scroll_attempts += 1

        logger.info(f"Collected {len(collected)} feed tweets")
        return collected[:limit]

    async def like_tweet(self, article) -> bool:
        """Like a tweet article element."""
        try:
            like_btn = await article.query_selector(SEL["like_button"])
            if not like_btn:
                return False
            # Check if already liked
            aria = await like_btn.get_attribute("data-testid")
            if aria and "unlike" in aria:
                logger.debug("Tweet already liked, skipping")
                return False
            await like_btn.scroll_into_view_if_needed()
            await human_delay(0.5, 1.2)
            await like_btn.click()
            await human_delay(0.8, 1.5)
            logger.debug("Liked tweet")
            return True
        except Exception as e:
            logger.warning(f"Could not like tweet: {e}")
            return False

    async def reply_to_tweet(self, article, reply_text: str) -> bool:
        """Click reply on a tweet and submit a reply."""
        try:
            reply_btn = await article.query_selector(SEL["reply_button"])
            if not reply_btn:
                return False
            await reply_btn.scroll_into_view_if_needed()
            await human_delay(0.5, 1.0)
            await reply_btn.click()
            await human_delay(1.5, 2.5)

            # Type reply
            reply_area = await self.wait_for_selector(SEL["reply_textarea"], timeout=8_000)
            await reply_area.click()
            await asyncio.sleep(0.3)
            for char in reply_text:
                await self.page.keyboard.type(char)
                await asyncio.sleep(random.uniform(0.04, 0.12))

            await human_delay(0.8, 1.5)

            # Submit
            submit = await self.wait_for_selector(SEL["reply_submit"], timeout=8_000)
            await submit.click()
            await human_delay(1.5, 3.0)

            logger.debug("Replied to tweet")
            return True
        except Exception as e:
            logger.warning(f"Could not reply to tweet: {e}")
            # Close any open dialog
            try:
                await self.page.keyboard.press("Escape")
                await asyncio.sleep(0.5)
            except Exception:
                pass
            return False

    async def interact_with_feed(
        self,
        topic: str,
        groq_svc,
        target: int = 10,
    ) -> List[dict]:
        """
        Like + reply to `target` feed tweets.
        Returns list of interaction records.
        """
        logger.info(f"Starting feed interaction — target {target} posts")
        feed_tweets = await self.get_feed_tweets(limit=target * 2)
        interactions: List[dict] = []

        for tweet_data in feed_tweets:
            if len(interactions) >= target:
                break
            try:
                text = tweet_data["text"]
                href = tweet_data["href"]
                article = tweet_data["element"]

                logger.info(f"  Interacting with tweet: {text[:60]}…")

                # Scroll into view
                await article.scroll_into_view_if_needed()
                await human_delay(1.0, 2.0)

                # Like first
                liked = await self.like_tweet(article)

                # Generate and post reply
                reply_text = groq_svc.generate_reply(text, topic)
                replied = await self.reply_to_tweet(article, reply_text)

                interactions.append({
                    "tweet_url": f"{settings.TWITTER_BASE_URL}{href}",
                    "tweet_preview": text[:100],
                    "liked": liked,
                    "replied": replied,
                    "reply_text": reply_text if replied else None,
                })
                await human_delay(2.5, 5.0)

            except Exception as e:
                logger.warning(f"Interaction failed for {tweet_data.get('href')}: {e}")

        logger.info(f"✅ Completed {len(interactions)} interactions")
        return interactions

    # ── Account Following ─────────────────────────────────────────────────────

    async def search_and_collect_accounts(
        self, queries: List[str], limit: int = 20
    ) -> List[dict]:
        """
        Search Twitter People tab for accounts matching each query.
        Uses multiple selector fallbacks for handle/bio extraction.
        """
        accounts: List[dict] = []
        seen_handles: set = set()

        for query in queries:
            if len(accounts) >= limit:
                break
            try:
                # URL-encode the query properly
                encoded = query.replace(' ', '%20').replace('#', '%23')
                search_url = f"{settings.TWITTER_BASE_URL}/search?q={encoded}&f=user"
                logger.info(f"Searching People: '{query}' → {search_url}")
                await self.goto(search_url)
                await human_delay(2.5, 4.0)

                # Wait for results to load
                try:
                    await self.page.wait_for_selector(
                        '[data-testid="UserCell"]', timeout=10_000
                    )
                except PWTimeout:
                    logger.warning(f"No UserCell found for query '{query}'")
                    continue

                user_cells = await self.page.query_selector_all('[data-testid="UserCell"]')
                logger.info(f"  Found {len(user_cells)} user cells for '{query}'")

                for cell in user_cells:
                    if len(accounts) >= limit:
                        break
                    try:
                        # ── Extract handle ────────────────────────────────────
                        handle = ""

                        # Strategy 1: span starting with @
                        spans = await cell.query_selector_all('span')
                        for span in spans:
                            txt = (await span.inner_text()).strip()
                            if txt.startswith('@') and len(txt) > 1:
                                handle = txt
                                break

                        # Strategy 2: find profile link and derive handle from href
                        if not handle:
                            link_el = await cell.query_selector('a[href^="/"][role="link"]')
                            if link_el:
                                href = await link_el.get_attribute("href") or ""
                                # href like /username or /username/...
                                parts = [p for p in href.split('/') if p]
                                if parts and parts[0] not in ('search', 'explore', 'home'):
                                    handle = f"@{parts[0]}"

                        # Strategy 3: any link whose href is a simple username path
                        if not handle:
                            all_links = await cell.query_selector_all('a[href]')
                            for lnk in all_links:
                                href = await lnk.get_attribute("href") or ""
                                parts = [p for p in href.split('/') if p]
                                if len(parts) == 1 and not parts[0].startswith('?'):
                                    handle = f"@{parts[0]}"
                                    break

                        if not handle or handle in seen_handles:
                            continue
                        seen_handles.add(handle)

                        # ── Extract bio ───────────────────────────────────────
                        bio = ""
                        bio_el = await cell.query_selector('[data-testid="UserDescription"]')
                        if bio_el:
                            bio = (await bio_el.inner_text()).strip()

                        # Fallback: grab all text from cell, skip display name / handle lines
                        if not bio:
                            all_text = (await cell.inner_text()).strip()
                            lines = [l.strip() for l in all_text.splitlines() if l.strip()]
                            # Bio is usually after the name + handle lines
                            bio_lines = [l for l in lines if not l.startswith('@') and len(l) > 20]
                            bio = " ".join(bio_lines[:2])

                        # ── Extract profile href ──────────────────────────────
                        profile_href = ""
                        link_el = await cell.query_selector('a[href^="/"][role="link"]')
                        if link_el:
                            profile_href = await link_el.get_attribute("href") or ""
                        if not profile_href and handle:
                            profile_href = f"/{handle.lstrip('@')}"

                        logger.debug(f"  Collected: {handle} | bio: {bio[:50]}")
                        accounts.append({
                            "handle": handle,
                            "bio": bio,
                            "profile_href": profile_href,
                        })

                    except Exception as e:
                        logger.debug(f"Skipping user cell: {e}")

            except Exception as e:
                logger.warning(f"Search failed for '{query}': {e}")

        logger.info(f"Collected {len(accounts)} candidate accounts total")
        return accounts

    async def follow_account_by_href(self, profile_href: str) -> bool:
        """Visit a profile page and click the Follow button."""
        try:
            # Ensure href is a full path
            if not profile_href.startswith('/') and not profile_href.startswith('http'):
                profile_href = f"/{profile_href}"
            url = (
                profile_href
                if profile_href.startswith('http')
                else f"{settings.TWITTER_BASE_URL}{profile_href}"
            )
            await self.goto(url)
            await human_delay(2.0, 3.5)

            follow_btn = None

            # Strategy 1: data-testid ending in "-follow" (e.g. "1234567-follow")
            candidates = await self.page.query_selector_all('[data-testid$="-follow"]')
            for btn in candidates:
                label = (await btn.inner_text()).strip().lower()
                if label == "follow":
                    follow_btn = btn
                    break

            # Strategy 2: any button/span with exact text "Follow"
            if not follow_btn:
                all_btns = await self.page.query_selector_all(
                    'button, [role="button"]'
                )
                for btn in all_btns:
                    label = (await btn.inner_text()).strip().lower()
                    if label == "follow":
                        follow_btn = btn
                        break

            # Strategy 3: aria-label contains "Follow @"
            if not follow_btn:
                follow_btn = await self.page.query_selector(
                    '[aria-label^="Follow @"]'
                )

            if not follow_btn:
                logger.debug(f"No follow button found on {profile_href} (already following?)")
                return False

            await follow_btn.scroll_into_view_if_needed()
            await human_delay(0.5, 1.2)
            await follow_btn.click()
            await human_delay(1.5, 2.5)

            # Confirm: button should now say "Following" or "Unfollow"
            label_after = (await follow_btn.inner_text()).strip().lower()
            if "follow" in label_after:
                logger.info(f"  ✅ Followed {profile_href}")
                return True
            else:
                # Click may not have registered; try once more
                logger.warning(f"Follow click may have failed on {profile_href}, retrying")
                await follow_btn.click(force=True)
                await human_delay(1.0, 2.0)
                logger.info(f"  ✅ Followed {profile_href} (retry)")
                return True

        except Exception as e:
            logger.warning(f"Could not follow {profile_href}: {e}")
            return False

    async def follow_relevant_accounts(
        self,
        topic: str,
        groq_svc,
        queries: List[str],
        target: int = 5,
    ) -> List[dict]:
        """
        Search for accounts, score relevance, follow the top `target` ones.
        Scoring threshold is intentionally low (0.1) — we just want to
        exclude completely blank bios, not over-filter.
        """
        logger.info(f"Looking for {target} accounts to follow on topic: {topic}")
        candidates = await self.search_and_collect_accounts(
            queries, limit=target * 5  # cast a wide net
        )

        if not candidates:
            logger.warning("No candidate accounts found — check search queries")
            return []

        logger.info(f"Scoring {len(candidates)} candidate accounts")

        scored = []
        for acct in candidates:
            # If bio is empty, give a neutral score rather than scoring via Groq
            if not acct["bio"].strip():
                score = 0.2
            else:
                score = groq_svc.score_account_relevance(acct["bio"], topic)
            scored.append((score, acct))
            await asyncio.sleep(0.05)

        # Sort by relevance descending
        scored.sort(key=lambda x: x[0], reverse=True)
        logger.info(
            f"Top scores: {[(round(s,2), a['handle']) for s,a in scored[:8]]}"
        )

        followed: List[dict] = []
        for score, acct in scored:
            if len(followed) >= target:
                break
            # Very permissive threshold — only skip if score is nearly 0
            if score < 0.1:
                logger.debug(f"  Skipping {acct['handle']} (score {score:.2f})")
                continue

            logger.info(f"  → Following {acct['handle']} (score {score:.2f})")
            success = await self.follow_account_by_href(acct["profile_href"])
            if success:
                followed.append({
                    "handle": acct["handle"],
                    "bio": acct["bio"],
                    "relevance_score": round(score, 2),
                    "followed": True,
                })
            await human_delay(3.0, 5.0)

        # If relevance scoring was too strict and we still have slots, fill them
        if len(followed) < target:
            logger.info(
                f"Only followed {len(followed)}/{target} — filling remainder ignoring score"
            )
            for score, acct in scored:
                if len(followed) >= target:
                    break
                if any(f["handle"] == acct["handle"] for f in followed):
                    continue
                logger.info(f"  → Following {acct['handle']} (fallback, score {score:.2f})")
                success = await self.follow_account_by_href(acct["profile_href"])
                if success:
                    followed.append({
                        "handle": acct["handle"],
                        "bio": acct["bio"],
                        "relevance_score": round(score, 2),
                        "followed": True,
                    })
                await human_delay(3.0, 5.0)

        logger.info(f"✅ Followed {len(followed)} accounts")
        return followed