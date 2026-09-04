import io, chess, chess.pgn
from app.services.engine import engine_service

def review_pgn(pgn: str, depth: int = 10):
    game = chess.pgn.read_game(io.StringIO(pgn))
    if not game:
        return {"error":"Не удалось прочитать партию"}
    board = game.board(); reviews=[]; previous_eval = 0
    ply = 0
    for move in game.mainline_moves():
        ply += 1
        san = board.san(move)
        before = engine_service.analyze(board.fen(), depth=depth, multipv=1)[0]
        mover = board.turn
        board.push(move)
        after = engine_service.analyze(board.fen(), depth=depth, multipv=1)[0]
        # after score is from next side's POV, flip to mover POV
        before_cp = before.get("score_cp") or 0
        after_cp = -(after.get("score_cp") or 0)
        loss = before_cp - after_cp
        if loss < 40: label = "хороший"
        elif loss < 90: label = "неточность"
        elif loss < 180: label = "ошибка"
        else: label = "грубая ошибка"
        reviews.append({"ply":ply,"move":san,"fen":board.fen(),"loss_cp":loss,"label":label,"best":before.get("line_san",[])[:3]})
        previous_eval = after_cp
    critical = sorted(reviews, key=lambda x:x["loss_cp"], reverse=True)[:5]
    return {"headers": dict(game.headers), "moves": reviews, "critical": critical}
