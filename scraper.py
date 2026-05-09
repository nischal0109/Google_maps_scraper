import asyncio
import csv
import re
from playwright.async_api import async_playwright

FEED_SELECTOR = 'div[role="feed"]'


async def scroll_feed(page):
    last_count = 0
    for i in range(15):
        count = await page.evaluate("""() => {
            const feed = document.querySelector('div[role="feed"]');
            if (!feed) return -1;
            feed.scrollTop = feed.scrollHeight;
            return feed.querySelectorAll('a.hfpxzc').length;
        }""")
        if count < 0:
            return 0
        print(f"  scroll {i+1}: {count} results loaded")
        if count == last_count and count > 0:
            break
        last_count = count
        await page.wait_for_timeout(1500)
    return last_count


async def extract_details(page):
    raw = await page.evaluate("""() => {
        const d = {};
        const h1 = document.querySelector('h1');
        if (h1) d.name = h1.innerText.trim();
        const cat = document.querySelector('button[jsaction*="category"]');
        if (cat) d.category = cat.innerText.trim();
        const addr = document.querySelector('[data-item-id="address"]');
        if (addr) d.address = addr.innerText.trim();
        const phone = document.querySelector('[data-item-id*="phone"]');
        if (phone) d.phone = phone.innerText.trim();
        const web = document.querySelector('a[data-item-id="authority"]');
        if (web) d.website = web.href;
        for (const a of document.querySelectorAll('a[href*="facebook.com"], a[href*="instagram.com"], a[href*="whatsapp.com"], a[href^="mailto:"]')) {
            const h = a.href;
            if (h.includes('facebook.com') && !d.facebook) d.facebook = h;
            if (h.includes('instagram.com') && !d.instagram) d.instagram = h;
            if (h.includes('whatsapp.com') && !d.whatsapp) d.whatsapp = h;
            if (h.startsWith('mailto:') && !d.email) d.email = h.replace('mailto:', '');
        }
        return d;
    }""")

    m = re.search(r'@(-?\d+\.\d+),(-?\d+\.\d+)', page.url)
    if m:
        raw['latitude'] = m.group(1)
        raw['longitude'] = m.group(2)

    raw['source_url'] = page.url
    return raw


async def main():
    keyword = "parlour"
    search_url = f"https://www.google.com/maps/search/{keyword}"

    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=False)
        page = await browser.new_page()
        await page.goto(search_url, wait_until="domcontentloaded")
        await page.wait_for_timeout(3000)

        total = await scroll_feed(page)
        print(f"Found {total} results after scrolling")

        if total == 0:
            print("No results found")
            await browser.close()
            return

        feed = await page.query_selector(FEED_SELECTOR)
        links = await feed.query_selector_all('a.hfpxzc')
        all_details = []

        for i, link in enumerate(links):
            print(f"\n--- Result {i + 1} / {len(links)} ---")
            try:
                name_from_list = await link.evaluate("""el => {
                    const article = el.closest('div[role="article"]');
                    return article ? article.getAttribute('aria-label') : '';
                }""")
                print(f"  name: {name_from_list}")
                
                await page.wait_for_timeout(1000)
                await link.click()
                await page.wait_for_timeout(3000)
                details = await extract_details(page)
                details["name"] = name_from_list
                all_details.append(details)
                for k, v in details.items():
                    print(f"  {k}: {v}")

                close_btn = await page.query_selector('button[aria-label="Close"]')
                if close_btn:
                    await close_btn.click()
                    await page.wait_for_timeout(1000)
            except Exception as e:
                print(f"  Error: {e}")

        print(f"\nExtracted {len(all_details)} results total")
        
        fields = ["name", "category", "address", "phone", "website", "email", "facebook", "instagram", "whatsapp", "latitude", "longitude", "source_url"]
        with open("output.csv", "w", newline="", encoding="utf-8") as f:
            w = csv.DictWriter(f, fieldnames=fields, extrasaction="ignore")
            w.writeheader()
            w.writerows(all_details)
        print("Saved to output.csv")

        await page.wait_for_timeout(3000)
        await browser.close()


if __name__ == "__main__":
    asyncio.run(main())
