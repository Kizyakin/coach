import chess
from app.services.chess_logic import tactical_summary
from app.services.engine import engine_service
from app.services.notation import move_ru

PIECE_RU = {chess.PAWN:"пешку",chess.KNIGHT:"коня",chess.BISHOP:"слона",chess.ROOK:"ладью",chess.QUEEN:"ферзя",chess.KING:"короля"}

def board_from_history(fen: str, history_uci: list[str] | None):
    if history_uci:
        board=chess.Board()
        try:
            for u in history_uci:
                m=chess.Move.from_uci(u)
                if m not in board.legal_moves: raise ValueError
                board.push(m)
            return board
        except Exception:
            pass
    return chess.Board(fen)

def _draw_flags(board: chess.Board, move: chess.Move):
    b=board.copy(stack=True); b.push(move)
    return {
        "stalemate": b.is_stalemate(),
        "threefold": b.can_claim_threefold_repetition(),
        "fifty": b.can_claim_fifty_moves(),
        "insufficient": b.is_insufficient_material(),
    }

def _reason(board: chess.Board, move: chess.Move, draw: dict) -> str:
    if draw["stalemate"]: return "Этот ход приводит к пату — избегай его, если позиция выиграна."
    if draw["threefold"]: return "Этот ход позволяет заявить ничью троекратным повторением — при преимуществе лучше выбрать другой план."
    piece=board.piece_at(move.from_square)
    if board.gives_check(move): return "Шах заставляет соперника реагировать и сужает выбор ответов."
    if board.is_capture(move):
        victim=board.piece_at(move.to_square)
        return f"Конкретное взятие {PIECE_RU.get(victim.piece_type,'фигуры') if victim else 'фигуры'}; сначала проверь ответ соперника."
    if piece and piece.piece_type in (chess.KNIGHT,chess.BISHOP) and board.fullmove_number<=12: return "Развивает лёгкую фигуру и улучшает координацию."
    if board.is_castling(move): return "Рокировка уводит короля из центра и подключает ладью."
    if move.to_square in {chess.D4,chess.E4,chess.D5,chess.E5}: return "Усиливает контроль центра."
    return "Сильный конкретный ход: улучшает позицию без немедленной тактической уступки."

def explain_position(fen: str, depth: int = 12, history_uci: list[str] | None = None):
    board=board_from_history(fen,history_uci)
    facts=tactical_summary(board)
    raw=engine_service.analyze_board(board, depth=depth, multipv=8)
    annotated=[]
    for line in raw:
        u=line.get("move_uci")
        if not u: continue
        move=chess.Move.from_uci(u); flags=_draw_flags(board,move)
        annotated.append((line,move,flags))
    # Если мы не проигрываем, не советуем добровольную ничью/пат, когда есть нормальная альтернатива.
    current_cp=annotated[0][0].get("score_cp") if annotated else None
    avoid_draw=(current_cp is None or current_cp >= -50)
    safe=[x for x in annotated if not (x[2]["stalemate"] or x[2]["threefold"] or x[2]["fifty"])] if avoid_draw else annotated
    chosen=safe if safe else annotated
    chosen=chosen[:3]

    hints=[]; priority="план"
    if board.is_check(): priority="защита короля"; hints.append("Ты под шахом: сначала перечисли все легальные ответы на шах.")
    elif chosen and chosen[0][0].get("mate") and chosen[0][0]["mate"]>0: priority="матовая атака"; hints.append("Есть форсированный мат. Не переключайся на спокойный план.")
    elif facts["opponent_hanging"]: priority="тактика"; hints.append("У соперника есть незащищённая фигура. Проверь безопасное взятие до позиционного хода.")
    elif facts["my_hanging"]: priority="защита фигуры"; hints.append("Одна из твоих фигур висит. Спаси её, разменяй или найди более сильную форсированную угрозу.")
    elif facts["material"]>=3: priority="реализация преимущества"; hints.append("Ты впереди по материалу: уменьшай контригру, но не повторяй позицию и не создавай пат.")
    elif facts["phase"]=="дебют" and facts["development"]["undeveloped"]: priority="развитие"; hints.append("Форсированной тактики нет: закончи развитие и обеспечь безопасность короля.")
    else: hints.append("Сравни конкретные кандидатные ходы ниже. Начинай с шахов, взятий и угроз.")

    if any(x[2]["threefold"] for x in annotated[:3]): hints.append("Внимание: среди естественных ходов есть повторение позиции. При преимуществе Coach его отфильтровал.")
    if any(x[2]["stalemate"] for x in annotated[:5]): hints.append("Внимание: один из вариантов ведёт к пату. В выигранной позиции его нужно избегать.")

    candidates=[]
    for i,(line,move,flags) in enumerate(chosen):
        candidates.append({"rank":i+1,"move_uci":move.uci(),"move_san":board.san(move),"move_ru":move_ru(board,move),"score_cp":line.get("score_cp"),"mate":line.get("mate"),"line_san":line.get("line_san",[]),"line_ru":line.get("line_ru",[]),"reason":_reason(board,move,flags),"draw_risk":flags})
    return {"facts":facts,"engine":raw[:3],"priority":priority,"hints":hints,"best_move":candidates[0] if candidates else None,"candidates":candidates,"side_to_move":"Белые" if board.turn else "Чёрные","draw_state":{"can_claim_threefold":board.can_claim_threefold_repetition(),"stalemate":board.is_stalemate(),"can_claim_fifty":board.can_claim_fifty_moves()}}
