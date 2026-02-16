import asyncio
import json
from playwright.async_api import async_playwright
from playwright_stealth import Stealth

# --- KAZANAN PROXY ---
# Az önce bulduğumuz çalışan IP
WORKING_PROXY = "http://149.86.140.214:8080" 

async def main():
    print(f"🚀 Başlatılıyor... Hedef Proxy: {WORKING_PROXY}")
    
    async with Stealth().use_async(async_playwright()) as p:
        try:
            browser = await p.chromium.launch(
                headless=True,
                proxy={"server": WORKING_PROXY}
            )
            
            # Proxy yavaş olduğu için timeout sürelerini artırdık (60sn)
            context = await browser.new_context(
                viewport={"width": 1920, "height": 1080},
                locale="tr-TR",
                timezone_id="Europe/Istanbul",
                user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/121.0.0.0 Safari/537.36",
                request_timeout=60000 
            )

            # Ekstra garanti çerezler
            await context.add_cookies([
                {"name": "EPIC_COUNTRY", "value": "TR", "domain": ".epicgames.com", "path": "/"},
                {"name": "storefrontCountry", "value": "TR", "domain": ".epicgames.com", "path": "/"},
            ])

            page = await context.new_page()
            
            # Bulunan oyunları saklayacağımız liste
            all_games = []

            # --- YÖNTEM 1: AĞ DİNLEME (En temiz veri) ---
            async def handle_response(response):
                if "graphql" in response.url and response.status == 200:
                    try:
                        json_data = await response.json()
                        # Veri yapısı bazen değişebilir, geniş kontrol yapalım
                        if "data" in json_data and "Catalog" in json_data["data"]:
                            catalog = json_data["data"]["Catalog"]
                            elements = []
                            
                            # Farklı şemalar olabilir
                            if "searchStore" in catalog:
                                elements = catalog["searchStore"]["elements"]
                            elif "catalogOffers" in catalog:
                                elements = catalog["catalogOffers"]["elements"]
                            
                            if elements:
                                print(f"📡 Ağdan {len(elements)} adet oyun verisi yakalandı!")
                                for game in elements:
                                    # Basitleştirilmiş veri objesi
                                    game_info = {
                                        "title": game.get("title"),
                                        "price": game.get("price", {}).get("totalPrice", {}).get("fmtPrice", {}).get("originalPrice"),
                                        "currency": game.get("price", {}).get("totalPrice", {}).get("currencyCode"),
                                        "discount": game.get("price", {}).get("totalPrice", {}).get("fmtPrice", {}).get("discountPrice")
                                    }
                                    all_games.append(game_info)
                    except:
                        pass

            page.on("response", handle_response)

            print("⏳ Epic Games mağazasına bağlanılıyor...")
            
            # İlk sayfaya git
            await page.goto(
                "https://store.epicgames.com/tr/browse?sortBy=releaseDate&sortDir=DESC&category=Game&count=40&start=0",
                wait_until="networkidle", # Ağ trafiği durana kadar bekle (Proxy için önemli)
                timeout=90000 # 1.5 dakika sabır süresi
            )

            # Sayfa yüklendi mi kontrol et
            content = await page.content()
            if "₺" in content or "TL" in content:
                print("✅ Fiyatlar TL olarak görünüyor.")
            else:
                print("⚠️ Uyarı: Sayfa yüklendi ama TL simgesi HTML'de görünmedi (Yine de devam ediliyor).")

            # Lazy Load tetiklemek için sayfayı yavaşça aşağı kaydır
            print("📜 Sayfa kaydırılıyor (Verilerin yüklenmesi için)...")
            for _ in range(5):
                await page.evaluate("window.scrollBy(0, 1000)")
                await asyncio.sleep(2)

            # --- YÖNTEM 2: EKRANDAN TOPLAMA (Yedek Plan) ---
            # Eğer ağdan veri gelmediyse, ekrandaki yazılardan topla
            if len(all_games) == 0:
                print("⚠️ Ağdan veri yakalanamadı, HTML'den okunuyor...")
                # Oyun kartlarını bul (Genel CSS yapısı)
                cards = await page.locator("section[data-component='PriceLayout']").all()
                titles = await page.locator("div[data-testid='offer-title-info-title']").all_innerTexts()
                
                # Basit eşleştirme (Tam doğru olmayabilir ama boş dönmekten iyidir)
                for i, title_text in enumerate(titles):
                    all_games.append({
                        "title": title_text,
                        "source": "HTML_SCRAPE"
                    })
                print(f"🖥️ Ekrandan {len(all_games)} oyun okundu.")

            # --- SONUÇLARI KAYDET ---
            if all_games:
                print(f"\n🎉 TOPLAM {len(all_games)} OYUN BULUNDU!")
                
                # Konsola ilk 5 tanesini bas
                for game in all_games[:5]:
                    print(f"🎮 {game.get('title')} | 💰 {game.get('price')} ({game.get('currency')})")
                
                # Dosyaya kaydet
                with open("oyunlar.json", "w", encoding="utf-8") as f:
                    json.dump(all_games, f, ensure_ascii=False, indent=4)
                print("\n💾 Veriler 'oyunlar.json' dosyasına kaydedildi.")
            else:
                print("\n❌ Veri çekilemedi. Proxy sayfayı açtı ama içerik boş olabilir.")

            await browser.close()

        except Exception as e:
            print(f"❌ Hata oluştu: {e}")

if __name__ == "__main__":
    asyncio.run(main())
