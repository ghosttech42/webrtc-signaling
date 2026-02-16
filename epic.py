import asyncio
import random
import json
from playwright.async_api import async_playwright
from playwright_stealth import Stealth

async def main():
    async with Stealth().use_async(async_playwright()) as p:
        browser = await p.chromium.launch(headless=True)
        
        context = await browser.new_context(
            viewport={"width": 1920, "height": 1080},
            locale="tr-TR",
            timezone_id="Europe/Istanbul"
        )
        page = await context.new_page()
        state = {"page_count": 90}
        # --- YANITLARI YAKALAYAN FONKSİYON ---
        async def handle_response(response):
            # Sadece GraphQL endpoint'inden gelen ve başarılı (200) yanıtları al
            if "graphql" in response.url and response.status == 200:
                
                try:
                    # Yanıtın içeriğini JSON olarak al
                    json_data = await response.json()
                    
                    # Verinin içinde "Catalog" veya "searchStore" var mı kontrol et
                    # (Epic Games yapısına göre değişebilir, genelde 'data' altındadır)
                    if "data" in json_data and "Catalog" in json_data["data"]:
                        
                        elements = json_data["data"]["Catalog"]["searchStore"]["elements"]
                        current_page = state["page_count"] 
                        with open(f"epic{current_page}.json","w",encoding="utf-8")as f:
                            json.dump(json_data,f,indent=4,ensure_ascii=False)
                        print(f"\n--- {len(elements)} ADET OYUN BULUNDU ({response.url[-20:]}...) ---")
                        # 2. DÜZELTME: Sayacı sözlük üzerinden artırıyoruz
                        state["page_count"] += 1
                        for game in elements:
                            title = game.get("title", "Bilinmiyor")
                            # Fiyat bazen null olabilir (ücretsiz oyunlar vb.)
                            price_info = game.get("price", {}).get("totalPrice", {})
                            price = price_info.get("fmtPrice", {}).get("originalPrice", "0 TL")
                            
                            print(f"Oyun: {title} | Fiyat: {price}")
                    else:
                        print(f"veri yok {current_page}")    
                except Exception as e:
                    print(e)
                    # JSON olmayan yanıtlar veya farklı formatlar hataya düşmesin
                    pass

        # Olay dinleyicisini ekle (Her gelen pakette çalışır)
        print("Epic Games Mağazası yükleniyor...")
        for i in range(state["page_count"]-1,96):
            
            page.on("response", handle_response)
            await page.goto(
                f"https://store.epicgames.com/tr/browse?sortBy=releaseDate&sortDir=DESC&category=Game&count=40&start={i*40}",
                wait_until="domcontentloaded"
            )
        
        # Sayfanın verileri çekmesi için bekle
            await asyncio.sleep(5)
        
        # İstersen burada sayfa değiştirebilirsin, listener hala aktif olur.
        # print("\nSayfa kaydırılıyor/değiştiriliyor...")
        # await page.goto(
        #     "https://store.epicgames.com/tr/browse?sortBy=releaseDate&sortDir=DESC&category=Game&count=40&start=40",
        #     wait_until="domcontentloaded"
        # )
        
        await asyncio.sleep(5)
        await browser.close()

if __name__ == "__main__":
    asyncio.run(main())
