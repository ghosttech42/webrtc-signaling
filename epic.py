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
        await context.route(
            "**/graphql",
            lambda route, request: asyncio.create_task(
                route.continue_(
                    headers={
                        **request.headers,
                        "Accept-Language": "tr-TR,tr;q=0.9",
                        "X-Epic-Country": "TR"
                    }
                )
            )
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
            
                f"https://store.epicgames.com/graphql?operationName=searchStoreQuery&variables=%7B%22allowCountries%22:%22TR%22,%22category%22:%22games%2Fedition%2Fbase%22,%22comingSoon%22:false,%22count%22:40,%22country%22:%22TR%22,%22keywords%22:%22%22,%22locale%22:%22tr%22,%22sortBy%22:%22releaseDate%22,%22sortDir%22:%22DESC%22,%22start%22:{i*40},%22tag%22:%22%22,%22withPrice%22:true%7D&extensions=%7B%22persistedQuery%22:%7B%22version%22:1,%22sha256Hash%22:%2229d49ab31d438cd90be2d554d2d54704951e4223a8fcd290fcf68308841a1979%22%7D%7D",
                wait_until="domcontentloaded"
            )
#    f"https://store.epicgames.com/tr/browse?sortBy=releaseDate&sortDir=DESC&category=Game&count=40&start={i*40}",
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
