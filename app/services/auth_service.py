from __future__ import annotations

import asyncio
import base64
import json
import os
import random
import tempfile
from dataclasses import dataclass
from typing import Optional

from playwright.async_api import async_playwright, TimeoutError as PWTimeout

from app.core.config import settings
from app.core.logger import get_logger

logger = get_logger(__name__)


@dataclass
class AuthResult:
    success: bool
    requires_2fa: bool = False
    message: str = ""
    storage_state_b64: Optional[str] = None


class AuthService:
    async def authenticate(
        self,
        username: str,
        password: str,
        two_factor_code: Optional[str] = None,
        backup_code: Optional[str] = None,
    ) -> AuthResult:
        playwright = await async_playwright().start()
        browser = await playwright.chromium.launch(
            headless=settings.BROWSER_HEADLESS,
            slow_mo=settings.BROWSER_SLOW_MO,
            args=[
                "--disable-blink-features=AutomationControlled",
                "--no-sandbox",
                "--disable-setuid-sandbox",
                "--disable-dev-shm-usage",
            ],
        )

        try:
            context = await browser.new_context(
                viewport={"width": 1280, "height": 900},
                user_agent=(
                    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                    "AppleWebKit/537.36 (KHTML, like Gecko) "
                    "Chrome/124.0.0.0 Safari/537.36"
                ),
                locale="en-US",
                timezone_id="America/New_York",
            )
            await context.add_init_script(
                "Object.defineProperty(navigator, 'webdriver', {get: () => undefined})"
            )
            page = await context.new_page()

            # ── Step 1: Go directly to the login flow ─────────────────────────
            # Skip the landing page entirely — go straight to the login flow.
            # This avoids the flaky "Sign in" button click on the landing page
            # and gives us a predictable starting point.
            logger.info("Navigating directly to X login flow...")
            await page.goto(
                "https://x.com/i/flow/login",
                wait_until="domcontentloaded",
                timeout=30_000,
            )
            await page.wait_for_timeout(3000)

            # ── Step 2: Wait for username input ──────────────────────────────
            logger.info("Waiting for username input...")
            try:
                await page.wait_for_selector("input", timeout=15_000)
            except PWTimeout:
                return AuthResult(
                    success=False,
                    message=f"Login form did not appear. Current URL: {page.url}",
                )
            await page.wait_for_timeout(1000)

            # ── Step 3: Fill username with human-like typing ──────────────────
            logger.info(f"Filling username: {username}")
            filled = await self._fill_username_human(page, username)
            if not filled:
                return AuthResult(
                    success=False,
                    message=f"Could not find username input. URL: {page.url}",
                )
            await page.wait_for_timeout(800)

            # ── Step 4: Click Next and wait for password field ────────────────
            logger.info("Clicking Next button...")
            await self._advance_login_step(page)

            # Wait generously for password field
            password_appeared = False
            try:
                await page.wait_for_selector(
                    'input[type="password"]',
                    timeout=15_000,
                )
                password_appeared = True
                logger.info("Password field appeared ✅")
            except PWTimeout:
                logger.warning(
                    f"Password field did not appear after first Next click. URL={page.url}"
                )

            # ── Step 5: Handle "confirm username/phone" challenge ─────────────
            if not password_appeared:
                body_text = (await page.inner_text("body")).lower()
                if any(k in body_text for k in [
                    "enter your phone", "enter your username",
                    "confirm your identity", "unusual login",
                ]):
                    logger.info("Identity confirmation screen — re-entering username...")
                    await self._fill_first_visible_text_input(page, username)
                    await page.wait_for_timeout(600)
                    await self._advance_login_step(page)
                    try:
                        await page.wait_for_selector(
                            'input[type="password"]', timeout=12_000
                        )
                        password_appeared = True
                        logger.info("Password field appeared after identity confirmation ✅")
                    except PWTimeout:
                        logger.warning("Still no password field after identity confirmation")

            if not password_appeared:
                url = page.url
                body_snippet = (await page.inner_text("body"))[:300]
                logger.error(
                    f"Password step never appeared. URL={url}\nBody: {body_snippet}"
                )
                return AuthResult(
                    success=False,
                    message=(
                        "Could not advance past the username step. "
                        "X may have changed their login flow or rate-limited this IP."
                    ),
                )

            # ── Step 6: Fill password ─────────────────────────────────────────
            logger.info("Filling password...")
            pwd_filled = await self._fill_password_human(page, password)
            if not pwd_filled:
                return AuthResult(
                    success=False,
                    message="Could not find password input. Login flow may have changed.",
                )
            await page.wait_for_timeout(600)

            # ── Step 7: Submit login ──────────────────────────────────────────
            logger.info("Submitting login form...")
            await self._click_login_submit(page)
            await page.wait_for_timeout(4000)

            # ── Step 8: Check if logged in ────────────────────────────────────
            if await self._is_logged_in(page):
                logger.info("Login successful! ✅")
                return await self._capture_session(context)

            # ── Step 9: Handle 2FA ────────────────────────────────────────────
            body_text = (await page.inner_text("body")).lower()
            needs_2fa = any(k in body_text for k in [
                "verification code", "two-factor", "2fa",
                "authentication code", "backup code", "confirm your identity",
                "check your email", "check your phone",
            ])
            if needs_2fa:
                if not (two_factor_code or backup_code):
                    return AuthResult(
                        success=False,
                        requires_2fa=True,
                        message=(
                            "Two-factor authentication required. "
                            "Please provide your verification code."
                        ),
                    )
                code = two_factor_code or backup_code
                logger.info("Filling 2FA code...")
                await self._fill_first_visible_text_input(page, code)
                await page.wait_for_timeout(400)
                await page.keyboard.press("Enter")
                await page.wait_for_timeout(3500)

                if await self._is_logged_in(page):
                    logger.info("Login successful after 2FA! ✅")
                    return await self._capture_session(context)

            # ── Step 10: Failed ───────────────────────────────────────────────
            url = page.url
            snippet = (await page.inner_text("body"))[:200]
            logger.error(f"Login failed. URL={url}. Page snippet: {snippet}")
            return AuthResult(
                success=False,
                message="Login failed. Please check your username and password.",
            )

        except PWTimeout as exc:
            return AuthResult(success=False, message=f"Login timed out: {exc}")
        except Exception as exc:
            logger.exception("Unexpected error during authentication")
            return AuthResult(success=False, message=f"Login error: {exc}")
        finally:
            await browser.close()
            await playwright.stop()

    # ── Core login helpers ────────────────────────────────────────────────────

    async def _fill_username_human(self, page, value: str) -> bool:
        """
        Fill the username field using human-like character-by-character typing.
        This is more reliable than .fill() because X's React form listens to
        key events, not just input value changes.
        """
        selectors = [
            'input[autocomplete="username"]',
            'input[autocomplete="email"]',
            'input[name="text"]',
            'input[data-testid="ocfEnterTextTextInput"]',
            'input[dir="auto"]',
        ]
        for sel in selectors:
            try:
                loc = page.locator(sel)
                count = await loc.count()
                for i in range(count):
                    el = loc.nth(i)
                    if await el.is_visible(timeout=1000):
                        await el.click()
                        await asyncio.sleep(0.3)
                        # Clear any pre-filled content
                        await page.keyboard.press("Control+a")
                        await asyncio.sleep(0.1)
                        # Type character by character
                        for ch in value:
                            await page.keyboard.type(ch)
                            await asyncio.sleep(random.uniform(0.05, 0.15))
                        logger.info(f"Typed username via selector: {sel}")
                        return True
            except Exception:
                continue

        # Fallback: first visible text input
        return await self._type_into_first_visible_text_input(page, value)

    async def _fill_password_human(self, page, value: str) -> bool:
        """Fill the password field with human-like typing."""
        selectors = [
            'input[type="password"]',
            'input[autocomplete="current-password"]',
            'input[name="password"]',
            'input[data-testid="ocfEnterPasswordPasswordInput"]',
            'input[placeholder*="Password" i]',
        ]
        for sel in selectors:
            try:
                loc = page.locator(sel)
                count = await loc.count()
                for i in range(count):
                    el = loc.nth(i)
                    if await el.is_visible(timeout=1000):
                        await el.click()
                        await asyncio.sleep(0.3)
                        for ch in value:
                            await page.keyboard.type(ch)
                            await asyncio.sleep(random.uniform(0.05, 0.13))
                        logger.info(f"Typed password via selector: {sel}")
                        return True
            except Exception:
                continue

        # Aria-label fallback
        try:
            el = page.get_by_label("Password").first
            if await el.is_visible(timeout=1000):
                await el.click()
                await asyncio.sleep(0.3)
                for ch in value:
                    await page.keyboard.type(ch)
                    await asyncio.sleep(random.uniform(0.05, 0.13))
                logger.info("Typed password via aria-label fallback")
                return True
        except Exception:
            pass

        return False

    async def _advance_login_step(self, page):
        """
        Advance past the current login step (username → password, etc.).

        Priority order:
          1. data-testid="ocfEnterTextNextButton"  ← most reliable for username step
          2. Scan all visible buttons for text "Next" / "Continue"
          3. Press Enter on the focused username input
          4. Global keyboard Enter as absolute last resort
        """

        # Strategy 1 — known data-testid selectors for the Next button
        next_testid_selectors = [
            '[data-testid="ocfEnterTextNextButton"]',
            '[data-testid="LoginForm_Login_Button"]',
            '[data-testid="ocfLoginNextLink"]',
        ]
        for sel in next_testid_selectors:
            try:
                btn = page.locator(sel).first
                if await btn.is_visible(timeout=2000):
                    await btn.scroll_into_view_if_needed()
                    await btn.click()
                    logger.info(f"Clicked Next via data-testid: {sel}")
                    await page.wait_for_timeout(2500)
                    return
            except Exception:
                continue

        # Strategy 2 — scan every <button> for text "Next" / "Continue"
        try:
            buttons = page.locator("button")
            count = await buttons.count()
            for i in range(count):
                btn = buttons.nth(i)
                try:
                    if not await btn.is_visible(timeout=500):
                        continue
                    label = (await btn.inner_text()).strip().lower()
                    if label in ("next", "continue", "next »"):
                        await btn.scroll_into_view_if_needed()
                        await btn.click()
                        logger.info(f"Clicked button with text: '{label}'")
                        await page.wait_for_timeout(2500)
                        return
                except Exception:
                    continue
        except Exception:
            pass

        # Strategy 3 — locate the username input and press Enter on it directly
        input_selectors = [
            'input[autocomplete="username"]',
            'input[autocomplete="email"]',
            'input[name="text"]',
            'input[data-testid="ocfEnterTextTextInput"]',
        ]
        for sel in input_selectors:
            try:
                inp = page.locator(sel).first
                if await inp.is_visible(timeout=1000):
                    await inp.focus()
                    await asyncio.sleep(0.3)
                    await inp.press("Enter")
                    logger.info(f"Pressed Enter on input: {sel}")
                    await page.wait_for_timeout(2500)
                    return
            except Exception:
                continue

        # Strategy 4 — absolute last resort
        logger.warning("All _advance_login_step strategies exhausted — pressing global Enter")
        await page.keyboard.press("Enter")
        await page.wait_for_timeout(2500)

    async def _click_login_submit(self, page):
        """Click the final 'Log in' submit button on the password step."""
        submit_selectors = [
            '[data-testid="LoginForm_Login_Button"]',
            'button[type="submit"]',
        ]
        for sel in submit_selectors:
            try:
                btn = page.locator(sel).first
                if await btn.is_visible(timeout=2000):
                    await btn.scroll_into_view_if_needed()
                    await btn.click()
                    logger.info(f"Clicked login submit via: {sel}")
                    return
            except Exception:
                continue

        # Text-based fallbacks
        for text in ["Log in", "Login", "Sign in"]:
            for role in ["button", "link"]:
                try:
                    el = page.get_by_role(role, name=text).first
                    if await el.is_visible(timeout=1000):
                        await el.click()
                        logger.info(f"Clicked '{text}' ({role})")
                        return
                except Exception:
                    continue

        # Scan all buttons
        try:
            buttons = page.locator("button")
            count = await buttons.count()
            for i in range(count):
                btn = buttons.nth(i)
                try:
                    if not await btn.is_visible(timeout=500):
                        continue
                    label = (await btn.inner_text()).strip().lower()
                    if label in ("log in", "login", "sign in"):
                        await btn.click()
                        logger.info(f"Clicked login button: '{label}'")
                        return
                except Exception:
                    continue
        except Exception:
            pass

        logger.warning("No submit button found — pressing Enter")
        await page.keyboard.press("Enter")

    # ── Generic helpers ───────────────────────────────────────────────────────

    async def _fill_first_visible_text_input(self, page, value: str) -> bool:
        """Generic fallback: fill the first visible non-password input."""
        try:
            loc = page.locator('input:not([type="password"]):not([type="hidden"])')
            count = await loc.count()
            for i in range(count):
                el = loc.nth(i)
                if await el.is_visible(timeout=500):
                    await el.fill(value)
                    return True
        except Exception:
            pass
        return False

    async def _type_into_first_visible_text_input(self, page, value: str) -> bool:
        """Generic fallback: human-type into the first visible non-password input."""
        try:
            loc = page.locator('input:not([type="password"]):not([type="hidden"])')
            count = await loc.count()
            for i in range(count):
                el = loc.nth(i)
                if await el.is_visible(timeout=500):
                    await el.click()
                    await asyncio.sleep(0.3)
                    for ch in value:
                        await page.keyboard.type(ch)
                        await asyncio.sleep(random.uniform(0.05, 0.15))
                    return True
        except Exception:
            pass
        return False

    async def _is_logged_in(self, page) -> bool:
        """Return True if the home feed is visible."""
        try:
            await page.wait_for_selector('[data-testid="primaryColumn"]', timeout=5_000)
            return True
        except Exception:
            pass
        return "home" in page.url

    async def _capture_session(self, context) -> AuthResult:
        """Save Playwright storage state and return it base64-encoded."""
        fd, temp_path = tempfile.mkstemp(suffix=".json")
        os.close(fd)
        try:
            await context.storage_state(path=temp_path)
            with open(temp_path, "rb") as fh:
                encoded = base64.b64encode(fh.read()).decode("utf-8")
            return AuthResult(
                success=True,
                message="Authenticated successfully.",
                storage_state_b64=encoded,
            )
        finally:
            try:
                os.remove(temp_path)
            except OSError:
                pass