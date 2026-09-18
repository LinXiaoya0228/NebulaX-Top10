"""
scripts/capture_day_mode_screenshots.py - Captures all 8 dashboard pages in Day Mode (Light theme).
"""

import time
from playwright.sync_api import sync_playwright

pages_to_test = [
    ("01_control_room", "Control Room"),
    ("02_schedule", "Schedule"),
    ("03_network", "Network"),
    ("04_scenario_comparison", "Scenario Comparison"),
    ("05_operations_sandbox", "Operations Sandbox"),
    ("06_passenger_eclo", "Passenger Impact & ECLO"),
    ("07_decision_brief", "Decision Brief"),
    ("08_validator_downloads", "Validator & Downloads"),
]

def main():
    with sync_playwright() as p:
        browser = p.chromium.launch(
            executable_path="C:/Program Files/Google/Chrome/Application/chrome.exe",
            headless=True,
        )
        context = browser.new_context(viewport={"width": 1440, "height": 900})
        page = context.new_page()
        page.goto("http://localhost:8503", wait_until="networkidle")
        page.wait_for_timeout(3000)

        # Dismiss popup if present
        try:
            btn = page.locator("button:has-text('Don')").first
            if btn.is_visible():
                btn.click()
                page.wait_for_timeout(500)
        except Exception as e:
            pass

        # Close any dialog or modal
        try:
            close_btn = page.locator("[aria-label='Close']").first
            if close_btn.is_visible():
                close_btn.click()
        except Exception:
            pass

        for file_prefix, nav_label in pages_to_test:
            print(f"Navigating to {nav_label}...")
            try:
                nav = page.locator(f"text={nav_label}").first
                if nav.is_visible():
                    nav.click()
                    page.wait_for_timeout(3500)
            except Exception as e:
                print(f"Navigation error for {nav_label}: {e}")

            # Special actions per page
            if file_prefix == "02_schedule":
                try:
                    capsule_radio = page.locator("text='Continuous Gantt (Connected Capsules)'").first
                    if capsule_radio.is_visible():
                        capsule_radio.click()
                        page.wait_for_timeout(2000)
                        page.screenshot(path="artifacts/screenshots_1440/02_schedule_capsules.png")
                        print("  Successfully saved: artifacts/screenshots_1440/02_schedule_capsules.png")
                        # switch back to timeline for the base screenshot
                        tl_radio = page.locator("text='Activity Possession Timeline (by Contract)'").first
                        tl_radio.click()
                        page.wait_for_timeout(1500)
                except Exception as e:
                    print("Error capturing capsules:", e)

            if file_prefix == "08_validator_downloads":
                try:
                    expander = page.locator("text='Reviewer / Judge Live Evaluation Panel'").first
                    if expander.is_visible():
                        expander.click()
                        page.wait_for_timeout(1500)
                except Exception as e:
                    print("Error opening expander:", e)

            out_path = f"artifacts/screenshots_1440/{file_prefix}.png"
            page.screenshot(path=out_path)
            print(f"  Successfully saved: {out_path}")

        context.close()
        browser.close()
    print("\nAll 8 day-mode screenshots updated successfully!")

if __name__ == "__main__":
    main()
