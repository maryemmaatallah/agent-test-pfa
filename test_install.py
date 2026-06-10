from playwright.sync_api import sync_playwright

with sync_playwright() as p:
    browser = p.chromium.launch(headless=False)  # headless=False = on voit le navigateur
    page = browser.new_page()
    page.goto("https://www.google.com")
    print("✅ Playwright fonctionne ! Titre de la page :", page.title())
    browser.close()