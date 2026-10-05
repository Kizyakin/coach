# Шахматный тренер — Chess Coach RU

Полноценный русскоязычный шахматный тренер: уроки, дебюты, партия против Stockfish, Live Coach, анализ, персональные ошибки и интеграции Chess.com/Lichess.

## Что уже реализовано

- Русский интерфейс с 7 основными разделами.
- Уроки и учебная структура.
- Дебютная энциклопедия с объяснением «когда / зачем / планы / продолжения»; архитектура готова для полного ECO-каталога.
- Тренировочная доска против Stockfish.
- Live Coach с ручным вводом ходов.
- Coach-анализ: шах, форсирующие ходы, взятия, висящие фигуры, материал, развитие, фаза партии, приоритет позиции.
- Несколько уровней представления анализа: человеческое объяснение + скрытый engine line.
- Backend-разбор PGN как внутренний механизм для автоматического разбора партий.
- Интеграция чтения последних партий Chess.com и Lichess.
- Схема хранения игр и персональных ошибок.
- Render Blueprint и Docker backend со Stockfish.

## Локальный запуск

### Backend

```bash
cd backend
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
# macOS: brew install stockfish
# Linux: sudo apt install stockfish
cp .env.example .env
uvicorn app.main:app --reload
```

Если путь Stockfish отличается, задайте `STOCKFISH_PATH` в `.env`.

### Frontend

```bash
cd frontend
npm install
npm run dev
```

Открыть: `http://localhost:5173`.

## Render

В корне уже есть `render.yaml`.

1. Создать GitHub-репозиторий и загрузить содержимое этой папки.
2. В Render выбрать **New → Blueprint** и подключить репозиторий.
3. Для `chess-coach-web` указать `VITE_API_URL=https://<имя-api>.onrender.com`.
4. Для `chess-coach-api` указать `FRONTEND_ORIGIN=https://<имя-web>.onrender.com`.
5. Запустить deploy.

### Render Free и база данных

- Web Service засыпает после простоя; первый запрос после сна зависит от cold start Render.
- Начиная с v1.5 PostgreSQL **не обязателен для запуска**. Если `DATABASE_URL` отсутствует или база истекла, все шахматные функции продолжают работать без persistence.
- Для постоянных аккаунтов/прогресса позже можно подключить любой PostgreSQL через `DATABASE_URL`, не меняя шахматное ядро.

## API

После запуска backend документация доступна на `/docs`.

Ключевые endpoint'ы:

- `GET /api/lessons`
- `GET /api/openings`
- `POST /api/coach/analyze`
- `POST /api/engine/move`
- `POST /api/move/preview`
- `POST /api/review`
- `GET /api/integrations/chesscom/{username}`
- `GET /api/integrations/lichess/{username}`

## Архитектурный принцип

Один слой шахматного анализа используется во всех режимах:

`позиция → chess logic → Stockfish → Coach → русское объяснение → Player Model`

Это позволяет улучшать объяснения и классификацию ошибок в одном месте, не переписывая Play, Live Coach, Review и Training отдельно.

## Master Games Coach (v1.4)

В проект добавлен case-based слой на партиях 45 великих и современных игроков. Список доступен через `/api/masters`.

Чтобы собрать локальную компактную библиотеку практических позиций:

```bash
cd backend
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
python scripts/build_master_library.py --players 45 --games-per-player 60 --positions-per-game 12
cd ..
```

После этого закоммить `backend/app/data/master_library/master_positions.json.gz` и отправь его в GitHub. Raw PGN не сохраняются.


## Performance Mode (v1.5)

Live Coach по умолчанию использует `FAST`: один постоянно запущенный Stockfish, ~120 ms engine budget, MultiPV=3, RAM-кэш позиций и неблокирующий Master Games слой. `NORMAL` и `DEEP` доступны из интерфейса для более подробного анализа.

## FAST master positions (v1.6)

Live Coach 1.6 uses a pre-aggregated master-position hash index instead of scanning the full case library at request time. Build it once locally before pushing to GitHub:

```bash
cd backend
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
python scripts/build_master_library.py --players 45 --games-per-player 60 --positions-per-game 12
cd ..
```

Commit `backend/app/data/master_library/master_fast_index.json.gz`. Raw PGNs are not stored. On API startup the compact index is preloaded into RAM, so FAST Coach performs only O(1) dictionary lookups.
