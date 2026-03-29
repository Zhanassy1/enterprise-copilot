# Скриншоты UI для README и презентаций

## План съёмки (что показываем)

| Сценарий | Файл | Содержимое кадра |
|----------|------|------------------|
| Маркетинг / home | `landing.png` | Hero, возможности, блок тарифов, CTA |
| Тарифы | `pricing.png` | Страница `/pricing` |
| Workspace / документы | `documents.png` | Список документов (по умолчанию — сразу после входа; с worker см. ниже) |
| Очередь / async | `jobs.png` | `/jobs` — задачи индексации |
| План и usage | `billing.png` | `/billing` — план и лимиты |
| Поиск | `search.png` | `/search` |
| Чат | `chat.png` | `/chat` |
| Аудит (admin-friendly) | `audit.png` | `/audit` — журнал событий |
| Summary (опционально) | `summary.png` | Диалог «Краткое содержание» после индексации |

## Готовые файлы в репозитории

Каталог: **`docs/assets/screenshots/`** (PNG добавляются командой ниже, не игнорируются `.gitignore`).

| Файл | Генерация |
|------|-----------|
| `landing.png` | `frontend` → `npm run demo:screenshots` |
| `pricing.png` | то же |
| `documents.png` | то же (без ожидания worker — часто пустой список или документ «В очереди», если только что загрузили вручную) |
| `jobs.png` | то же |
| `billing.png` | то же |
| `search.png` | то же |
| `chat.png` | то же |
| `audit.png` | то же |
| `summary.png` | Только при **`DEMO_SCREENSHOTS_WITH_INGEST=1`** и **работающем Celery worker**, иначе шаг пропускается |

## Где используются

- **[README.md](../../README.md)** — секция «Скриншоты», быстрый визуальный обзор для evaluators.
- **[docs/DEMO_MEDIA.md](../DEMO_MEDIA.md)** — сценарий живого демо; те же экраны в том же порядке, что и скриншоты.
- Презентации / PR / портфолио — прямые пути `docs/assets/screenshots/*.png` из корня репозитория (GitHub рендерит в Markdown).

## Как снять автоматически

Требуется запущенный стек: UI (например `http://127.0.0.1:3000`) и API (`E2E_API_URL` или `http://127.0.0.1:8000/api/v1` по умолчанию).

```bash
cd frontend
npm run demo:screenshots
```

Перед прогоном Playwright создаёт тестового пользователя через `POST /auth/register`.

**Полный кадр документов + summary:** поднимите worker (`docker compose` с Celery), затем:

```bash
# PowerShell
$env:DEMO_SCREENSHOTS_WITH_INGEST="1"; npm run demo:screenshots

# bash
DEMO_SCREENSHOTS_WITH_INGEST=1 npm run demo:screenshots
```

Используется фикстура `frontend/e2e/fixtures/demo-ingest.txt`; ожидается статус документа **Готово** (до ~2 мин ожидания на шаг).

## Что ещё не снято / ограничения

- **`search.png` / `chat.png`** без готового индекса показывают UI без осмысленных ответов — для «живого» кадра с контекстом нужен проиндексированный документ (ручной прогон или `DEMO_SCREENSHOTS_WITH_INGEST=1`).
- **`summary.png`** отсутствует, если не задан `DEMO_SCREENSHOTS_WITH_INGEST=1` или worker не обработал очередь.
- Отдельные кадры **регистрации**, **выбора workspace** (если несколько), **модалки загрузки** — по желанию вручную; в авто-спеке не выделены.
- Тёмная тема, мобильная вёрстка — в плане нет; съёмка **1440×900** (см. `e2e/demo-screenshots.spec.ts`).

## Видео

Слот на маркетинговой главной и чек-лист записи: **[docs/DEMO_MEDIA.md](../DEMO_MEDIA.md)**.
