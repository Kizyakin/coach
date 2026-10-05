from __future__ import annotations

import threading
from dataclasses import dataclass

import chess
import chess.engine

from app.core.config import settings
from app.services.notation import line_ru


@dataclass(frozen=True)
class AnalysisProfile:
    time: float
    multipv: int
    pv_len: int


PROFILES = {
    # Designed for Live Coach. On a warm Render worker the engine itself should
    # usually spend only ~90 ms here.
    "fast": AnalysisProfile(time=0.09, multipv=3, pv_len=8),
    "balanced": AnalysisProfile(time=0.35, multipv=5, pv_len=10),
    "deep": AnalysisProfile(time=1.00, multipv=8, pv_len=14),
}


class EngineService:
    """One persistent Stockfish process shared by all requests.

    Starting a new Stockfish process for every request was one of the largest
    avoidable delays in Live Coach. A lock serialises access to the single UCI
    process safely while keeping process-start overhead out of the hot path.
    """

    def __init__(self):
        self.path = settings.stockfish_path
        self._engine: chess.engine.SimpleEngine | None = None
        self._lock = threading.RLock()
        self._start_error: str | None = None

    def start(self) -> None:
        with self._lock:
            if self._engine is not None:
                return
            try:
                self._engine = chess.engine.SimpleEngine.popen_uci(self.path)
                # Keep settings conservative for Render Free memory/CPU.
                try:
                    self._engine.configure({"Threads": 1, "Hash": 64})
                except Exception:
                    pass
                self._start_error = None
            except Exception as exc:
                self._engine = None
                self._start_error = f"{type(exc).__name__}: {exc}"
                raise

    def stop(self) -> None:
        with self._lock:
            if self._engine is None:
                return
            try:
                self._engine.quit()
            except Exception:
                pass
            finally:
                self._engine = None

    def status(self) -> dict:
        return {"running": self._engine is not None, "error": self._start_error}

    def _get_engine(self) -> chess.engine.SimpleEngine:
        if self._engine is None:
            self.start()
        assert self._engine is not None
        return self._engine

    def analyze_board(
        self,
        board: chess.Board,
        depth: int | None = None,
        multipv: int | None = None,
        speed: str = "balanced",
    ):
        profile = PROFILES.get(speed, PROFILES["balanced"])
        pv_count = max(1, min(multipv or profile.multipv, 8))
        # Backward compatibility: an explicitly supplied depth is honoured only
        # outside FAST mode. FAST always uses a hard time budget.
        limit = (
            chess.engine.Limit(time=profile.time)
            if speed == "fast" or depth is None
            else chess.engine.Limit(depth=max(6, min(depth, 20)))
        )

        with self._lock:
            engine = self._get_engine()
            try:
                infos = engine.analyse(board, limit, multipv=pv_count)
            except (chess.engine.EngineTerminatedError, chess.engine.EngineError):
                # Recover once from a crashed UCI process.
                self.stop()
                engine = self._get_engine()
                infos = engine.analyse(board, limit, multipv=pv_count)

        if isinstance(infos, dict):
            infos = [infos]

        result = []
        for info in infos:
            score = info["score"].pov(board.turn)
            mate = score.mate()
            cp = score.score(mate_score=100000)
            pv = info.get("pv", [])[: profile.pv_len]
            san = []
            tmp = board.copy()
            for move in pv:
                try:
                    san.append(tmp.san(move))
                    tmp.push(move)
                except Exception:
                    break
            result.append(
                {
                    "score_cp": cp,
                    "mate": mate,
                    "move_uci": pv[0].uci() if pv else None,
                    "pv_uci": [m.uci() for m in pv],
                    "line_san": san,
                    "line_ru": line_ru(board, pv),
                }
            )
        return result

    def analyze(self, fen: str, depth: int | None = None, multipv: int | None = None, speed: str = "balanced"):
        return self.analyze_board(chess.Board(fen), depth, multipv, speed)


engine_service = EngineService()
