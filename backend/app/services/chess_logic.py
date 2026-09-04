import chess

PIECE_VALUES = {chess.PAWN:1, chess.KNIGHT:3, chess.BISHOP:3, chess.ROOK:5, chess.QUEEN:9, chess.KING:0}

def material_score(board: chess.Board, color: chess.Color) -> int:
    mine = sum(len(board.pieces(pt, color)) * v for pt, v in PIECE_VALUES.items())
    theirs = sum(len(board.pieces(pt, not color)) * v for pt, v in PIECE_VALUES.items())
    return mine - theirs

def hanging_pieces(board: chess.Board, color: chess.Color):
    result = []
    for sq in chess.SQUARES:
        piece = board.piece_at(sq)
        if not piece or piece.color != color or piece.piece_type == chess.KING:
            continue
        attackers = board.attackers(not color, sq)
        defenders = board.attackers(color, sq)
        if attackers and not defenders:
            result.append({"square": chess.square_name(sq), "piece": piece.symbol(), "attackers": len(attackers)})
    return result

def legal_forcing_moves(board: chess.Board):
    checks, captures = [], []
    for move in board.legal_moves:
        if board.gives_check(move): checks.append(move.uci())
        if board.is_capture(move): captures.append(move.uci())
    return checks, captures

def development_status(board: chess.Board, color: chess.Color):
    home = {chess.WHITE: [chess.B1,chess.G1,chess.C1,chess.F1], chess.BLACK:[chess.B8,chess.G8,chess.C8,chess.F8]}[color]
    undeveloped = []
    for sq in home:
        p = board.piece_at(sq)
        if p and p.color == color and p.piece_type in (chess.KNIGHT, chess.BISHOP):
            undeveloped.append(chess.square_name(sq))
    king_sq = board.king(color)
    castled = king_sq in ([chess.G1,chess.C1] if color else [chess.G8,chess.C8])
    return {"undeveloped": undeveloped, "castled": castled}

def phase(board: chess.Board):
    queens = len(board.pieces(chess.QUEEN, chess.WHITE)) + len(board.pieces(chess.QUEEN, chess.BLACK))
    pieces = sum(len(board.pieces(pt, c)) for pt in [chess.KNIGHT,chess.BISHOP,chess.ROOK,chess.QUEEN] for c in [chess.WHITE,chess.BLACK])
    if board.fullmove_number <= 12 and pieces >= 10:
        return "дебют"
    if queens == 0 or pieces <= 6:
        return "эндшпиль"
    return "миттельшпиль"

def tactical_summary(board: chess.Board):
    side = board.turn
    checks, captures = legal_forcing_moves(board)
    return {
        "side": "белые" if side else "чёрные",
        "in_check": board.is_check(),
        "checkmate": board.is_checkmate(),
        "stalemate": board.is_stalemate(),
        "checks": checks,
        "captures": captures,
        "my_hanging": hanging_pieces(board, side),
        "opponent_hanging": hanging_pieces(board, not side),
        "material": material_score(board, side),
        "development": development_status(board, side),
        "phase": phase(board),
    }
