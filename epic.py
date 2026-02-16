import asyncio
import json
from playwright.async_api import async_playwright
from playwright_stealth import Stealth

# --- 1. MOCK VERİLERİ (Senin verdiğin yanıtlar) ---
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

async def handle_routes(route, request):
    # İsteğin URL'ine ve tipine bakıyoruz
    url = request.url
    method = request.method
    
    # POST verisini (payload) güvenle alalım
    post_data = {}
    if method == "POST" and request.post_data:
        try:
            post_data = json.loads(request.post_data)
        except:
            pass
    
    # URL parametrelerini veya Payload'ı kontrol edelim
    
    # SENARYO 1: Ülke Bilgisi İsteği (getCatalogCountryInfo)
    # Hem URL parametresinde hem de POST body içinde olabilir
    if "operationName=getCatalogCountryInfo" in url or post_data.get("operationName") == "getCatalogCountryInfo":
        print(">> 'getCatalogCountryInfo' yakalandı! TR verisiyle cevaplanıyor...")
        await route.fulfill(
            status=200,
            content_type="application/json",
            body=json.dumps(TR_COUNTRY_INFO)
        )
        return

    # SENARYO 2: Para Birimi İsteği (getCatalogCurrencyInfo)
    if "operationName=getCatalogCurrencyInfo" in url or post_data.get("operationName") == "getCatalogCurrencyInfo":
        print(">> 'getCatalogCurrencyInfo' yakalandı! TRY verisiyle cevaplanıyor...")
        await route.fulfill(
            status=200,
            content_type="application/json",
            body=json.dumps(TR_CURRENCY_INFO)
        )
        return

    # SENARYO 3: Asıl Oyun Listesi İsteği (searchStore veya Catalog)
    # Buradaki isteği manipüle edip değişkenleri (variables) TR'ye zorlayacağız.
    if method == "POST" and "graphql" in url:
        try:
            # Sadece oyun listeleme sorgusuysa müdahale et
            # Genelde 'searchStore', 'catalogQuery' veya null operationName olabilir
            is_catalog_query = False
            
            # Request body içinde variables kontrolü
            variables = post_data.get("variables", {})
            
            # Eğer countryCode veya country varsa TR yap
            if "country" in variables or "countryCode" in variables:
                variables["country"] = "TR"
                variables["countryCode"] = "TR"
                variables["locale"] = "tr"
                post_data["variables"] = variables
                is_catalog_query = True
            
            # Eğer bu bir katalog sorgusuysa, modifiye edilmiş veriyi gönder
            if is_catalog_query:
                await route.continue_(
                    post_data=json.dumps(post_data),
                    headers={
                        **request.headers,
                        "X-Epic-Storefront": "TR",
                        "Accept-Language": "tr-TR,tr;q=0.9"
                    }
                )
                return

        except Exception as e:
            print(f"Hata: {e}")

    # Diğer tüm istekler olduğu gibi devam etsin
    await route.continue_()

async def main():
    async with Stealth().use_async(async_playwright()) as p:
        browser = await p.chromium.launch(headless=True)
        
        context = await browser.new_context(
            viewport={"width": 1920, "height": 1080},
            locale="tr-TR",
            timezone_id="Europe/Istanbul"
        )
        
        # Çerezleri baştan verelim (Frontend'i kandırmaya yardımcı olur)
        await context.add_cookies([
            {"name": "EPIC_COUNTRY", "value": "TR", "domain": ".epicgames.com", "path": "/"},
            {"name": "EPIC_CURRENCY", "value": "TRY", "domain": ".epicgames.com", "path": "/"},
            {"name": "storefrontCountry", "value": "TR", "domain": ".epicgames.com", "path": "/"},
        ])

        # Tüm GraphQL isteklerini tek bir yönlendiricide toplayalım
        await context.route("**/graphql**", handle_routes)

        page = await context.new_page()
        
        # Sonuçları dinleyen fonksiyon
        async def handle_response(response):
            if "graphql" in response.url and response.status == 200:
                try:
                    json_data = await response.json()
                    
                    # Veriyi bul
                    if "data" in json_data and "Catalog" in json_data["data"]:
                        catalog = json_data["data"]["Catalog"]
                        elements = []
                        if "searchStore" in catalog:
                            elements = catalog["searchStore"]["elements"]
                        
                        if elements:
                            print(f"\n--- VERİ GELDİ ({len(elements)} OYUN) ---")
                            for game in elements:
                                title = game.get("title", "Bilinmiyor")
                                price_info = game.get("price", {}).get("totalPrice", {})
                                price = price_info.get("fmtPrice", {}).get("originalPrice", "0")
                                currency = price_info.get("currencyCode", "??")
                                
                                # Sadece ilk 3 tanesini yazdıralım ekran kirlenmesin
                                print(f"Oyun: {title} | Fiyat: {price} ({currency})")
                                if elements.index(game) == 2: break 
                except:
                    pass

        page.on("response", handle_response)
        
        print("Sayfa yükleniyor...")
        # Start=0 ile ilk sayfayı çağıralım
        await page.goto(
            "https://store.epicgames.com/tr/browse?sortBy=releaseDate&sortDir=DESC&category=Game&count=40&start=0",
            wait_until="domcontentloaded"
        )
        
        await asyncio.sleep(8) # Yükleme ve mock yanıtlarının işlemesi için bekle
        await browser.close()

if __name__ == "__main__":
    asyncio.run(main())
