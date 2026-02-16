import asyncio
import json
from playwright.async_api import async_playwright
from playwright_stealth import Stealth

# --- KAZANAN PROXY ---
WORKING_PROXY = "http://149.86.140.214:8080" 

async def main():
    print(f"🚀 Başlatılıyor... Hedef Proxy: {WORKING_PROXY}")
    
    async with Stealth().use_async(async_playwright()) as p:
        try:
            browser = await p.chromium.launch(
                headless=True,
                proxy={"server": WORKING_PROXY}
            )
            
            # DÜZELTME: request_timeout buradan kaldırıldı.
            context = await browser.new_context(
                viewport={"width": 1920, "height": 1080},
                locale="tr-TR",
                timezone_id="Europe/Istanbul",
                user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/121.0.0.0 Safari/537.36"
            )

            # DÜZELTME: Timeout ayarları buraya eklendi (90 saniye)
            context.set_default_navigation_timeout(90000)
            context.set_default_timeout(90000)

            await context.add_cookies([
                {"name": "EPIC_COUNTRY", "value": "TR", "domain": ".epicgames.com", "path": "/"},
                {"name": "storefrontCountry", "value": "TR", "domain": ".epicgames.com", "path": "/"},
            ])

            page = await context.new_page()
            
            # Verileri saklayacağımız liste
            all_games = []

            # --- AĞ DİNLEYİCİSİ ---
            async def handle_response(response):
                if "graphql" in response.url and response.status == 200:
                    try:
                        json_data = await response.json()
                        if "data" in json_data and "Catalog" in json_data["data"]:
                            catalog = json_data["data"]["Catalog"]
                            elements = []
                            
                            if "searchStore" in catalog:
                                elements = catalog["searchStore"]["elements"]
                            elif "catalogOffers" in catalog:
                                elements = catalog["catalogOffers"]["elements"]
                            
                            if elements:
                                print(f"📡 Ağdan {len(elements)} oyun verisi yakalandı!")
                                for game in elements:
                                    price_info = game.get("price", {}).get("totalPrice", {})
                                    fmt_price = price_info.get("fmtPrice", {})
                                    
                                    game_info = {
                                        "title": game.get("title"),
                                        "price": fmt_price.get("originalPrice"),
                                        "currency": price_info.get("currencyCode"),
                                        "discount_price": fmt_price.get("discountPrice")
                                    }
                                    all_games.append(game_info)
                                    # Anlık ekrana da basalım ki çalıştığını gör
                                    print(f"   -> {game_info['title']} : {game_info['price']}")
                    except:
                        pass

            page.on("response", handle_response)

            print("⏳ Epic Games mağazasına bağlanılıyor (Proxy yavaş olabilir, lütfen bekle)...")
            
            try:
                # İlk sayfaya git
                await page.goto(
                    "https://store.epicgames.com/tr/browse?sortBy=releaseDate&sortDir=DESC&category=Game&count=40&start=0",
                    wait_until="domcontentloaded"
                )
            except Exception as e:
                print(f"⚠️ Sayfa tam yüklenemedi ama devam ediliyor: {e}")

            # Sayfa yüklendi mi kontrol et (HTML içinde TL var mı?)
            try:
                content = await page.content()
                if "₺" in content or "TL" in content:
                    print("✅ BAŞARILI: Fiyatlar TL olarak görünüyor.")
                elif "$" in content:
                    print("⚠️ UYARI: Fiyatlar DOLAR görünüyor (Proxy TR olarak algılanmadı).")
            except:
                pass

            # Lazy Load tetiklemek için sayfayı aşağı kaydır
            print("📜 Oyunların yüklenmesi için sayfa kaydırılıyor...")
            for i in range(1, 6):
                print(f"   Kaydırma {i}/5...")
                await page.evaluate("window.scrollBy(0, 800)")
                # Proxy yavaş olduğu için her kaydırmada 3 saniye bekle
                await asyncio.sleep(3)

            # --- KAYDETME ---
            if all_games:
                print(f"\n🎉 TOPLAM {len(all_games)} OYUN ÇEKİLDİ!")
                
                # Dosyaya kaydet
                with open("oyunlar.json", "w", encoding="utf-8") as f:
                    json.dump(all_games, f, ensure_ascii=False, indent=4)
                print("💾 Veriler 'oyunlar.json' dosyasına kaydedildi.")
            else:
                print("\n❌ Veri çekilemedi. Proxy sayfayı açtı ama GraphQL verisi yakalanamadı.")
                print("İpucu: Proxy çok yavaş olduğu için veriler zaman aşımına uğruyor olabilir.")

            await browser.close()

        except Exception as e:
            print(f"❌ Kritik Hata: {e}")

if __name__ == "__main__":
    asyncio.run(main())
