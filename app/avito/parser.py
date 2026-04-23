from bs4 import BeautifulSoup


def parse_search_results(html: str):
    """
    Парсит HTML выдачи Avito и возвращает список объявлений
    """
    soup = BeautifulSoup(html, "html.parser")

    results = []

    items = soup.select('[data-marker="item"]')

    for item in items:
        try:
            title_tag = item.select_one('[itemprop="name"]')
            price_tag = item.select_one('[itemprop="price"]')
            link_tag = item.select_one("a[itemprop='url']")

            title = title_tag.get_text(strip=True) if title_tag else "Без названия"
            price = price_tag.get_text(strip=True) if price_tag else "Цена не указана"
            link = "https://www.avito.ru" + link_tag["href"] if link_tag else None

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
    """
    Убирает дубли по ссылке
    """
    seen = set()
    unique = []

    for item in items:
        if item["link"] not in seen:
            seen.add(item["link"])
            unique.append(item)

    return unique