from __future__ import annotations

import asyncio
import base64
import json
import os
import re
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
            headless=True,
            slow_mo=200,
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

            logger.info("Navigating to X login page...")
            await self._open_login_flow(page)

            logger.info("Waiting for login form inputs to appear...")
            input_ready = await self._wait_for_login_inputs(page)
            if not input_ready:
                return AuthResult(
                    success=False,
                    message=f"Login page did not render any inputs. URL: {page.url}",
                )

            await page.wait_for_timeout(500)

            # --- Step 1: Fill username ---
            logger.info("Filling username...")
            filled = await self._smart_fill(page, username, field_hint="username")
            if not filled:
                return AuthResult(
                    success=False,
                    message=f"Could not find username input. URL: {page.url}",
                )

            await page.wait_for_timeout(500)

            # Click Next
            await self._click_next(page)
            await page.wait_for_timeout(3000)

            # X sometimes shows an extra "Enter phone/username" challenge
            # If a new text input appears that isn't a password, fill it with username again
            challenge = await self._find_visible_input(page, input_type="text")
            if challenge:
                logger.info("Detected intermediate challenge input, filling username again...")
                await challenge.fill(username)
                await page.wait_for_timeout(300)
                await self._click_next(page)
                await page.wait_for_timeout(2500)

            # --- Step 2: Fill password ---
            logger.info("Filling password...")
            pwd_input = await self._find_visible_input(page, input_type="password")
            if not pwd_input:
                # Wait a bit more and retry
                await page.wait_for_timeout(2000)
                pwd_input = await self._find_visible_input(page, input_type="password")

            if not pwd_input:
                return AuthResult(
                    success=False,
                    message="Could not find password input after username step.",
                )

            await pwd_input.fill(password)
            await page.wait_for_timeout(500)

            # Click Log in
            await self._click_login(page)
            await page.wait_for_timeout(4000)

            # --- Check result ---
            if await self._is_logged_in(page):
                return await self._success_result(context)

            # Check for 2FA
            otp_input = await self._find_visible_input(page, input_type="text")
            if otp_input:
                page_text = await page.inner_text("body")
                is_2fa = any(k in page_text.lower() for k in [
                    "verification", "two-factor", "2fa", "confirm your identity",
                    "authentication code", "backup code", "security key"
                ])
                if is_2fa:
                    if not (two_factor_code or backup_code):
                        return AuthResult(
                            success=False,
                            requires_2fa=True,
                            message="Two-factor authentication required. Please provide a verification code.",
                        )
                    code = two_factor_code or backup_code
                    logger.info("Filling 2FA code...")
                    await otp_input.fill(code)
                    await page.wait_for_timeout(400)
                    await page.keyboard.press("Enter")
                    await page.wait_for_timeout(3500)

                    if await self._is_logged_in(page):
                        return await self._success_result(context)

            page_url = page.url
            page_text = (await page.inner_text("body"))[:300]
            logger.error(f"Login failed. URL={page_url}. Page text: {page_text}")
            return AuthResult(
                success=False,
                message="Login did not complete. Check your credentials or 2FA code.",
            )

        except PWTimeout as exc:
            return AuthResult(success=False, message=f"Login timed out: {exc}")
        except Exception as exc:
            logger.exception("Unexpected error during authentication")
            return AuthResult(success=False, message=f"Login failed: {exc}")
        finally:
            await browser.close()
            await playwright.stop()

    async def _find_visible_input(self, page, input_type: str = "text"):
        """Find the first visible input of a given type."""
        selector = f'input[type="{input_type}"]'
        try:
            locator = page.locator(selector)
            count = await locator.count()
            for i in range(count):
                el = locator.nth(i)
                if await el.is_visible():
                    return el
        except Exception:
            pass

        # Fallback for type="text": also try inputs without explicit type
        if input_type == "text":
            try:
                locator = page.locator('input:not([type="password"]):not([type="hidden"])')
                count = await locator.count()
                for i in range(count):
                    el = locator.nth(i)
                    if await el.is_visible():
                        return el
            except Exception:
                pass
        return None

    async def _open_login_flow(self, page) -> None:
        """Open the most reliable X login flow and click through any landing layer."""
        candidates = [
            "https://mobile.twitter.com/i/flow/login",
            "https://mobile.twitter.com/login",
            f"{settings.TWITTER_BASE_URL}/i/flow/login",
            "https://twitter.com/i/flow/login",
            f"{settings.TWITTER_BASE_URL}/login",
            "https://twitter.com/login",
        ]

        for url in candidates:
            try:
                logger.info(f"Opening login URL: {url}")
                await page.goto(url, wait_until="domcontentloaded", timeout=30_000)
                await page.wait_for_load_state("networkidle")
                await page.wait_for_timeout(1200)

                # If X is showing a landing page or cookie dialog, click through it.
                await self._dismiss_overlays(page)
                await self._click_any_text(page, ["Sign in", "Log in", "Accept all cookies", "Accept"])
                await page.wait_for_timeout(1200)

                return
            except Exception as exc:
                logger.warning(f"Login URL failed ({url}): {exc}")

        raise RuntimeError("Could not open a usable X login page.")

    async def _wait_for_login_inputs(self, page) -> bool:
        """Wait for username/email and password inputs to appear, with retries."""
        for _ in range(4):
            inputs = page.locator(
                'input, textarea, [contenteditable="true"]'
            )
            try:
                count = await inputs.count()
                visible_count = 0
                for i in range(count):
                    element = inputs.nth(i)
                    if await element.is_visible():
                        visible_count += 1
                if visible_count:
                    return True
            except Exception:
                pass

            await self._dismiss_overlays(page)
            await self._click_any_text(page, ["Sign in", "Log in", "Next"])
            await page.wait_for_timeout(1500)

        return False

    async def _smart_fill(self, page, value: str, field_hint: str = "") -> bool:
        """Fill the first visible text input on the page."""
        # Ordered list of selectors to try
        selectors = [
            'input[autocomplete="username"]',
            'input[autocomplete="email"]',
            'input[name="text"]',
            'input[dir="auto"]',
            'input[data-testid="ocfEnterTextTextInput"]',
        ]

        for sel in selectors:
            try:
                loc = page.locator(sel)
                count = await loc.count()
                for i in range(count):
                    el = loc.nth(i)
                    if await el.is_visible():
                        await el.fill(value)
                        logger.info(f"Filled {field_hint} using selector: {sel}")
                        return True
            except Exception:
                continue

        # Last resort: first visible text input
        el = await self._find_visible_input(page, input_type="text")
        if el:
            await el.fill(value)
            logger.info(f"Filled {field_hint} using generic text input fallback")
            return True

        return False

    async def _click_any_text(self, page, labels) -> bool:
        for label in labels:
            try:
                buttons = [
                    page.get_by_role("button", name=re.compile(re.escape(label), re.I)),
                    page.get_by_text(label, exact=False),
                    page.locator(f'button:has-text("{label}")'),
                    page.locator(f'[role="button"]:has-text("{label}")'),
                ]
                for locator in buttons:
                    try:
                        if await locator.count():
                            await locator.first.click()
                            return True
                    except Exception:
                        continue
            except Exception:
                continue
        return False

    async def _dismiss_overlays(self, page) -> None:
        """Best-effort dismissal of cookie/landing overlays that block inputs."""
        overlay_labels = [
            "Accept all cookies",
            "Accept cookies",
            "Accept",
            "Close",
            "Not now",
        ]
        await self._click_any_text(page, overlay_labels)

    async def _click_next(self, page):
        """Click the Next button using multiple strategies."""
        strategies = [
            lambda: page.locator('button:has-text("Next")').first.click(),
            lambda: page.get_by_role("button", name="Next").click(),
            lambda: page.locator('[data-testid="LoginForm_Login_Button"]').click(),
            lambda: page.keyboard.press("Enter"),
        ]
        for fn in strategies:
            try:
                await fn()
                return
            except Exception:
                continue

    async def _click_login(self, page):
        """Click the Log in button."""
        strategies = [
            lambda: page.locator('[data-testid="LoginForm_Login_Button"]').click(),
            lambda: page.locator('button:has-text("Log in")').first.click(),
            lambda: page.get_by_role("button", name="Log in").click(),
            lambda: page.keyboard.press("Enter"),
        ]
        for fn in strategies:
            try:
                await fn()
                return
            except Exception:
                continue

    async def _is_logged_in(self, page) -> bool:
        """Check if we're on an authenticated page."""
        try:
            await page.wait_for_selector('[data-testid="primaryColumn"]', timeout=5_000)
            return True
        except Exception:
            pass
        # Secondary check: home URL
        if page.url in (
            "https://x.com/home",
            "https://twitter.com/home",
            "https://x.com/",
        ):
            return True
        return False

    async def _success_result(self, context) -> AuthResult:
        fd, temp_path = tempfile.mkstemp(suffix=".json")
        os.close(fd)
        try:
            await context.storage_state(path=temp_path)
            with open(temp_path, "rb") as handle:
                encoded = base64.b64encode(handle.read()).decode("utf-8")
            logger.info("Authentication succeeded and storage state captured")
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