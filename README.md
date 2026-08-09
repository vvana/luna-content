# luna-content

Автопубликация Instagram для «Луна не советует» (@luna.ne.sovetuet).

- `ig-queue.json` — очередь постов (время московское)
- `media/` — файлы недели; Meta забирает их по raw-URL
- `ig_publish.py` — публикатор, запускается GitHub Actions по крону
  (окна 09:00–11:00 и 18:00–20:00 МСК) или вручную через workflow_dispatch

Секреты репозитория: `IG_ACCESS_TOKEN` (long-lived токен Instagram API,
обновляется еженедельно скриптом `ig_push_week.py` с рабочей машины)
и `IG_USER_ID`.

Наполняется еженедельным прогоном из `D:\SandBox\luna-ne-sovetuet\`
(скрипт `reels-generator\ig_push_week.py`: копирует медиа, пушит,
освежает токен).
