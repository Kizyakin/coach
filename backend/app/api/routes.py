from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field
import chess
from app.data.lessons import LESSONS
from app.data.openings import OPENINGS
from app.data.training import TRAINING_TASKS
from app.services.coach import explain_position
from app.services.engine import engine_service
from app.services.review import review_pgn
from app.services.external import chesscom_games, lichess_games

router = APIRouter(prefix="/api")

class FenRequest(BaseModel):
    fen: str
    depth: int = Field(12, ge=6, le=20)
    player_side: str | None = None

class MoveRequest(BaseModel):
    fen: str
    move_uci: str
    depth: int = Field(10, ge=6, le=18)

class ReviewRequest(BaseModel):
    pgn: str
    depth: int = Field(9, ge=6, le=14)

@router.get("/health")
def health(): return {"ok": True, "service":"Шахматный тренер"}

@router.get("/lessons")
def lessons(): return LESSONS

@router.get("/training")
def training(category: str | None = None):
    if not category: return TRAINING_TASKS
    return [t for t in TRAINING_TASKS if t["category"].lower() == category.lower()]

@router.get("/openings")
def openings(q: str | None = None):
    if not q: return OPENINGS
    qq=q.lower()
    return [o for o in OPENINGS if qq in o["name_ru"].lower() or qq in o["name_en"].lower() or qq in o["eco"].lower()]

@router.post("/coach/analyze")
def coach_analyze(req: FenRequest):
    try: chess.Board(req.fen)
    except Exception as e: raise HTTPException(400, f"Некорректный FEN: {e}")
    try: return explain_position(req.fen, req.depth)
    except FileNotFoundError: raise HTTPException(503, "Stockfish не найден на сервере")

@router.post("/engine/move")
def engine_move(req: FenRequest):
    try:
        board=chess.Board(req.fen)
        lines=engine_service.analyze(req.fen, req.depth, 1)
        if not lines or not lines[0]["move_uci"]: return {"game_over":True}
        move=chess.Move.from_uci(lines[0]["move_uci"])
        san=board.san(move); board.push(move)
        return {"move_uci":move.uci(),"move_san":san,"fen":board.fen(),"evaluation":lines[0]}
    except FileNotFoundError: raise HTTPException(503, "Stockfish не найден")
    except Exception as e: raise HTTPException(400, str(e))

@router.post("/move/preview")
def move_preview(req: MoveRequest):
    try:
        board=chess.Board(req.fen); before=engine_service.analyze(board.fen(), req.depth, 1)[0]
        move=chess.Move.from_uci(req.move_uci)
        if move not in board.legal_moves: raise HTTPException(400,"Недопустимый ход")
        san=board.san(move); mover=board.turn; board.push(move)
        after=engine_service.analyze(board.fen(), req.depth, 1)[0]
        loss=(before.get("score_cp") or 0) + (after.get("score_cp") or 0)
        if loss < 40: label="Хороший ход"
        elif loss < 90: label="Неточность"
        elif loss < 180: label="Ошибка"
        else: label="Грубая ошибка"
        return {"move":san,"label":label,"loss_cp":loss,"best_line":before.get("line_san",[])[:4],"fen_after":board.fen()}
    except HTTPException: raise
    except Exception as e: raise HTTPException(400,str(e))

@router.post("/review")
def review(req: ReviewRequest):
    try: return review_pgn(req.pgn, req.depth)
    except FileNotFoundError: raise HTTPException(503,"Stockfish не найден")

@router.get("/integrations/chesscom/{username}")
async def sync_chesscom(username: str, limit: int=20):
    try: return await chesscom_games(username, min(max(limit,1),100))
    except Exception as e: raise HTTPException(502, f"Chess.com: {e}")

@router.get("/integrations/lichess/{username}")
async def sync_lichess(username: str, limit: int=20):
    try: return await lichess_games(username, min(max(limit,1),100))
    except Exception as e: raise HTTPException(502, f"Lichess: {e}")
