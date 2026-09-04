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

### Ограничения Render Free

- Web Service засыпает после 15 минут без входящего трафика и затем «просыпается» при новом запросе.
- Бесплатный Postgres ограничен 1 GB и истекает через 30 дней. Код использует стандартный `DATABASE_URL`, поэтому позже БД можно без изменений приложения перенести на другой PostgreSQL.
- Файлы внутри Web Service непостоянны, поэтому SQLite на Render не использовать для пользовательских данных.

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
