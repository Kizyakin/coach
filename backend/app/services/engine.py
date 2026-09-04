import chess
import chess.engine
from app.core.config import settings

class EngineService:
    def __init__(self):
        self.path = settings.stockfish_path

    def analyze(self, fen: str, depth: int = 12, multipv: int = 3):
        board = chess.Board(fen)
        with chess.engine.SimpleEngine.popen_uci(self.path) as engine:
            infos = engine.analyse(board, chess.engine.Limit(depth=depth), multipv=multipv)
        if isinstance(infos, dict): infos = [infos]
        result = []
        for info in infos:
            score = info["score"].pov(board.turn)
            mate = score.mate()
            cp = score.score(mate_score=100000)
            pv = info.get("pv", [])[:8]
            san = []
            tmp = board.copy()
            for move in pv:
                try:
                    san.append(tmp.san(move)); tmp.push(move)
                except Exception:
                    break
            result.append({
                "score_cp": cp,
                "mate": mate,
                "move_uci": pv[0].uci() if pv else None,
                "line_san": san,
            })
        return result

engine_service = EngineService()
