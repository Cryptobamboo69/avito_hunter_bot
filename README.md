# Avito Context Bot (MVP)

Telegram-бот для мониторинга новых объявлений на Avito по контекстным правилам.

## Что умеет MVP
- Хранит поисковые задачи в SQLite.
- Проверяет заранее подготовленные поисковые URL Avito по расписанию.
- Пытается вытаскивать новые объявления из HTML.
- Фильтрует по цене, ключевым словам, брендам, размерам и стоп-словам.
- Не шлёт дубли.
- Показывает, почему объявление прошло фильтр.

## Важно
Это MVP. Вёрстка Avito может меняться, поэтому файл `app/avito/parser.py` сделан максимально осторожным и допускает доработку селекторов под актуальную разметку.

## Быстрый старт
1. Создай бота через BotFather и скопируй токен.
2. Скопируй `.env.example` в `.env` и заполни значения.
3. Установи зависимости:
   ```bash
   pip install -r requirements.txt
   ```
4. Запусти:
   ```bash
   python -m app.bot
   ```

## Команды
- `/start`
- `/help`
- `/add_json` — добавить задачу JSON-ом
- `/list` — список задач
- `/pause <id>`
- `/resume <id>`
- `/delete <id>`
- `/check <id>` — разово проверить задачу
- `/checkall` — проверить все активные задачи

## Формат задачи
Используй `/add_json`, затем отправь JSON одним сообщением:

```json
{
  "name": "Nespresso Essenza Mini",
  "search_url": "https://www.avito.ru/moskva?q=nespresso+essenza+mini+c30",
  "max_price": 3000,
  "city": "Москва",
  "include_keywords": ["nespresso", "essenza", "mini", "c30", "delonghi"],
  "exclude_keywords": ["vertuo", "совместим", "аналог", "3 в 1"],
  "brand_filters": ["nespresso", "delonghi"],
  "size_filters": [],
  "min_score": 8,
  "check_interval_sec": 120,
  "enabled": true
}
```

## Примеры задач
Смотри `data/sample_tasks.json`.
