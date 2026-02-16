import asyncio
import json
from playwright.async_api import async_playwright

# SADECE ÇALIŞAN PROXYLER (Loglardan aldıklarımız)
PROXY_LIST = [
    "http://212.175.88.208:8080",   # Türk Telekom
    "http://212.252.39.103:8080"    # Superonline
]

async def run_scraper(proxy_url):
    print(f"\n🔌 Proxy Başlatılıyor: {proxy_url}")
    
    async with async_playwright() as p:
        try:
            browser = await p.chromium.launch(
                headless=True, # Arka planda çalışır
                proxy={"server": proxy_url}
            )
            
            context = await browser.new_context(
                viewport={"width": 1920, "height": 1080},
                user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/121.0.0.0 Safari/537.36",
                locale="tr-TR",
                timezone_id="Europe/Istanbul"
            )
            
            # 60 Saniye sabır süresi (Proxy yavaş olduğu için)
            context.set_default_timeout(60000)

            # --- 1. MANUEL STEALTH (Robot değiliz) ---
            await context.add_init_script("Object.defineProperty(navigator, 'webdriver', {get: () => undefined})")

            # --- 2. REQUEST INTERCEPTION (TR Zorlama) ---
            # Epic Games'e giden istekleri yakalayıp "Ben Türkiye'deyim" diye değiştiriyoruz.
            async def handle_routes(route, request):
                if request.method == "POST" and "graphql" in request.url:
                    try:
                        post_data = json.loads(request.post_data)
                        variables = post_data.get("variables", {})
                        if "country" in variables:
                            variables["country"] = "TR"
                            variables["locale"] = "tr"
                            variables["countryCode"] = "TR"
                            variables["currencyCode"] = "TRY"
                            post_data["variables"] = variables
                            await route.continue_(post_data=json.dumps(post_data))
                            return
                    except:
                        pass
                await route.continue_()

            await context.route("**/*", handle_routes)

            page = await context.new_page()

            # --- 3. PAKET BEKLEYİCİSİ (EN ÖNEMLİ KISIM) ---
            # Arka planda "graphql" içeren ve başarılı (200) olan yanıtı bekleyen bir "Kapan" kuruyoruz.
            # Bu kod, veri gelmeden aşağıya inmez!
            async with page.expect_response(lambda response: "graphql" in response.url and response.status == 200, timeout=60000) as response_info:
                
                print("⏳ Siteye gidiliyor ve veri paketi bekleniyor...")
                # Siteye gitmek isteği tetikler
                await page.goto("https://store.epicgames.com/tr/browse?sortBy=releaseDate&sortDir=DESC&category=Game&count=40", wait_until="domcontentloaded")
            
            # Buraya geldiyse paket yakalanmıştır!
            response = await response_info.value
            print(f"📦 Paket Yakalandı! (URL: {response.url[-30:]})")
            
            json_data = await response.json()
            
            # --- 4. VERİYİ AYIKLAMA ---
            elements = []
            if "data" in json_data and "Catalog" in json_data["data"]:
                cat = json_data["data"]["Catalog"]
                if "searchStore" in cat:
                    elements = cat["searchStore"]["elements"]
                elif "catalogOffers" in cat:
                    elements = cat["catalogOffers"]["elements"]

            if elements:
                print(f"✅ JSON İÇİNDEN {len(elements)} OYUN ÇIKARILDI!")
                
                clean_list = []
                for game in elements:
                    title = game.get("title", "Bilinmiyor")
                    price_info = game.get("price", {}).get("totalPrice", {}).get("fmtPrice", {})
                    original_price = price_info.get("originalPrice", "0")
                    discount_price = price_info.get("discountPrice", "0")
                    
                    print(f"   🕹️ {title} -> {original_price}")
                    
                    clean_list.append({
                        "title": title,
                        "original_price": original_price,
                        "discount_price": discount_price
                    })

                # Dosyaya temiz kaydet
                with open("epic_packet_data.json", "w", encoding="utf-8") as f:
                    json.dump(clean_list, f, ensure_ascii=False, indent=4)
                print("💾 Veriler 'epic_packet_data.json' dosyasına kaydedildi.")
                
                await browser.close()
                return True
            else:
                print("⚠️ Paket geldi ama içi boş veya yapı farklı.")
                
            await browser.close()
            return False

        except Exception as e:
            print(f"❌ Hata: {str(e)[:100]}")
            return False

async def main():
    for proxy in PROXY_LIST:
        if await run_scraper(proxy):
            break
    else:
        print("\n😔 İki proxy ile de paket yakalanamadı.")

if __name__ == "__main__":
    asyncio.run(main())
