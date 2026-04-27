import json
from bs4 import BeautifulSoup


def parse_search_results(html: str):
    soup = BeautifulSoup(html, "html.parser")

    scripts = soup.find_all("script")

    results = []

    for script in scripts:
        if script.string and "window.__initialData__" in script.string:
            try:
                json_text = script.string.split("=", 1)[1].strip().rstrip(";")
                data = json.loads(json_text)

                items = (
                    data.get("catalog", {})
                    .get("items", [])
                )

                for item in items:
                    title = item.get("title")
                    price = item.get("price", {}).get("string")
                    link = "https://www.avito.ru" + item.get("urlPath", "")

                    if title and link:
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