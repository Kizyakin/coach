from __future__ import annotations

from collections import OrderedDict
import time

import chess

from app.services.chess_logic import tactical_summary
from app.services.engine import engine_service
from app.services.notation import move_ru
from app.services.master_library import master_library

PIECE_RU = {
    chess.PAWN: "пешку",
    chess.KNIGHT: "коня",
    chess.BISHOP: "слона",
    chess.ROOK: "ладью",
    chess.QUEEN: "ферзя",
    chess.KING: "короля",
}
VALUE = {chess.PAWN: 1, chess.KNIGHT: 3, chess.BISHOP: 3, chess.ROOK: 5, chess.QUEEN: 9, chess.KING: 0}

# Small in-memory hot-position cache. Useful when the user requests the same
# position again, changes notation, or returns to a previous move.
_COACH_CACHE: OrderedDict[tuple, dict] = OrderedDict()
_CACHE_LIMIT = 160


def board_from_history(fen: str, history_uci: list[str] | None):
    if history_uci:
        board = chess.Board()
        try:
            for u in history_uci:
                m = chess.Move.from_uci(u)
                if m not in board.legal_moves:
                    raise ValueError
                board.push(m)
            return board
        except Exception:
            pass
    return chess.Board(fen)


def _draw_flags(board: chess.Board, move: chess.Move):
    b = board.copy(stack=True)
    b.push(move)
    return {
        "stalemate": b.is_stalemate(),
        "threefold": b.can_claim_threefold_repetition(),
        "fifty": b.can_claim_fifty_moves(),
        "insufficient": b.is_insufficient_material(),
    }


def _material(board, color):
    return sum(len(board.pieces(pt, color)) * VALUE[pt] for pt in VALUE)


def _pv_material(board: chess.Board, pv_uci: list[str]):
    side = board.turn
    start = _material(board, side) - _material(board, not side)
    b = board.copy()
    for u in pv_uci[:8]:
        try:
            m = chess.Move.from_uci(u)
            if m not in b.legal_moves:
                break
            b.push(m)
        except Exception:
            break
    end = _material(b, side) - _material(b, not side)
    return end - start


def _king_attack(board: chess.Board, move: chess.Move):
    b = board.copy()
    side = board.turn
    b.push(move)
    enemy_king = b.king(not side)
    if enemy_king is None:
        return 0
    ring = chess.SquareSet(chess.BB_KING_ATTACKS[enemy_king] | chess.BB_SQUARES[enemy_king])
    attacks = 0
    pieces = b.pieces(chess.QUEEN, side) | b.pieces(chess.ROOK, side) | b.pieces(chess.BISHOP, side) | b.pieces(chess.KNIGHT, side)
    for sq in pieces:
        attacks += len(b.attacks(sq) & ring)
    return attacks


def _reason(board: chess.Board, move: chess.Move, draw: dict, mate=None, material_line=0) -> str:
    if draw["stalemate"]:
        return "Этот ход приводит к пату — избегай его, если позиция выиграна."
    if draw["threefold"]:
        return "Этот ход ведёт к повторению позиции. При преимуществе лучше продолжать игру на победу."
    if mate and mate > 0:
        extra = "" if material_line >= 0 else f" Комбинация временно отдаёт около {abs(material_line)} ед. материала, но форсированный мат важнее."
        return f"Форсированный мат примерно за {mate} ход(а/ов). Это главный приоритет позиции.{extra}"
    piece = board.piece_at(move.from_square)
    if board.gives_check(move):
        return "Форсированный шах сужает ответы соперника и поддерживает инициативу."
    if board.is_capture(move):
        victim = board.piece_at(move.to_square)
        return f"Конкретное взятие {PIECE_RU.get(victim.piece_type, 'фигуры') if victim else 'фигуры'}; ход улучшает материальный или тактический баланс."
    if _king_attack(board, move) >= 2:
        return "Ход усиливает давление на короля и подключает фигуры к атаке."
    if board.is_castling(move):
        return "Рокировка уводит короля из центра и подключает ладью."
    if piece and piece.piece_type in (chess.KNIGHT, chess.BISHOP) and board.fullmove_number <= 12:
        return "Развивает лёгкую фигуру и улучшает координацию."
    if move.to_square in {chess.D4, chess.E4, chess.D5, chess.E5}:
        return "Усиливает контроль центра и активность фигур."
    return "Сильный практический ход: сохраняет оценку и улучшает координацию без лишнего риска."


def _rank_candidates(board, annotated):
    if not annotated:
        return []

    # Forced mate outranks material. Among mating lines choose the shortest;
    # if mate length is equal, prefer the line that sacrifices less material.
    mates = []
    for line, move, flags in annotated:
        m = line.get("mate")
        if m is not None and m > 0 and not flags["stalemate"]:
            mat = _pv_material(board, line.get("pv_uci", []))
            mates.append((m, -mat, line, move, flags))
    if mates:
        mates.sort(key=lambda x: (x[0], x[1]))
        return [(x[2], x[3], x[4]) for x in mates]

    top_cp = annotated[0][0].get("score_cp") or 0
    scored = []
    for line, move, flags in annotated:
        cp = line.get("score_cp") or -100000
        # Do not throw away a clearly stronger objective move just to attack.
        if cp < top_cp - 90:
            continue
        mat = _pv_material(board, line.get("pv_uci", []))
        attack = _king_attack(board, move)
        forcing = (30 if board.gives_check(move) else 0) + (16 if board.is_capture(move) else 0)
        sacrifice_penalty = max(0, -mat) * 8
        practical = cp + attack * 7 + forcing - sacrifice_penalty
        scored.append((practical, line, move, flags))
    scored.sort(key=lambda x: x[0], reverse=True)
    return [(x[1], x[2], x[3]) for x in scored] or annotated


def _cache_get(key):
    value = _COACH_CACHE.get(key)
    if value is not None:
        _COACH_CACHE.move_to_end(key)
    return value


def _cache_put(key, value):
    _COACH_CACHE[key] = value
    _COACH_CACHE.move_to_end(key)
    while len(_COACH_CACHE) > _CACHE_LIMIT:
        _COACH_CACHE.popitem(last=False)


def explain_position(
    fen: str,
    depth: int | None = None,
    history_uci: list[str] | None = None,
    speed: str = "fast",
):
    started = time.perf_counter()
    board = board_from_history(fen, history_uci)
    history_key = tuple(history_uci or ())
    cache_key = (board.fen(), history_key, speed, depth if speed != "fast" else None)
    cached = _cache_get(cache_key)
    if cached is not None:
        out = dict(cached)
        out["performance"] = {**out.get("performance", {}), "cache": True, "total_ms": round((time.perf_counter() - started) * 1000)}
        return out

    facts = tactical_summary(board)
    multipv = 3 if speed == "fast" else 5 if speed == "balanced" else 8
    engine_started = time.perf_counter()
    raw = engine_service.analyze_board(board, depth=depth, multipv=multipv, speed=speed)
    engine_ms = round((time.perf_counter() - engine_started) * 1000)

    annotated = []
    for line in raw:
        u = line.get("move_uci")
        if not u:
            continue
        move = chess.Move.from_uci(u)
        annotated.append((line, move, _draw_flags(board, move)))

    current_cp = annotated[0][0].get("score_cp") if annotated else None
    avoid_draw = current_cp is None or current_cp >= -50
    if avoid_draw:
        safe = [x for x in annotated if not (x[2]["stalemate"] or x[2]["threefold"] or x[2]["fifty"])]
        if safe:
            annotated = safe
    chosen = _rank_candidates(board, annotated)[:3]

    hints = []
    priority = "план"
    if board.is_check():
        priority = "защита короля"
        hints.append("Ты под шахом: сначала перечисли все легальные ответы.")
    elif chosen and chosen[0][0].get("mate") and chosen[0][0]["mate"] > 0:
        priority = "форсированный мат"
        hints.append("Есть форсированный мат. Coach выбирает самый быстрый мат, а материал становится вторичным.")
    elif facts["opponent_hanging"]:
        priority = "тактика"
        hints.append("У соперника есть незащищённая фигура. Сравни взятие с более сильными шахами и угрозами.")
    elif facts["my_hanging"]:
        priority = "защита фигуры"
        hints.append("Твоя фигура висит. Но сначала проверь, нет ли у тебя форсированной атаки сильнее обычной защиты.")
    elif facts["material"] >= 3:
        priority = "реализация преимущества"
        hints.append("Ты впереди по материалу: упрощай, не отдавай инициативу и не допускай пат/повторение.")
    elif facts["phase"] == "дебют" and facts["development"]["undeveloped"]:
        priority = "развитие"
        hints.append("Форсированной тактики нет: закончи развитие и подготовь активный план.")
    else:
        hints.append("Ищи форсированные ходы: мат → шах → взятие → угроза. Затем сравни позиционные планы.")

    master_started = time.perf_counter()
    master = master_library.find_patterns(board, 6 if speed == "fast" else 10, fast=(speed == "fast"))
    master_ms = round((time.perf_counter() - master_started) * 1000)
    if master.get("available") and master.get("plans"):
        top = master["plans"][0]["name"]
        names = ", ".join(master.get("top_players", [])[:3])
        hints.append(f"Мастерская практика: в похожих структурах часто встречается план «{top}». Примеры: {names}.")

    candidates = []
    for i, (line, move, flags) in enumerate(chosen):
        ml = _pv_material(board, line.get("pv_uci", []))
        candidates.append(
            {
                "rank": i + 1,
                "move_uci": move.uci(),
                "move_san": board.san(move),
                "move_ru": move_ru(board, move),
                "score_cp": line.get("score_cp"),
                "mate": line.get("mate"),
                "line_san": line.get("line_san", []),
                "line_ru": line.get("line_ru", []),
                "reason": _reason(board, move, flags, line.get("mate"), ml),
                "draw_risk": flags,
                "material_line": ml,
                "attack_score": _king_attack(board, move),
            }
        )

    result = {
        "facts": facts,
        "engine": raw[:3],
        "priority": priority,
        "hints": hints,
        "best_move": candidates[0] if candidates else None,
        "candidates": candidates,
        "master_insight": master,
        "side_to_move": "Белые" if board.turn else "Чёрные",
        "draw_state": {
            "can_claim_threefold": board.can_claim_threefold_repetition(),
            "stalemate": board.is_stalemate(),
            "can_claim_fifty": board.can_claim_fifty_moves(),
        },
        "performance": {
            "mode": speed,
            "engine_ms": engine_ms,
            "master_ms": master_ms,
            "total_ms": round((time.perf_counter() - started) * 1000),
            "cache": False,
        },
    }
    _cache_put(cache_key, result)
    return result
