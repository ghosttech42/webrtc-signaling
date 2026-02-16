import asyncio
import json
import random
from playwright.async_api import async_playwright
from playwright_stealth import Stealth

# --- MOCK VERİLERİ (Epic'i kandırmak için) ---
TR_COUNTRY_INFO = {
    "data": {
        "Catalog": {
            "countryData": {
                "defaultCurrency": "TRY",
                "paymentCurrency": "TRY",
                "currencySymbolPlacement": "LEFT"
            }
        }
    }
}

TR_CURRENCY_INFO = {
    "data": {
        "Catalog": {
            "currency": {
                "decimals": 2,
                "code": "TRY",
                "symbol": "₺"
            }
        }
    }
}

async def main():
    print("🚀 Bot Başlatılıyor (Proxy yok, Hızlandırma aktif)...")
    
    async with Stealth().use_async(async_playwright()) as p:
        # Headless=False yaparsan tarayıcıyı görürsün, True yaparsan arka planda çalışır
        browser = await p.chromium.launch(headless=True)
        
        context = await browser.new_context(
            viewport={"width": 1920, "height": 1080},
            locale="tr-TR",
            timezone_id="Europe/Istanbul",
            user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/121.0.0.0 Safari/537.36"
        )
        
        # Zaman aşımı ayarları (30 saniye)
        context.set_default_navigation_timeout(30000)
        context.set_default_timeout(30000)

        # --- AĞ YÖNLENDİRİCİSİ (REQUEST INTERCEPTION) ---
        # Burası Epic Games'e giden istekleri yakalayıp "Biz TR'deyiz" diyor.
        async def handle_routes(route, request):
            url = request.url
            method = request.method
            post_data = {}
            
            if method == "POST" and request.post_data:
                try:
                    post_data = json.loads(request.post_data)
                except:
                    pass

            # 1. Ülke Bilgisi İsteği
            if "operationName=getCatalogCountryInfo" in url or post_data.get("operationName") == "getCatalogCountryInfo":
                await route.fulfill(status=200, content_type="application/json", body=json.dumps(TR_COUNTRY_INFO))
                return

            # 2. Para Birimi İsteği
            if "operationName=getCatalogCurrencyInfo" in url or post_data.get("operationName") == "getCatalogCurrencyInfo":
                await route.fulfill(status=200, content_type="application/json", body=json.dumps(TR_CURRENCY_INFO))
                return

            # 3. Oyun Listesi İsteği (searchStore) - Değişkenleri TR'ye çevir
            if "graphql" in url and method == "POST":
                try:
                    data = json.loads(request.post_data)
                    variables = data.get("variables", {})
                    
                    # Zorla TR yapıyoruz
                    if "country" in variables or "countryCode" in variables or "locale" in variables:
                        variables["country"] = "TR"
                        variables["countryCode"] = "TR"
                        variables["locale"] = "tr"
                        variables["currencyCode"] = "TRY"
                        data["variables"] = variables
                        
                        # Modifiye edilmiş isteği gönder
                        await route.continue_(
                            post_data=json.dumps(data),
                            headers={**request.headers, "X-Epic-Storefront": "TR"}
                        )
                        return
                except:
                    pass
            
            # Diğer her şeye izin ver
            await route.continue_()

        # Tüm GraphQL isteklerini dinle
        await context.route("**/graphql", handle_routes)

        page = await context.new_page()

        # --- VERİ YAKALAYICI (RESPONSE LISTENER) ---
        async def handle_response(response):
            if "graphql" in response.url and response.status == 200:
                try:
                    json_data = await response.json()
                    
                    # Veri yolu bazen değişebilir, iki ihtimali de kontrol edelim
                    elements = []
                    if "data" in json_data and "Catalog" in json_data["data"]:
                        catalog = json_data["data"]["Catalog"]
                        if "searchStore" in catalog:
                            elements = catalog["searchStore"]["elements"]
                        elif "catalogOffers" in catalog:
                            elements = catalog["catalogOffers"]["elements"]

                    if elements:
                        print(f"\n✅ {len(elements)} OYUN VERİSİ GELDİ!")
                        for game in elements:
                            title = game.get("title", "Bilinmiyor")
                            
                            # Fiyat Okuma
                            price_info = game.get("price", {}).get("totalPrice", {})
                            fmt_price = price_info.get("fmtPrice", {})
                            original_price = fmt_price.get("originalPrice", "0")
                            discount_price = fmt_price.get("discountPrice", "0")
                            
                            print(f"   🕹️ {title} -> {original_price} (İndirimli: {discount_price})")
                            
                except Exception as e:
                    # Bazen JSON olmayan yanıtlar gelir, onları görmezden gel
                    pass

        # Response dinleyicisini sayfaya ekle
        page.on("response", handle_response)

        # --- DÖNGÜ İLE SAYFALARI GEZME ---
        print("⏳ Epic Games mağazasına bağlanılıyor...")
        
        # Kaç sayfa çekeceksin? Örnek: 0'dan 5. sayfaya kadar (Her sayfa 40 oyun)
        # range(0, 5) yaparsan ilk 200 oyunu çeker.
        for page_num in range(0, 3): 
            start_count = page_num * 40
            print(f"\n--- SAYFA {page_num + 1} (Start: {start_count}) YÜKLENİYOR ---")
            
            try:
                await page.goto(
                    f"https://store.epicgames.com/tr/browse?sortBy=releaseDate&sortDir=DESC&category=Game&count=40&start={start_count}",
                    wait_until="domcontentloaded"
                )
                
                # Sayfanın tam oturması ve verinin akması için bekle
                await asyncio.sleep(4) 
                
                # Lazy load için azıcık aşağı kaydır
                await page.evaluate("window.scrollBy(0, 500)")
                await asyncio.sleep(1)
                
            except Exception as e:
                print(f"⚠️ Sayfa geçiş hatası: {e}")

        print("\n🏁 İşlem tamamlandı.")
        await browser.close()

if __name__ == "__main__":
    asyncio.run(main())
