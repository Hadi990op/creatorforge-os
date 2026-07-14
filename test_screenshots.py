import asyncio
from playwright.async_api import async_playwright

async def test():
    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True)
        page = await browser.new_page(viewport={"width": 1280, "height": 900})
        
        await page.goto("https://essay-own-cradle-novel.2n6.me/forge/", wait_until="networkidle", timeout=30000)
        await page.wait_for_timeout(5000)
        
        # Take screenshot of the overview
        await page.screenshot(path="/opt/baal-agent/workspace/forge_overview.png", full_page=True)
        print("Overview screenshot saved")
        
        # Click on Deals tab
        await page.click("text=Deals")
        await page.wait_for_timeout(2000)
        await page.screenshot(path="/opt/baal-agent/workspace/forge_deals.png", full_page=True)
        print("Deals screenshot saved")
        
        # Click on Agents tab
        await page.click("text=Agents")
        await page.wait_for_timeout(2000)
        await page.screenshot(path="/opt/baal-agent/workspace/forge_agents.png", full_page=True)
        print("Agents screenshot saved")
        
        # Check for errors
        text = await page.inner_text("body")
        print(f"\n=== Agents tab text (first 600 chars) ===")
        print(text[:600])
        
        await browser.close()

asyncio.run(test())
