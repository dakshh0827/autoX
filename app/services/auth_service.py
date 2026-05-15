from __future__ import annotations

import asyncio
import base64
import json
import os
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
            slow_mo=100,
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

            # ── Step 1: Go to x.com landing page ─────────────────────────────
            logger.info("Navigating to x.com...")
            await page.goto("https://x.com", wait_until="domcontentloaded", timeout=30_000)
            await page.wait_for_timeout(3000)

            # ── Step 2: Click "Sign in" button on the landing page ────────────
            logger.info("Looking for Sign in button on landing page...")
            signed_in = await self._click_sign_in_button(page)
            if not signed_in:
                # Fallback: go directly to the login flow URL
                logger.info("Sign in button not found, navigating directly to login flow...")
                await page.goto(
                    "https://x.com/i/flow/login",
                    wait_until="domcontentloaded",
                    timeout=30_000,
                )
            await page.wait_for_timeout(3000)

            # ── Step 3: Wait for username input to appear ─────────────────────
            logger.info("Waiting for username input...")
            try:
                await page.wait_for_selector("input", timeout=15_000)
            except PWTimeout:
                return AuthResult(
                    success=False,
                    message=f"Login form did not appear. Current URL: {page.url}",
                )
            await page.wait_for_timeout(1000)

            # ── Step 4: Fill username ─────────────────────────────────────────
            logger.info(f"Filling username: {username}")
            filled = await self._fill_username(page, username)
            if not filled:
                return AuthResult(
                    success=False,
                    message=f"Could not find username input. URL: {page.url}",
                )
            await page.wait_for_timeout(600)

            # Click Next
            await self._click_button_by_text(page, ["Next"])
            await page.wait_for_timeout(3000)

            # ── Step 5: Handle possible "confirm username" challenge ───────────
            # X sometimes shows an extra screen asking to confirm phone/username
            body_text = (await page.inner_text("body")).lower()
            if any(k in body_text for k in ["enter your phone", "enter your username", "confirm your identity"]):
                logger.info("Detected identity confirmation screen, re-entering username...")
                await self._fill_first_visible_text_input(page, username)
                await page.wait_for_timeout(400)
                await self._click_button_by_text(page, ["Next"])
                await page.wait_for_timeout(2500)

            # ── Step 6: Fill password ─────────────────────────────────────────
            logger.info("Filling password...")
            pwd_filled = await self._fill_password(page, password)
            if not pwd_filled:
                await page.wait_for_timeout(2000)
                pwd_filled = await self._fill_password(page, password)
            if not pwd_filled:
                return AuthResult(
                    success=False,
                    message="Could not find password input. Login flow may have changed.",
                )
            await page.wait_for_timeout(600)

            # Click Log in
            await self._click_button_by_text(page, ["Log in", "Login"])
            await page.wait_for_timeout(4000)

            # ── Step 7: Check if logged in ────────────────────────────────────
            if await self._is_logged_in(page):
                logger.info("Login successful!")
                return await self._capture_session(context)

            # ── Step 8: Handle 2FA if needed ──────────────────────────────────
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
                        message="Two-factor authentication required. Please provide your verification code.",
                    )
                code = two_factor_code or backup_code
                logger.info("Filling 2FA code...")
                await self._fill_first_visible_text_input(page, code)
                await page.wait_for_timeout(400)
                await page.keyboard.press("Enter")
                await page.wait_for_timeout(3500)

                if await self._is_logged_in(page):
                    logger.info("Login successful after 2FA!")
                    return await self._capture_session(context)

            # ── Step 9: Failed ────────────────────────────────────────────────
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

    # ── Helpers ───────────────────────────────────────────────────────────────

    async def _click_sign_in_button(self, page) -> bool:
        """
        Click the Sign in button on the X.com landing page.
        Tries multiple strategies since the landing page has several CTAs.
        """
        strategies = [
            # data-testid used by X for the sign-in link
            'a[data-testid="loginButton"]',
            'a[href="/login"]',
            '[data-testid="login"]',
        ]
        for sel in strategies:
            try:
                el = page.locator(sel).first
                if await el.is_visible():
                    await el.click()
                    logger.info(f"Clicked sign in via selector: {sel}")
                    return True
            except Exception:
                continue

        # Text-based fallback — find any link/button that says "Sign in"
        for text in ["Sign in", "Log in", "Sign In"]:
            try:
                el = page.get_by_role("link", name=text).first
                if await el.is_visible():
                    await el.click()
                    logger.info(f"Clicked sign in via text: {text}")
                    return True
            except Exception:
                pass
            try:
                el = page.get_by_role("button", name=text).first
                if await el.is_visible():
                    await el.click()
                    logger.info(f"Clicked sign in button via text: {text}")
                    return True
            except Exception:
                pass

        return False

    async def _fill_username(self, page, value: str) -> bool:
        """Fill the username/email field."""
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
                    if await el.is_visible():
                        await el.fill(value)
                        logger.info(f"Filled username with selector: {sel}")
                        return True
            except Exception:
                continue

        return await self._fill_first_visible_text_input(page, value)

    async def _fill_password(self, page, value: str) -> bool:
        """Fill the password field."""
        selectors = [
            'input[type="password"]',
            'input[autocomplete="current-password"]',
            'input[name="password"]',
        ]
        for sel in selectors:
            try:
                loc = page.locator(sel)
                count = await loc.count()
                for i in range(count):
                    el = loc.nth(i)
                    if await el.is_visible():
                        await el.fill(value)
                        logger.info(f"Filled password with selector: {sel}")
                        return True
            except Exception:
                continue
        return False

    async def _fill_first_visible_text_input(self, page, value: str) -> bool:
        """Generic fallback: fill the first visible non-password input."""
        try:
            loc = page.locator('input:not([type="password"]):not([type="hidden"])')
            count = await loc.count()
            for i in range(count):
                el = loc.nth(i)
                if await el.is_visible():
                    await el.fill(value)
                    return True
        except Exception:
            pass
        return False

    async def _click_button_by_text(self, page, texts: list[str]):
        """Click the first visible button/link matching any of the given texts."""
        for text in texts:
            for role in ["button", "link"]:
                try:
                    el = page.get_by_role(role, name=text).first
                    if await el.is_visible():
                        await el.click()
                        logger.info(f"Clicked '{text}' ({role})")
                        return
                except Exception:
                    continue
            # Fallback: locator with has-text
            try:
                el = page.locator(f'button:has-text("{text}")').first
                if await el.is_visible():
                    await el.click()
                    logger.info(f"Clicked button with has-text: {text}")
                    return
            except Exception:
                continue
        # Last resort
        await page.keyboard.press("Enter")

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