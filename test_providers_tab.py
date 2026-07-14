import asyncio
from playwright.async_api import async_playwright

async def test():
    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True)
        page = await browser.new_page()
        
        # Navigate to the dashboard
        await page.goto("https://essay-own-cradle-novel.2n6.me/forge/", wait_until="networkidle", timeout=30000)
        await page.wait_for_timeout(3000)
        
        # Click the AI Providers tab
        await page.click("text=AI Providers")
        await page.wait_for_timeout(3000)
        
        # Take screenshot of the providers tab
        await page.screenshot(path="/opt/baal-agent/workspace/forge_providers.png", full_page=True)
        print("Providers tab screenshot saved")
        
        # Check what's visible
        text = await page.inner_text("body")
        print(f"\n=== Visible Text (first 800 chars) ===")
        print(text[:800])
        
        await browser.close()

asyncio.run(test())
