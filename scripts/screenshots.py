"""Headless screenshots of the running app (pip install playwright && playwright install chromium).
Usage: python scripts/screenshots.py [http://localhost:5173]"""
import sys
from pathlib import Path
from playwright.sync_api import sync_playwright

URL = sys.argv[1] if len(sys.argv) > 1 else "http://localhost:5173"
OUT = Path(__file__).resolve().parent.parent / "screenshots"
OUT.mkdir(exist_ok=True)

with sync_playwright() as p:
    b = p.chromium.launch()
    pg = b.new_page(viewport={"width": 1440, "height": 900}, device_scale_factor=1)
    pg.goto(URL)
    pg.wait_for_selector(".landing-title")
    pg.wait_for_timeout(600)
    pg.screenshot(path=str(OUT / "01-landing.png"))

    pg.click("text=refrigerators")
    pg.wait_for_selector(".stage.running")
    pg.wait_for_timeout(1300)
    pg.screenshot(path=str(OUT / "02-loading.png"))

    for i, (topic, slug) in enumerate([("refrigerators", "refrigerators"), ("standing desks", "standing-desks"),
                                       ("e-bikes", "e-bikes")]):
        pg.goto(f"{URL}/?q={topic}")
        pg.wait_for_selector(".headline", timeout=15000)
        pg.wait_for_timeout(900)
        pg.screenshot(path=str(OUT / f"{3 + i:02d}-dashboard-{slug}.png"), full_page=True)

    # open a category panel (click the top bar) on e-bikes, then a dig-deeper answer on refrigerators
    pg.locator(".recharts-bar-rectangle").first.click()
    pg.wait_for_selector(".post")
    pg.wait_for_timeout(500)
    pg.screenshot(path=str(OUT / "06-category-panel-e-bikes.png"))
    pg.keyboard.press("Escape")

    pg.goto(f"{URL}/?q=refrigerators")
    pg.wait_for_selector(".headline", timeout=15000)
    pg.locator(".dig-card .chip").nth(1).click()
    pg.wait_for_selector(".dig-answer p")
    pg.wait_for_timeout(400)
    pg.locator(".dig-card").scroll_into_view_if_needed()
    pg.screenshot(path=str(OUT / "07-dig-deeper-refrigerators.png"))
    b.close()
print("saved to", OUT)
