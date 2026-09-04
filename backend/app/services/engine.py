import chess
import chess.engine
from app.core.config import settings
from app.services.notation import line_ru

class EngineService:
    def __init__(self):
        self.path = settings.stockfish_path

    def analyze_board(self, board: chess.Board, depth: int = 12, multipv: int = 3):
        with chess.engine.SimpleEngine.popen_uci(self.path) as engine:
            infos = engine.analyse(board, chess.engine.Limit(depth=depth), multipv=multipv)
        if isinstance(infos, dict): infos = [infos]
        result=[]
        for info in infos:
            score = info["score"].pov(board.turn)
            mate = score.mate(); cp = score.score(mate_score=100000)
            pv = info.get("pv", [])[:10]
            san=[]; tmp=board.copy()
            for move in pv:
                try: san.append(tmp.san(move)); tmp.push(move)
                except Exception: break
            result.append({
                "score_cp": cp, "mate": mate,
                "move_uci": pv[0].uci() if pv else None,
                "line_san": san,
                "line_ru": line_ru(board, pv),
            })
        return result

    def analyze(self, fen: str, depth: int = 12, multipv: int = 3):
        return self.analyze_board(chess.Board(fen), depth, multipv)

engine_service = EngineService()
