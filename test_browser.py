import asyncio
from playwright.async_api import async_playwright

async def test():
    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True)
        page = await browser.new_page()
        
        errors = []
        console_msgs = []
        
        page.on("console", lambda msg: console_msgs.append(f"[{msg.type}] {msg.text}"))
        page.on("pageerror", lambda err: errors.append(str(err)))
        page.on("requestfailed", lambda req: errors.append(f"FAILED: {req.url}"))
        
        print("Navigating to https://essay-own-cradle-novel.2n6.me/forge/...")
        await page.goto("https://essay-own-cradle-novel.2n6.me/forge/", wait_until="networkidle", timeout=30000)
        
        # Wait a bit for React to hydrate and fetch data
        await page.wait_for_timeout(5000)
        
        # Check what's on the page
        content = await page.content()
        
        # Check if "Initializing" is still showing (bad) or if real content loaded (good)
        has_initializing = "Initializing" in content
        has_creator = "Layla" in content
        has_stats = "Followers" in content or "followers" in content
        
        print(f"\n=== Page State ===")
        print(f"Has 'Initializing': {has_initializing}")
        print(f"Has 'Layla' (creator name): {has_creator}")
        print(f"Has stats (Followers): {has_stats}")
        
        # Get visible text
        text = await page.inner_text("body")
        print(f"\n=== Visible Text (first 500 chars) ===")
        print(text[:500])
        
        print(f"\n=== Console Messages ({len(console_msgs)}) ===")
        for msg in console_msgs[:10]:
            print(f"  {msg}")
        
        print(f"\n=== Errors ({len(errors)}) ===")
        for err in errors[:10]:
            print(f"  {err}")
        
        # Take screenshot
        await page.screenshot(path="/tmp/forge_screenshot.png", full_page=True)
        print("\nScreenshot saved to /tmp/forge_screenshot.png")
        
        await browser.close()

asyncio.run(test())
