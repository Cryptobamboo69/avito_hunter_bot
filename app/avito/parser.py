from bs4 import BeautifulSoup


def parse_search_results(html: str):
    soup = BeautifulSoup(html, "html.parser")

    results = []

    # основной контейнер объявлений
    items = soup.select('div[data-marker="item"]')

    for item in items:
        try:
            # заголовок
            title_tag = item.select_one('h3')
            title = title_tag.get_text(strip=True) if title_tag else "Без названия"

            # цена (новый селектор Avito)
            price_tag = item.select_one('[data-marker="item-price"]')
            price = price_tag.get_text(strip=True) if price_tag else "Цена не указана"

            # ссылка
            link_tag = item.select_one('a[data-marker="item-title"]')
            link = None

            if link_tag and link_tag.get("href"):
                link = "https://www.avito.ru" + link_tag["href"]

            if link:
                results.append({
                    "title": title,
                    "price": price,
                    "link": link
                })

        except Exception:
            continue

    return _dedupe(results)


def _dedupe(items):
    seen = set()
    unique = []

    for item in items:
        if item["link"] not in seen:
            seen.add(item["link"])
            unique.append(item)

    return unique