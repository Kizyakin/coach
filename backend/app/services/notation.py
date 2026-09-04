import chess

PIECE = {
    chess.PAWN: "Пешка", chess.KNIGHT: "Конь", chess.BISHOP: "Слон",
    chess.ROOK: "Ладья", chess.QUEEN: "Ферзь", chess.KING: "Король",
}
PROMO = {chess.QUEEN:"ферзь", chess.ROOK:"ладья", chess.BISHOP:"слон", chess.KNIGHT:"конь"}

def move_ru(board: chess.Board, move: chess.Move) -> str:
    if board.is_castling(move):
        label = "Рокировка 0-0" if chess.square_file(move.to_square) == 6 else "Рокировка 0-0-0"
    else:
        piece = board.piece_at(move.from_square)
        name = PIECE.get(piece.piece_type, "Фигура") if piece else "Фигура"
        capture = " × " if board.is_capture(move) else " → "
        label = f"{name}{capture}{chess.square_name(move.to_square)}"
        if move.promotion:
            label += f" = {PROMO.get(move.promotion, 'фигура')}"
    if board.gives_check(move):
        tmp = board.copy(); tmp.push(move)
        label += "#" if tmp.is_checkmate() else "+"
    return label

def line_ru(board: chess.Board, moves):
    tmp = board.copy(); out=[]
    for move in moves:
        try:
            out.append(move_ru(tmp, move)); tmp.push(move)
        except Exception:
            break
    return out
