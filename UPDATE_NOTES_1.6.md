# Chess Coach 1.6 — FAST Master Index

Главная цель версии: подключить мастерские позиции к Live Coach без заметного влияния на задержку FAST.

## Что изменилось

- FAST Stockfish budget: 120 мс → 90 мс, чтобы оставить запас на Python/API и мастерский слой.
- Мастерские позиции больше не сканируются на каждом запросе.
- Новый `master_fast_index.json.gz` — агрегированный O(1) hash index.
- Три уровня совпадения позиции:
  - exact: ход + фаза + материал + положение королей + структура центра;
  - medium: ход + фаза + материал + положение королей;
  - broad: ход + фаза + материал.
- Индекс загружается один раз при старте API.
- FAST lookup — только несколько обращений к dict, без similarity scan.
- В `/api/masters/status` видны mode, buckets, load_ms и состояние индекса.
- В `master_insight.lookup_ms` можно смотреть стоимость мастерского lookup на конкретном ходе.

## Цель по задержке

На прогретом Render Worker:

- Stockfish FAST: ориентир ~90–140 мс с учётом UCI overhead;
- master lookup: обычно <1–2 мс;
- server-side total: целевой диапазон ~110–175 мс.

Это целевой бюджет, а не абсолютная гарантия: планировщик CPU на Render Free иногда может дать всплеск выше 180 мс.

## Один раз перед GitHub

В `backend`:

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
python scripts/build_master_library.py --players 45 --games-per-player 60 --positions-per-game 12
```

После завершения должен появиться:

```text
backend/app/data/master_library/master_fast_index.json.gz
```

Именно этот файл нужно закоммитить. Сырые PGN не сохраняются.

Проверка после Render deploy:

```text
GET /api/masters/status?load=true
```

Ожидается:

```json
{
  "available": true,
  "loaded": true,
  "mode": "fast-index",
  "positions": 30000,
  "players": 45
}
```

Число позиций будет зависеть от доступных архивов и фильтрации.
