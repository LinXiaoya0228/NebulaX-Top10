"""
scripts/verify_ui_screenshots.py - Playwright visual audit across 1440x900 and 1920x1080 viewports.
"""

import os
import subprocess
import time
import urllib.request
from playwright.sync_api import sync_playwright

CHROME_BIN = "/Applications/Google Chrome.app/Contents/MacOS/Google Chrome"
PORT = 8505
BASE_URL = f"http://localhost:{PORT}"


def wait_for_server(url, timeout=30):
    start = time.time()
    while time.time() - start < timeout:
        try:
            with urllib.request.urlopen(f"{url}/_stcore/health") as resp:
                if resp.status == 200:
                    return True
        except Exception:
            time.sleep(1)
    return False


def run_visual_audit():
    print(f"Starting Streamlit server on port {PORT}...")
    proc = subprocess.Popen(
        [
            ".venv/bin/streamlit",
            "run",
            "app.py",
            f"--server.port={PORT}",
            "--server.headless=true",
            "--browser.gatherUsageStats=false",
        ],
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
    )

    try:
        print("Waiting for Streamlit server health check...")
        if not wait_for_server(BASE_URL, timeout=35):
            raise RuntimeError("Streamlit server failed to start within timeout.")
        print("Streamlit server is ready!")

        viewports = [
            ("1440", {"width": 1440, "height": 900}),
            ("1920", {"width": 1920, "height": 1080}),
        ]

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

        with sync_playwright() as p:
            browser = p.chromium.launch(executable_path=CHROME_BIN, headless=True)

            for vp_name, vp_size in viewports:
                print(f"\n--- Testing Viewport {vp_name} ({vp_size['width']}x{vp_size['height']}) ---")
                context = browser.new_context(viewport=vp_size)
                page = context.new_page()

                # Open Base URL
                page.goto(BASE_URL, wait_until="networkidle")
                page.wait_for_timeout(3000)

                for file_prefix, nav_label in pages_to_test:
                    print(f"Navigating to {nav_label}...")
                    # Click on sidebar navigation item
                    try:
                        # Find navigation link by text
                        nav_link = page.locator(f"text={nav_label}").first
                        if nav_link.is_visible():
                            nav_link.click()
                            page.wait_for_timeout(2500)
                    except Exception as e:
                        print(f"Warning clicking {nav_label}: {e}")

                    # Check for horizontal scroll overflow
                    has_h_scroll = page.evaluate("() => document.documentElement.scrollWidth > window.innerWidth")
                    scroll_diff = page.evaluate("() => document.documentElement.scrollWidth - window.innerWidth")
                    print(f"  Page-level horizontal overflow: {has_h_scroll} (diff: {scroll_diff}px)")

                    # Save screenshot
                    out_path = f"artifacts/screenshots_{vp_name}/{file_prefix}.png"
                    page.screenshot(path=out_path, full_page=False)
                    print(f"  Captured: {out_path}")

                context.close()

            browser.close()
        print("\nAll visual screenshots successfully captured and audited!")

    finally:
        print("Stopping Streamlit server...")
        proc.terminate()
        proc.wait(timeout=5)


if __name__ == "__main__":
    run_visual_audit()

