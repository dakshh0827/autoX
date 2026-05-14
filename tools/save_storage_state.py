import asyncio
import os

from app.services.twitter_browser import TwitterBrowser


async def main():
    # Ensure headful mode so the browser UI is visible for login
    os.environ.setdefault("BROWSER_HEADLESS", "false")

    browser = TwitterBrowser()
    try:
        await browser.start()
        # Open login page and wait until user completes login
        await browser.navigate_to_login()
        # Save storage state to file
        out_path = "storage_state.json"
        await browser.save_storage_state(out_path)
        print(f"Saved storage state to {out_path}")
    finally:
        await browser.close()


if __name__ == "__main__":
    asyncio.run(main())
