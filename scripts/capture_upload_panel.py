"""
scripts/capture_upload_panel.py - Captures Page 8 with the Reviewer Upload panel open,
and captures the sidebar with the custom file uploader visible.
"""

from playwright.sync_api import sync_playwright

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

        # Go to Page 8: Validator & Downloads
        nav = page.locator("text='Validator & Downloads'").first
        if nav.is_visible():
            nav.click()
            page.wait_for_timeout(3000)

        # Click the expander summary
        try:
            summary = page.locator("summary:has-text('Reviewer')").first
            if summary.is_visible():
                summary.click()
                page.wait_for_timeout(2000)
                page.screenshot(path="artifacts/screenshots_1440/08_validator_downloads.png")
                print("Captured 08_validator_downloads.png with expander open!")
        except Exception as e:
            print("Expander error:", e)

        # Switch to sidebar upload option
        try:
            radio = page.locator("text='Upload Custom Instance'").first
            if radio.is_visible():
                radio.click()
                page.wait_for_timeout(2500)
                page.screenshot(path="artifacts/screenshots_1440/08_reviewer_upload_sidebar.png")
                print("Captured 08_reviewer_upload_sidebar.png!")
        except Exception as e:
            print("Sidebar upload error:", e)

        context.close()
        browser.close()

if __name__ == "__main__":
    main()

