import asyncio
import json
from playwright.async_api import async_playwright

# --- SENİN VERDİĞİN LİSTEDEN TEMİZLENMİŞ PROXYLER ---
PROXY_LIST = [
    "http://185.181.208.88:3128",
    "http://176.236.227.106:8080",
    "http://185.103.202.35:8443",
    "http://149.86.140.214:8080",
    "http://194.124.36.14:8080",
    "http://164.138.207.81:8080",
    "http://149.86.139.166:8085",
    "http://213.74.163.181:8080",
    "http://188.132.221.188:8080",
    "http://176.88.191.254:8080",
    "http://212.175.88.208:8080",
    "http://139.28.48.39:8080",
    "http://185.80.21.92:8080",
    "http://103.231.75.209:3128",
    "http://212.252.39.103:8080",
    "http://176.236.46.146:80",
    "http://95.70.235.241:8080",
    "http://212.174.242.114:8080",
    "http://185.181.208.190:3128",
    "http://31.40.204.250:80",
    "socks5://185.86.5.162:8975"
]

# --- MOCK VERİLERİ ---
TR_COUNTRY_INFO = {"data": {"Catalog": {"countryData": {"defaultCurrency": "TRY","paymentCurrency": "TRY","currencySymbolPlacement": "LEFT"}}}}
TR_CURRENCY_INFO = {"data": {"Catalog": {"currency": {"decimals": 2,"code": "TRY","symbol": "₺"}}}}

async def run_scraper(proxy_url):
    async with async_playwright() as p:
        print(f"\n🔌 Proxy deneniyor: {proxy_url}")
        
        try:
            # Tarayıcıyı başlat
            browser = await p.chromium.launch(
                headless=True, 
                proxy={"server": proxy_url}
            )
            
            # Context oluştur
            context = await browser.new_context(
                viewport={"width": 1920, "height": 1080},
                locale="tr-TR",
                timezone_id="Europe/Istanbul",
                user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/121.0.0.0 Safari/537.36"
            )
            
            # Timeout ayarları (20 saniye yeterli, ölü proxy'de çok beklemeyelim)
            context.set_default_navigation_timeout(20000)
            context.set_default_timeout(20000)
            
            # --- KRİTİK NOKTA: MANUEL STEALTH MODU ---
            # Harici kütüphane yerine bu kod tarayıcının "otomasyon" olduğunu gizler.
            await context.add_init_script("Object.defineProperty(navigator, 'webdriver', {get: () => undefined})")

            # --- REQUEST INTERCEPTION (Proxy çalışsa bile TL'yi zorla) ---
            async def handle_routes(route, request):
                # 1. POST İsteklerindeki Değişkenleri TR yap
                if request.method == "POST" and "graphql" in request.url:
                    try:
                        if request.post_data:
                            data = json.loads(request.post_data)
                            variables = data.get("variables", {})
                            # Eğer ülke/dil parametresi varsa zorla TR yap
                            if "country" in variables or "locale" in variables or "countryCode" in variables:
                                variables["country"] = "TR"
                                variables["countryCode"] = "TR"
                                variables["locale"] = "tr"
                                variables["currencyCode"] = "TRY"
                                data["variables"] = variables
                                await route.continue_(
                                    post_data=json.dumps(data),
                                    headers={**request.headers, "X-Epic-Storefront": "TR"}
                                )
                                return
                    except:
                        pass
                
                # 2. Ülke Bilgisi Sorulursa Mock Cevap Ver
                if "getCatalogCountryInfo" in request.url:
                    await route.fulfill(status=200, content_type="application/json", body=json.dumps(TR_COUNTRY_INFO))
                    return
                # 3. Para Birimi Sorulursa Mock Cevap Ver
                if "getCatalogCurrencyInfo" in request.url:
                    await route.fulfill(status=200, content_type="application/json", body=json.dumps(TR_CURRENCY_INFO))
                    return
                
                await route.continue_()

            await context.route("**/*", handle_routes)

            page = await context.new_page()

            print("⏳ Siteye bağlanılıyor...")
            await page.goto("https://store.epicgames.com/tr/browse?sortBy=releaseDate&sortDir=DESC&category=Game&count=40", wait_until="domcontentloaded")
            
            # İçeriği kontrol et
            content = await page.content()
            
            if "₺" in content or "TL" in content:
                print(f"✅ BAŞARILI! Proxy çalışıyor ve TL fiyatlar görünüyor: {proxy_url}")
            elif "$" in content:
                print("⚠️ Proxy çalıştı ama DOLAR görünüyor (Mock sistemi devreye girecek, devam ediliyor).")
            else:
                print("❌ Site yüklenmedi veya fiyatlar görünmüyor.")
                await browser.close()
                return False

            # --- VERİ ÇEKME KISMI ---
            all_games = []
            
            async def handle_response(response):
                if "graphql" in response.url and response.status == 200:
                    try:
                        json_data = await response.json()
                        elements = []
                        if "data" in json_data and "Catalog" in json_data["data"]:
                            cat = json_data["data"]["Catalog"]
                            if "searchStore" in cat: elements = cat["searchStore"]["elements"]
                            elif "catalogOffers" in cat: elements = cat["catalogOffers"]["elements"]
                        
                        if elements:
                            for game in elements:
                                title = game.get("title", "Bilinmiyor")
                                price_info = game.get("price", {}).get("totalPrice", {}).get("fmtPrice", {})
                                price = price_info.get("originalPrice", "0")
                                discount = price_info.get("discountPrice", "0")
                                
                                # Tekrarı önle ve listeye ekle
                                if title not in [g['title'] for g in all_games]:
                                    print(f"   🕹️ {title} -> {price}")
                                    all_games.append({"title": title, "price": price, "discount": discount})
                    except: pass
            
            page.on("response", handle_response)
            
            print("📜 Oyunlar yükleniyor (Scroll)...")
            # 3 kere aşağı kaydır (daha fazla veri için artırabilirsin)
            for _ in range(3):
                await page.evaluate("window.scrollBy(0, 1000)")
                await asyncio.sleep(3)
            
            if all_games:
                filename = f"epic_games_result.json"
                with open(filename, "w", encoding="utf-8") as f:
                    json.dump(all_games, f, ensure_ascii=False, indent=4)
                print(f"🎉 Toplam {len(all_games)} oyun '{filename}' dosyasına kaydedildi.")
                await browser.close()
                return True 
            
            await browser.close()
            return False

        except Exception as e:
            error_msg = str(e)
            if "Target closed" in error_msg: error_msg = "Bağlantı koptu"
            elif "Timeout" in error_msg: error_msg = "Zaman aşımı (Proxy çok yavaş)"
            print(f"❌ Proxy Hatası ({proxy_url}): {error_msg}")
            return False

async def main():
    print(f"🚀 Toplam {len(PROXY_LIST)} adet proxy denenecek...")
    
    for proxy in PROXY_LIST:
        success = await run_scraper(proxy)
        if success:
            print("\n🏁 İşlem başarıyla tamamlandı.")
            break
    else:
        print("\n😔 Hiçbir proxy ile sağlıklı veri çekilemedi. Yeni proxy bulman gerekebilir.")

if __name__ == "__main__":
    asyncio.run(main())
