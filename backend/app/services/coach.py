import chess
from app.services.chess_logic import tactical_summary
from app.services.engine import engine_service

ERROR_LABELS = {
    "missed_mate":"пропущенный мат",
    "hanging_piece":"фигура оставлена под боем",
    "ignored_threat":"не замечена угроза",
    "bad_trade":"невыгодный размен",
    "opening":"ошибка в дебюте",
}

def explain_position(fen: str, depth: int = 12):
    board = chess.Board(fen)
    facts = tactical_summary(board)
    lines = engine_service.analyze(fen, depth=depth, multipv=3)
    best = lines[0] if lines else None
    hints = []
    priority = "план"

    if board.is_check():
        priority = "защита короля"
        hints.append("Ты под шахом: сначала найди все легальные способы убрать шах.")
    elif best and best.get("mate") is not None and best["mate"] > 0:
        priority = "матовая атака"
        hints += ["У тебя есть форсированная матовая идея.", "Начни с проверки всех шахов."]
    elif facts["opponent_hanging"]:
        priority = "тактика"
        hints.append("У соперника есть фигура без достаточной защиты. Проверь безопасные взятия.")
    elif facts["my_hanging"]:
        priority = "защита фигуры"
        hints.append("Одна из твоих фигур висит. Перед атакой реши, нужно ли её спасти или можно создать более сильную угрозу.")
    elif facts["material"] >= 3:
        priority = "реализация преимущества"
        hints.append("Ты впереди по материалу. Ищи выгодные размены фигур, особенно ферзей, и уменьши контригру соперника.")
    elif facts["phase"] == "дебют" and facts["development"]["undeveloped"]:
        priority = "развитие"
        hints.append("Тактики не доминируют: закончи развитие и позаботься о безопасности короля.")
    else:
        hints.append("Проверь шахи, взятия и прямые угрозы. Если форсированных ходов нет — улучши худшую фигуру.")

    return {"facts": facts, "engine": lines, "priority": priority, "hints": hints}
