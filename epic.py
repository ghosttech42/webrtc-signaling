import asyncio
import json
from playwright.async_api import async_playwright
from playwright_stealth import Stealth

# --- SENİN BULDUĞUN PROXY LİSTESİ ---
# En yeniden eskiye ve en güvenilire göre sıraladım.
# Format: "http://ip:port"
PROXY_LIST = [
    "http://176.236.227.106:8080",  # Superonline (En yüksek ihtimal)
    "http://185.181.208.88:3128",   # Hostigger
    "http://185.103.202.35:8443",
    "http://149.86.140.214:8080",
    "http://194.124.36.14:8080",
    "http://164.138.207.81:8080",
    "http://149.86.139.166:8085",
    "http://213.74.163.181:8080",
    "http://188.132.221.188:8080",
    "http://176.88.191.254:8080"
]

async def run_scraper_with_proxy(playwright, proxy_url):
    print(f"\n{'='*50}")
    print(f"📡 PROXY DENENİYOR: {proxy_url}")
    print(f"{'='*50}")

    browser = None
    try:
        # Proxy ile tarayıcıyı başlat
        browser = await playwright.chromium.launch(
            headless=True,
            proxy={"server": proxy_url}
        )
        
        # Context ayarları (Timeout'u biraz uzun tutuyoruz çünkü free proxy yavaştır)
        context = await browser.new_context(
            viewport={"width": 1920, "height": 1080},
            locale="tr-TR",
            timezone_id="Europe/Istanbul",
            user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/121.0.0.0 Safari/537.36"
        )

        # Ekstra: Çerezlerle de TR zorlaması yapalım (IP en önemlisidir ama bu da yardımcı olur)
        await context.add_cookies([
            {"name": "EPIC_COUNTRY", "value": "TR", "domain": ".epicgames.com", "path": "/"},
            {"name": "storefrontCountry", "value": "TR", "domain": ".epicgames.com", "path": "/"},
        ])

        page = await context.new_page()

        # --- 1. KONTROL AŞAMASI ---
        print("⏳ Epic Games ana sayfasına bağlanılıyor (Fiyat Kontrolü)...")
        try:
            # Sadece HTML'i hızlıca yükle
            await page.goto("https://store.epicgames.com/tr/browse?count=1", timeout=60000, wait_until="domcontentloaded")
            await asyncio.sleep(5) # Fiyatların yüklenmesi için bekle
        except Exception as e:
            print(f"❌ Bağlantı hatası (Timeout/Erişim): {e}")
            await browser.close()
            return False

        # İçeriği kontrol et
        content = await page.content()
        
        if "$" in content and "₺" not in content:
            print("⚠️ BAŞARISIZ: Proxy çalışıyor ama fiyatlar DOLAR ($). Epic bu IP'yi TR saymıyor.")
            await browser.close()
            return False
        
        if "₺" not in content and "TL" not in content:
            print("⚠️ BAŞARISIZ: Sayfa yüklendi ama fiyat simgesi (₺/TL) bulunamadı.")
            await browser.close()
            return False

        print("✅ BAŞARILI! TÜRK LİRASI (₺) TESPİT EDİLDİ.")
        print("📥 Veri çekme işlemine başlanıyor...")

        # --- 2. VERİ ÇEKME AŞAMASI (Listener Ekleme) ---
        
        # GraphQL Yanıtlarını Dinleyen Fonksiyon
        async def handle_response(response):
            if "graphql" in response.url and response.status == 200:
                try:
                    json_data = await response.json()
                    
                    # Verinin içinde oyun kataloğu var mı?
                    if "data" in json_data and "Catalog" in json_data["data"]:
                        catalog = json_data["data"]["Catalog"]
                        elements = []
                        if "searchStore" in catalog:
                            elements = catalog["searchStore"]["elements"]
                        
                        if elements:
                            print(f"\n--- 📦 PAKET GELDİ ({len(elements)} OYUN) ---")
                            for game in elements:
                                title = game.get("title", "Bilinmiyor")
                                price_info = game.get("price", {}).get("totalPrice", {})
                                price = price_info.get("fmtPrice", {}).get("originalPrice", "0")
                                currency = price_info.get("currencyCode", "??")
                                
                                # Sadece TL olanları veya hepsini yazdır
                                print(f"🎮 {title} | 💰 {price} ({currency})")
                except:
                    pass

        page.on("response", handle_response)

        # Sayfaları gez (Örnek olarak ilk 2 sayfayı -80 oyun- çekelim)
        # Eğer tümünü çekeceksen range'i artır.
        for i in range(0, 2):
            print(f"\n>> Sayfa {i+1} yükleniyor (Start={i*40})...")
            await page.goto(
                f"https://store.epicgames.com/tr/browse?sortBy=releaseDate&sortDir=DESC&category=Game&count=40&start={i*40}",
                wait_until="domcontentloaded",
                timeout=60000
            )
            # Verilerin gelmesi için bekle
            await asyncio.sleep(8)

        print("\n✅ İşlem başarıyla tamamlandı.")
        await browser.close()
        return True

    except Exception as e:
        print(f"❌ Beklenmeyen hata: {e}")
        if browser:
            await browser.close()
        return False

async def main():
    async with Stealth().use_async(async_playwright()) as p:
        success = False
        for proxy in PROXY_LIST:
            # Her proxy'yi dene, eğer başarılı olursa döngüyü kır
            success = await run_scraper_with_proxy(p, proxy)
            if success:
                break
        
        if not success:
            print("\n❌❌ MAALESEF: Listedeki hiçbir proxy ile TL fiyatı alınamadı.")

if __name__ == "__main__":
    asyncio.run(main())
