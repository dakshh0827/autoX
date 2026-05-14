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
            slow_mo=settings.BROWSER_SLOW_MO,
            args=[
                "--disable-blink-features=AutomationControlled",
                "--no-sandbox",
                "--disable-setuid-sandbox",
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

            await page.goto(f"{settings.TWITTER_BASE_URL}/i/flow/login", wait_until="domcontentloaded")
            await page.wait_for_load_state("networkidle")
            await page.wait_for_timeout(1000)

            await self._fill_first_visible(page, [
                'input[autocomplete="username"]',
                'input[autocomplete="email"]',
                'input[placeholder*="phone"]',
                'input[placeholder*="username"]',
                'input[aria-label*="phone"]',
                'input[aria-label*="email"]',
                'input[name="text"]',
                'input[dir="auto"]',
                'input[type="text"]',
                'input',
            ], username)
            await self._click_text_or_selector(page, "Next", 'button[type="button"]')
            await page.wait_for_load_state("networkidle")
            await page.wait_for_timeout(1000)

            await self._fill_first_visible(page, [
                'input[type="password"]',
                'input[autocomplete="current-password"]',
                'input[name="password"]',
                'input[aria-label*="password"]',
            ], password)
            await self._click_text_or_selector(page, "Log in", 'button[data-testid="LoginForm_Login_Button"]')
            await page.wait_for_load_state("networkidle")
            await page.wait_for_timeout(2000)

            if await self._is_logged_in(page):
                return await self._success_result(context, browser, playwright)

            otp_selector = await self._find_2fa_input(page)
            if otp_selector:
                if not (two_factor_code or backup_code):
                    return AuthResult(
                        success=False,
                        requires_2fa=True,
                        message="Two-factor authentication required. Please provide a verification code or backup code.",
                    )
                code = backup_code or two_factor_code
                await page.fill(otp_selector, code)
                await page.keyboard.press("Enter")
                await page.wait_for_timeout(2500)

                if await self._is_logged_in(page):
                    return await self._success_result(context, browser, playwright)

            return AuthResult(
                success=False,
                message="Login did not complete. Check credentials, 2FA code, or X/Twitter challenge prompts.",
            )
        except PWTimeout as exc:
            return AuthResult(success=False, message=f"Login timed out: {exc}")
        except Exception as exc:
            return AuthResult(success=False, message=f"Login failed: {exc}")
        finally:
            await browser.close()
            await playwright.stop()

    async def _success_result(self, context, browser, playwright) -> AuthResult:
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

    async def _is_logged_in(self, page) -> bool:
        try:
            await page.wait_for_selector('[data-testid="primaryColumn"]', timeout=4_000)
            return True
        except Exception:
            return False

    async def _find_2fa_input(self, page) -> Optional[str]:
        selectors = [
            'input[autocomplete="one-time-code"]',
            'input[data-testid="ocfEnterTextTextInput"]',
            'input[type="text"]',
        ]
        for selector in selectors:
            try:
                loc = page.locator(selector)
                count = await loc.count()
                for index in range(count):
                    element = loc.nth(index)
                    if await element.is_visible():
                        return selector
            except Exception:
                continue
        return None

    async def _fill_first_visible(self, page, selectors, value: str):
        for selector in selectors:
            try:
                loc = page.locator(selector)
                count = await loc.count()
                for index in range(count):
                    element = loc.nth(index)
                    if await element.is_visible():
                        await element.fill(value)
                        return
            except Exception:
                continue

        # Last-resort fallback: fill the first visible textbox/input on the page.
        try:
            visible_inputs = page.locator('input, textarea, [contenteditable="true"]')
            count = await visible_inputs.count()
            for index in range(count):
                element = visible_inputs.nth(index)
                if await element.is_visible():
                    try:
                        await element.fill(value)
                    except Exception:
                        await element.click()
                        await page.keyboard.type(value)
                    return
        except Exception:
            pass

        raise RuntimeError(
            f"Could not find input field for selectors: {selectors}. Current URL: {page.url}"
        )

    async def _click_text_or_selector(self, page, text: str, selector: str):
        try:
            button = page.locator(selector)
            if await button.count():
                await button.first.click()
                return
        except Exception:
            pass

        try:
            await page.get_by_text(text, exact=False).first.click()
        except Exception:
            raise RuntimeError(f"Could not click button '{text}' or selector '{selector}'")
