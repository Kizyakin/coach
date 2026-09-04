from fastapi import APIRouter, HTTPException, Query
from pydantic import BaseModel, Field
import chess
from app.data.openings import OPENINGS as FALLBACK_OPENINGS
from app.data.training import TRAINING_TASKS
from app.services.coach import explain_position, board_from_history
from app.services.engine import engine_service
from app.services.notation import move_ru
from app.services.review import review_pgn
from app.services.external import chesscom_games, lichess_games
from app.services.open_data import load_lichess_openings, fetch_lichess_puzzle, lesson_catalog, THEME_RU

router=APIRouter(prefix="/api")

class FenRequest(BaseModel):
    fen:str
    depth:int=Field(12,ge=6,le=20)
    player_side:str|None=None
    history_uci:list[str]=[]
class MoveRequest(BaseModel):
    fen:str; move_uci:str; depth:int=Field(10,ge=6,le=18)
class ReviewRequest(BaseModel):
    pgn:str; depth:int=Field(9,ge=6,le=14)

@router.get('/health')
def health(): return {'ok':True,'service':'Шахматный тренер','version':'1.3'}

@router.get('/lessons')
def lessons(): return lesson_catalog()

@router.get('/training')
def training(category:str|None=None):
    if not category:return TRAINING_TASKS
    return [t for t in TRAINING_TASKS if t['category'].lower()==category.lower()]

@router.get('/training/themes')
def training_themes():
    return [{'id':k,'name':v[0],'description':v[1]} for k,v in THEME_RU.items()]

@router.get('/training/next')
async def training_next(theme:str='mix',difficulty:str=Query('normal',pattern='^(easiest|easier|normal|harder|hardest)$'),color:str|None=None):
    try:return await fetch_lichess_puzzle(theme,difficulty,color)
    except Exception as e: raise HTTPException(502,f'Lichess puzzle API: {e}')

@router.get('/openings')
async def openings(q:str|None=None,limit:int=Query(5000,ge=1,le=10000)):
    try: data=await load_lichess_openings()
    except Exception: data=[]
    if not data:data=FALLBACK_OPENINGS
    if q:
        qq=q.lower();data=[o for o in data if qq in o['name_ru'].lower() or qq in o['name_en'].lower() or qq in o['eco'].lower()]
    return data[:limit]

@router.post('/coach/analyze')
def coach_analyze(req:FenRequest):
    try: chess.Board(req.fen)
    except Exception as e: raise HTTPException(400,f'Некорректный FEN: {e}')
    try:return explain_position(req.fen,req.depth,req.history_uci)
    except FileNotFoundError:raise HTTPException(503,'Stockfish не найден на сервере')

@router.post('/engine/move')
def engine_move(req:FenRequest):
    try:
        board=board_from_history(req.fen,req.history_uci)
        lines=engine_service.analyze_board(board,req.depth,8)
        if not lines:return {'game_over':True}
        candidates=[]
        for line in lines:
            if not line.get('move_uci'):continue
            m=chess.Move.from_uci(line['move_uci']); b=board.copy(stack=True); b.push(m)
            draw=b.is_stalemate() or b.can_claim_threefold_repetition() or b.can_claim_fifty_moves()
            candidates.append((line,m,draw))
        cp=candidates[0][0].get('score_cp') if candidates else None
        if cp is None or cp>=-50:
            safe=[x for x in candidates if not x[2]]
            if safe:candidates=safe
        if not candidates:return {'game_over':True}
        line,move,_=candidates[0]
        san=board.san(move); ru=move_ru(board,move);board.push(move)
        return {'move_uci':move.uci(),'move_san':san,'move_ru':ru,'fen':board.fen(),'evaluation':line,'game_over':board.is_game_over(claim_draw=True),'outcome':str(board.outcome(claim_draw=True)) if board.is_game_over(claim_draw=True) else None}
    except FileNotFoundError:raise HTTPException(503,'Stockfish не найден')
    except Exception as e:raise HTTPException(400,str(e))

@router.post('/move/preview')
def move_preview(req:MoveRequest):
    try:
        board=chess.Board(req.fen); before=engine_service.analyze_board(board,req.depth,1)[0]
        move=chess.Move.from_uci(req.move_uci)
        if move not in board.legal_moves:raise HTTPException(400,'Недопустимый ход')
        san=board.san(move); ru=move_ru(board,move);board.push(move);after=engine_service.analyze_board(board,req.depth,1)[0]
        loss=(before.get('score_cp') or 0)+(after.get('score_cp') or 0)
        label='Хороший ход' if loss<40 else 'Неточность' if loss<90 else 'Ошибка' if loss<180 else 'Грубая ошибка'
        return {'move':san,'move_ru':ru,'label':label,'loss_cp':loss,'best_line':before.get('line_san',[])[:4],'fen_after':board.fen()}
    except HTTPException:raise
    except Exception as e:raise HTTPException(400,str(e))

@router.post('/review')
def review(req:ReviewRequest):
    try:return review_pgn(req.pgn,req.depth)
    except FileNotFoundError:raise HTTPException(503,'Stockfish не найден')

@router.get('/integrations/chesscom/{username}')
async def sync_chesscom(username:str,limit:int=20):
    try:return await chesscom_games(username,min(max(limit,1),100))
    except Exception as e:raise HTTPException(502,f'Chess.com: {e}')

@router.get('/integrations/lichess/{username}')
async def sync_lichess(username:str,limit:int=20):
    try:return await lichess_games(username,min(max(limit,1),100))
    except Exception as e:raise HTTPException(502,f'Lichess: {e}')
