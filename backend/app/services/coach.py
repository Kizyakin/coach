import chess
from app.services.chess_logic import tactical_summary
from app.services.engine import engine_service

PIECE_RU = {
    chess.PAWN: "пешку", chess.KNIGHT: "коня", chess.BISHOP: "слона",
    chess.ROOK: "ладью", chess.QUEEN: "ферзя", chess.KING: "короля"
}

def _move_reason(board: chess.Board, move: chess.Move) -> str:
    piece = board.piece_at(move.from_square)
    if board.gives_check(move):
        if board.is_capture(move): return "Форсированный шах со взятием: сопернику приходится реагировать."
        return "Форсированный шах: ограничивает выбор ответов соперника."
    if board.is_capture(move):
        victim = board.piece_at(move.to_square)
        return f"Взятие {PIECE_RU.get(victim.piece_type, 'фигуры') if victim else 'фигуры'} с конкретной материальной выгодой или упрощением."
    if piece and piece.piece_type in (chess.KNIGHT, chess.BISHOP) and board.fullmove_number <= 12:
        return "Развивает лёгкую фигуру и улучшает координацию."
    if piece and piece.piece_type == chess.KING and abs(move.to_square - move.from_square) == 2:
        return "Рокировка: уводит короля из центра и подключает ладью."
    center = {chess.D4, chess.E4, chess.D5, chess.E5}
    if move.to_square in center:
        return "Усиливает контроль центра и активность фигур."
    return "Сильный ход движка: улучшает позицию и ограничивает контригру соперника."

def explain_position(fen: str, depth: int = 12):
    board = chess.Board(fen)
    facts = tactical_summary(board)
    lines = engine_service.analyze(fen, depth=depth, multipv=3)
    best = lines[0] if lines else None
    hints = []
    priority = "план"

    if board.is_check():
        priority = "защита короля"
        hints.append("Ты под шахом. Сначала сравни все легальные ответы: уход короля, взятие атакующей фигуры и блокировку.")
    elif best and best.get("mate") is not None and best["mate"] > 0:
        priority = "матовая атака"
        hints.append(f"Есть форсированный мат. Первый ход комбинации: {best.get('line_san',[None])[0] or 'смотри кандидаты ниже'}.")
    elif facts["opponent_hanging"]:
        priority = "тактика"
        squares = ", ".join(x["square"] for x in facts["opponent_hanging"][:3])
        hints.append(f"У соперника есть незащищённая фигура ({squares}). Сначала проверь безопасное взятие.")
    elif facts["my_hanging"]:
        priority = "защита фигуры"
        squares = ", ".join(x["square"] for x in facts["my_hanging"][:3])
        hints.append(f"Твоя фигура висит на {squares}. Проверь, можно ли её спасти, разменять или создать более сильную форсированную угрозу.")
    elif facts["material"] >= 3:
        priority = "реализация преимущества"
        hints.append("Ты впереди по материалу. Предпочитай безопасные размены фигур и особенно ферзей, если они не отдают часть преимущества.")
    elif facts["phase"] == "дебют" and facts["development"]["undeveloped"]:
        priority = "развитие"
        hints.append("Форсированной тактики не видно. Закончи развитие, рокируй и только потом начинай долгий план.")
    else:
        hints.append("Форсированной тактики не видно. Сравни три лучших кандидатных хода ниже и выбери тот, который улучшает худшую фигуру или создаёт конкретную угрозу.")

    candidates=[]
    for i,line in enumerate(lines[:3]):
        uci=line.get("move_uci")
        if not uci: continue
        move=chess.Move.from_uci(uci)
        try: san=board.san(move)
        except Exception: san=uci
        candidates.append({
            "rank": i+1,
            "move_uci": uci,
            "move_san": san,
            "score_cp": line.get("score_cp"),
            "mate": line.get("mate"),
            "line_san": line.get("line_san",[]),
            "reason": _move_reason(board, move),
        })

    return {
        "facts": facts,
        "engine": lines,
        "priority": priority,
        "hints": hints,
        "best_move": candidates[0] if candidates else None,
        "candidates": candidates,
        "side_to_move": "Белые" if board.turn else "Чёрные",
    }
