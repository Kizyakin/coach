import asyncio
import csv
import io
import re
from functools import lru_cache

import chess
import chess.pgn
import httpx

LICHESS_OPENING_URLS = [
    f"https://raw.githubusercontent.com/lichess-org/chess-openings/master/{letter}.tsv"
    for letter in "abcde"
]

FAMILY_RU = {
    "Sicilian Defense": "Сицилианская защита",
    "French Defense": "Французская защита",
    "Caro-Kann Defense": "Защита Каро-Канн",
    "Alekhine Defense": "Защита Алехина",
    "Scandinavian Defense": "Скандинавская защита",
    "Pirc Defense": "Защита Пирца",
    "Modern Defense": "Современная защита",
    "Ruy Lopez": "Испанская партия",
    "Italian Game": "Итальянская партия",
    "Scotch Game": "Шотландская партия",
    "Vienna Game": "Венская партия",
    "Four Knights Game": "Дебют четырёх коней",
    "Three Knights Opening": "Дебют трёх коней",
    "King's Gambit": "Королевский гамбит",
    "Queen's Gambit": "Ферзевый гамбит",
    "Queen's Gambit Declined": "Отказанный ферзевый гамбит",
    "Queen's Gambit Accepted": "Принятый ферзевый гамбит",
    "Slav Defense": "Славянская защита",
    "Semi-Slav Defense": "Полуславянская защита",
    "King's Indian Defense": "Староиндийская защита",
    "Queen's Indian Defense": "Ферзево-индийская защита",
    "Nimzo-Indian Defense": "Нимцо-индийская защита",
    "Grünfeld Defense": "Защита Грюнфельда",
    "Dutch Defense": "Голландская защита",
    "Benoni Defense": "Защита Бенони",
    "Benko Gambit": "Гамбит Бенко",
    "Catalan Opening": "Каталонское начало",
    "London System": "Лондонская система",
    "English Opening": "Английское начало",
    "Réti Opening": "Дебют Рети",
    "Bird Opening": "Дебют Бёрда",
    "Polish Opening": "Польское начало",
    "King's Pawn Game": "Дебют королевской пешки",
    "Queen's Pawn Game": "Дебют ферзевой пешки",
    "Petrov's Defense": "Защита Петрова",
    "Philidor Defense": "Защита Филидора",
    "Englund Gambit": "Гамбит Энглунда",
    "Blackmar-Diemer Gambit": "Гамбит Блэкмара — Димера",
}

TERM_REPLACEMENTS = [
    ("Countergambit", "контргамбит"), ("Gambit Accepted", "принятый гамбит"),
    ("Gambit Declined", "отказанный гамбит"), ("Main Line", "главная линия"),
    ("Exchange Variation", "разменный вариант"), ("Classical Variation", "классический вариант"),
    ("Modern Variation", "современный вариант"), ("Advance Variation", "вариант с продвижением"),
    ("Variation", "вариант"), ("Defense", "защита"), ("Defence", "защита"),
    ("Attack", "атака"), ("Gambit", "гамбит"), ("Opening", "дебют"),
    ("System", "система"), ("Game", "партия"),
]

THEME_RU = {
    "advancedPawn": ("Продвинутая пешка", "Найди, как использовать далеко продвинутую пешку."),
    "advantage": ("Получить преимущество", "Найди точный ход, который даёт решающее преимущество."),
    "anastasiaMate": ("Мат Анастасии", "Распознай матовую сеть ладьи/ферзя и коня."),
    "arabianMate": ("Арабский мат", "Используй связку ладьи и коня у края доски."),
    "attackingF2F7": ("Атака f2 / f7", "Используй уязвимость пешки возле короля."),
    "attraction": ("Завлечение", "Заставь фигуру соперника перейти на неудобное поле."),
    "backRankMate": ("Мат по последней горизонтали", "Используй запертого собственными пешками короля."),
    "capturingDefender": ("Уничтожение защитника", "Убери фигуру, которая держит ключевую защиту."),
    "clearance": ("Освобождение линии", "Освободи поле, вертикаль или диагональ для следующего удара."),
    "crushing": ("Решающая тактика", "Накажи серьёзную ошибку соперника."),
    "defensiveMove": ("Точная защита", "Найди ход, который не даёт позиции развалиться."),
    "deflection": ("Отвлечение", "Отвлеки защитника от его главной обязанности."),
    "discoveredAttack": ("Вскрытое нападение", "Отойди одной фигурой и открой атаку другой."),
    "discoveredCheck": ("Вскрытый шах", "Открой линию шаха скрытой фигурой."),
    "doubleCheck": ("Двойной шах", "Создай шах сразу двумя фигурами."),
    "endgame": ("Тактика в эндшпиле", "Найди точное решение в упрощённой позиции."),
    "exposedKing": ("Открытый король", "Используй недостаток защитников вокруг короля."),
    "fork": ("Вилка", "Атакуй две или больше целей одним ходом."),
    "hangingPiece": ("Висящая фигура", "Найди фигуру без достаточной защиты."),
    "interference": ("Перекрытие", "Разорви связь между фигурами соперника."),
    "intermezzo": ("Промежуточный ход", "Вместо ожидаемого ответа вставь более сильную угрозу."),
    "kingsideAttack": ("Атака на королевском фланге", "Найди точный удар по рокированному королю."),
    "mate": ("Матовая комбинация", "Найди форсированную матовую последовательность."),
    "mateIn1": ("Мат в 1", "Поставь мат одним ходом."),
    "mateIn2": ("Мат в 2", "Найди форсированный мат за два своих хода."),
    "mateIn3": ("Мат в 3", "Рассчитай матовую последовательность на три своих хода."),
    "mateIn4": ("Мат в 4", "Рассчитай длинную матовую последовательность."),
    "middlegame": ("Тактика миттельшпиля", "Найди лучший тактический ход в середине партии."),
    "opening": ("Тактика в дебюте", "Найди тактический ресурс в ранней стадии партии."),
    "pawnEndgame": ("Пешечный эндшпиль", "Рассчитай королей, пешки и превращение."),
    "pin": ("Связка", "Используй фигуру, которая не может уйти без большей потери."),
    "promotion": ("Превращение пешки", "Проведи пешку и выбери правильное превращение."),
    "queenEndgame": ("Ферзевый эндшпиль", "Найди точную игру ферзём в эндшпиле."),
    "queensideAttack": ("Атака на ферзевом фланге", "Найди удар по королю после длинной рокировки."),
    "quietMove": ("Тихий ход", "Найди нефорсированный на вид ход со скрытой угрозой."),
    "rookEndgame": ("Ладейный эндшпиль", "Найди точную игру ладьями и пешками."),
    "sacrifice": ("Жертва", "Отдай материал ради форсированной выгоды."),
    "skewer": ("Рентген / шпажка", "Атакуй дорогую фигуру так, чтобы забрать стоящую за ней."),
    "smotheredMate": ("Спёртый мат", "Поставь мат конём королю, запертому своими фигурами."),
    "trappedPiece": ("Ловля фигуры", "Найди способ поймать фигуру без безопасных полей."),
    "underPromotion": ("Слабое превращение", "Преврати пешку не в ферзя, если это точнее."),
    "xRayAttack": ("Рентген", "Используй атаку сквозь фигуру соперника."),
    "zugzwang": ("Цугцванг", "Передай ход сопернику так, чтобы любой ответ ухудшал его позицию."),
    "mix": ("Смешанная тренировка", "Неизвестная тема: сначала сам определи, что происходит в позиции."),
}


def _translate_name(name: str) -> str:
    family, *rest = name.split(":", 1)
    ru = FAMILY_RU.get(family.strip(), family.strip())
    if rest:
        variation = rest[0].strip()
        for en, rr in TERM_REPLACEMENTS:
            variation = variation.replace(en, rr)
        return f"{ru}: {variation}"
    if ru == family:
        for en, rr in TERM_REPLACEMENTS:
            ru = ru.replace(en, rr)
    return ru


def _pgn_to_uci(pgn_text: str):
    game = chess.pgn.read_game(io.StringIO(pgn_text))
    if not game:
        return []
    return [m.uci() for m in game.mainline_moves()]


def _opening_meta(name: str):
    low = name.lower()
    if "gambit" in low:
        return ["атакующий", "гамбит"], 4, "Если хочется инициативы и ты готов временно отдать материал ради темпов.", "Идея гамбита — ускорить развитие, вскрыть линии и заставить соперника решать конкретные задачи."
    if "defense" in low or "defence" in low:
        return ["защита", "контригра"], 3, "Используй за чёрных, когда возникает эта структура и тебе подходит её тип контригры.", "Защита определяет способ борьбы чёрных с центром белых и типичный план развития."
    if "attack" in low:
        return ["атакующий", "активный"], 3, "Если хочешь получить активную расстановку и ранние конкретные угрозы.", "Расстановка направлена на инициативу и давление на конкретный участок доски."
    if "system" in low:
        return ["системный", "позиционный"], 2, "Если хочется повторяемой расстановки и понятного плана против разных ответов.", "Система строится вокруг устойчивой схемы развития, а не запоминания одной форсированной линии."
    return ["универсальный"], 3, "Выбирай, если тебе комфортна возникающая пешечная структура и типичные планы этой позиции.", "Главная цель дебюта — получить гармоничное развитие, безопасность короля и понятный переход в миттельшпиль."

_openings_cache = None
_openings_lock = asyncio.Lock()

async def load_lichess_openings():
    global _openings_cache
    if _openings_cache is not None:
        return _openings_cache
    async with _openings_lock:
        if _openings_cache is not None:
            return _openings_cache
        rows = []
        headers = {"User-Agent": "ChessCoachRU/1.3 educational project"}
        async with httpx.AsyncClient(timeout=20, headers=headers, follow_redirects=True) as client:
            responses = await asyncio.gather(*[client.get(url) for url in LICHESS_OPENING_URLS], return_exceptions=True)
        for response in responses:
            if isinstance(response, Exception) or response.status_code != 200:
                continue
            reader = csv.DictReader(io.StringIO(response.text), delimiter="\t")
            for row in reader:
                try:
                    uci = _pgn_to_uci(row["pgn"])
                    style, difficulty, when, why = _opening_meta(row["name"])
                    rows.append({
                        "eco": row["eco"], "name_ru": _translate_name(row["name"]), "name_en": row["name"],
                        "moves": row["pgn"], "pgn": row["pgn"], "line_uci": uci, "side": "Обе",
                        "style": style, "difficulty": difficulty, "theory": min(5, max(1, len(uci)//3)),
                        "elo_min": 500 if len(uci) <= 6 else 800,
                        "when": when, "why": why,
                        "plan_white": ["Развивай фигуры по смыслу позиции", "Обеспечь безопасность короля", "Подготовь тематический пешечный прорыв"],
                        "plan_black": ["Не отставай в развитии", "Бей по центру в подходящий момент", "Ищи активную контригру"],
                        "next": [], "source": "Lichess chess-openings (CC0)",
                    })
                except Exception:
                    continue
        _openings_cache = rows
        return rows


def _board_from_puzzle_payload(data: dict):
    game_data = data.get("game", {})
    puzzle = data.get("puzzle", {})
    pgn_text = game_data.get("pgn", "")
    solution = puzzle.get("solution", [])
    initial_ply = int(puzzle.get("initialPly", 0))
    game = chess.pgn.read_game(io.StringIO(pgn_text))
    if not game:
        raise ValueError("Lichess вернул задачу без корректной партии")
    moves = list(game.mainline_moves())
    for shift in (0, 1, -1):
        count = max(0, min(len(moves), initial_ply + shift))
        board = game.board()
        for m in moves[:count]:
            board.push(m)
        if solution:
            try:
                if chess.Move.from_uci(solution[0]) in board.legal_moves:
                    return board, solution
            except Exception:
                pass
    # Последний fallback: ищем ближайшую позицию, где первый ход решения легален.
    if solution:
        target = chess.Move.from_uci(solution[0])
        for count in range(max(0, initial_ply - 3), min(len(moves), initial_ply + 4) + 1):
            board = game.board()
            for m in moves[:count]: board.push(m)
            if target in board.legal_moves:
                return board, solution
    raise ValueError("Не удалось восстановить позицию задачи")

async def fetch_lichess_puzzle(angle: str = "mix", difficulty: str = "normal", color: str | None = None):
    params = {"angle": angle, "difficulty": difficulty}
    if color in ("white", "black"):
        params["color"] = color
    headers = {"Accept": "application/json", "User-Agent": "ChessCoachRU/1.3 educational project"}
    async with httpx.AsyncClient(timeout=15, headers=headers, follow_redirects=True) as client:
        response = await client.get("https://lichess.org/api/puzzle/next", params=params)
        response.raise_for_status()
        data = response.json()
    board, solution = _board_from_puzzle_payload(data)
    themes = data.get("puzzle", {}).get("themes", [])
    primary = angle if angle in THEME_RU else next((t for t in themes if t in THEME_RU), "mix")
    title, prompt = THEME_RU.get(primary, THEME_RU["mix"])
    return {
        "id": data.get("puzzle", {}).get("id"),
        "category": title, "theme": primary, "themes": themes,
        "title": title, "prompt": prompt,
        "fen": board.fen(), "solution_uci": solution,
        "rating": data.get("puzzle", {}).get("rating"),
        "plays": data.get("puzzle", {}).get("plays"),
        "source": "Lichess puzzles — public domain",
    }


def lesson_catalog():
    order = [
        ("Мат", ["mateIn1","mateIn2","mateIn3","backRankMate","smotheredMate","anastasiaMate","arabianMate"]),
        ("Тактика", ["hangingPiece","fork","pin","skewer","discoveredAttack","discoveredCheck","doubleCheck","xRayAttack","intermezzo","interference","capturingDefender","deflection","attraction","clearance","trappedPiece","sacrifice","quietMove"]),
        ("Атака и защита", ["attackingF2F7","exposedKing","kingsideAttack","queensideAttack","defensiveMove","advantage","crushing"]),
        ("Эндшпиль", ["endgame","pawnEndgame","rookEndgame","queenEndgame","promotion","underPromotion","advancedPawn","zugzwang"]),
        ("Практика", ["opening","middlegame","mix"]),
    ]
    lessons=[]
    i=1
    for section, themes in order:
        for theme in themes:
            title, prompt = THEME_RU[theme]
            lessons.append({
                "id": f"interactive-{theme}", "section": section, "title": title,
                "level": "адаптивный", "summary": prompt, "theme": theme,
                "exercise_count": 5, "format": "board", "source": "Lichess puzzles — public domain",
                "order": i,
            })
            i += 1
    return lessons
