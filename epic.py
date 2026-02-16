import asyncio
import json
from playwright.async_api import async_playwright
from playwright_stealth import Stealth

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
    "socks5://185.86.5.162:8975" # Listede bir tane SOCKS5 vardı
]

# --- MOCK VERİLERİ (Garantilemek İçin) ---
TR_COUNTRY_INFO = {"data": {"Catalog": {"countryData": {"defaultCurrency": "TRY","paymentCurrency": "TRY","currencySymbolPlacement": "LEFT"}}}}
TR_CURRENCY_INFO = {"data": {"Catalog": {"currency": {"decimals": 2,"code": "TRY","symbol": "₺"}}}}

async def run_scraper(proxy_url):
    """
    Belirli bir proxy ile scraping işlemini dener.
    Başarılı olursa True döner ve işlemi tamamlar.
    """
    async with async_playwright() as p:
        print(f"\n🔌 Proxy deneniyor: {proxy_url}")
        
        try:
            # Proxy ile tarayıcıyı başlat
            browser = await p.chromium.launch(
                headless=True, 
                proxy={"server": proxy_url}
            )
            
            # Context oluştur (request_timeout hatası buradaydı, kaldırdık)
            context = await browser.new_context(
                viewport={"width": 1920, "height": 1080},
                locale="tr-TR",
                timezone_id="Europe/Istanbul",
                user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/121.0.0.0 Safari/537.36"
            )
            
            # Timeout ayarlarını SONRADAN yapıyoruz (Doğrusu bu)
            context.set_default_navigation_timeout(20000) # 20 saniye içinde bağlanmazsa pas geç
            context.set_default_timeout(20000)
            
            # Stealth modunu aktif et
            await Stealth().use_async(context.active_page if context.pages else await context.new_page())

            # --- REQUEST INTERCEPTION (Proxy çalışsa bile TL'yi zorla) ---
            async def handle_routes(route, request):
                if request.method == "POST" and "graphql" in request.url:
                    try:
                        # Giden isteği yakala ve TR parametrelerini ekle
                        if request.post_data:
                            data = json.loads(request.post_data)
                            variables = data.get("variables", {})
                            if "country" in variables or "locale" in variables:
                                variables["country"] = "TR"
                                variables["countryCode"] = "TR"
                                variables["locale"] = "tr"
                                data["variables"] = variables
                                await route.continue_(post_data=json.dumps(data))
                                return
                    except:
                        pass
                
                # Mock yanıtları (Site bize ülke sorduğunda)
                if "getCatalogCountryInfo" in request.url:
                    await route.fulfill(status=200, content_type="application/json", body=json.dumps(TR_COUNTRY_INFO))
                    return
                if "getCatalogCurrencyInfo" in request.url:
                    await route.fulfill(status=200, content_type="application/json", body=json.dumps(TR_CURRENCY_INFO))
                    return
                
                await route.continue_()

            await context.route("**/*", handle_routes)

            page = await context.new_page()

            # Test için Epic Games anasayfasına git
            print("⏳ Siteye bağlanılıyor...")
            await page.goto("https://store.epicgames.com/tr/browse?sortBy=releaseDate&sortDir=DESC&category=Game&count=40", wait_until="domcontentloaded")
            
            # İçeriği kontrol et
            content = await page.content()
            
            if "₺" in content or "TL" in content:
                print(f"✅ BAŞARILI! Proxy çalışıyor ve TL fiyatlar görünüyor: {proxy_url}")
            else:
                print("⚠️ Proxy bağlandı ama TL göremedi (veya site İngilizce açıldı).")
                # Yine de veri çekmeyi deneyebiliriz ama riskli.
                # Şimdilik başarısız sayıp diğerine geçelim en temizini bulalım.
                await browser.close()
                return False

            # --- BURAYA KADAR GELDİYSEK PROXY SAĞLAMDIR, VERİYİ ÇEKELİM ---
            
            all_games = []
            
            # Response dinleyicisi
            async def handle_response(response):
                if "graphql" in response.url and response.status == 200:
                    try:
                        json_data = await response.json()
                        elements = []
                        # Veri yolunu bul
                        if "data" in json_data and "Catalog" in json_data["data"]:
                            cat = json_data["data"]["Catalog"]
                            if "searchStore" in cat: elements = cat["searchStore"]["elements"]
                            elif "catalogOffers" in cat: elements = cat["catalogOffers"]["elements"]
                        
                        if elements:
                            for game in elements:
                                title = game.get("title", "Bilinmiyor")
                                price = game.get("price", {}).get("totalPrice", {}).get("fmtPrice", {}).get("originalPrice", "0")
                                if title not in [g['title'] for g in all_games]: # Tekrarı önle
                                    print(f"   🕹️ {title} -> {price}")
                                    all_games.append({"title": title, "price": price})
                    except: pass
            
            page.on("response", handle_response)
            
            # Sayfayı kaydır ki oyunlar yüklensin
            print("📜 Oyunlar yükleniyor (Scroll)...")
            for _ in range(3):
                await page.evaluate("window.scrollBy(0, 1000)")
                await asyncio.sleep(2)
            
            # Verileri kaydet
            if all_games:
                with open("epic_proxy_games.json", "w", encoding="utf-8") as f:
                    json.dump(all_games, f, ensure_ascii=False, indent=4)
                print(f"🎉 Toplam {len(all_games)} oyun kaydedildi.")
                await browser.close()
                return True # Başarılı oldu, döngüden çık
            
            await browser.close()
            return False

        except Exception as e:
            print(f"❌ Proxy Hatası ({proxy_url}): {str(e)[:100]}...") # Hatanın sadece başını göster
            return False

async def main():
    print(f"🚀 Toplam {len(PROXY_LIST)} adet proxy denenecek...")
    
    for proxy in PROXY_LIST:
        success = await run_scraper(proxy)
        if success:
            print("\n🏁 İşlem başarıyla tamamlandı. Diğer proxyleri denemeye gerek yok.")
            break
    else:
        print("\n😔 Hiçbir proxy ile sağlıklı veri çekilemedi. Listeyi güncellemen gerekebilir.")

if __name__ == "__main__":
    asyncio.run(main())
