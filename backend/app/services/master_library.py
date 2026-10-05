from __future__ import annotations

import gzip
import json
import time
from collections import Counter
from pathlib import Path

import chess

from app.data.master_players import MASTER_PLAYERS

DATA_DIR = Path(__file__).resolve().parents[1] / "data" / "master_library"
RAW_PATH = DATA_DIR / "master_positions.json.gz"
FAST_PATH = DATA_DIR / "master_fast_index.json.gz"

PLAN_RU = {
    "check": "форсированный шах",
    "capture": "тактическое взятие",
    "castle": "рокировка и безопасность короля",
    "central_break": "пешечный прорыв в центре",
    "kingside_pawn": "пешечное наступление на королевском фланге",
    "queenside_pawn": "пешечное наступление на ферзевом фланге",
    "knight_center": "перевод коня на сильное центральное поле",
    "rook_open_file": "активизация ладьи по открытой/полуоткрытой линии",
    "queen_activity": "активизация ферзя",
    "minor_improve": "улучшение лёгкой фигуры",
    "quiet": "улучшение позиции без форсирования",
}

VALUES = {
    chess.PAWN: 1,
    chess.KNIGHT: 3,
    chess.BISHOP: 3,
    chess.ROOK: 5,
    chess.QUEEN: 9,
    chess.KING: 0,
}


def _material_sig(board: chess.Board) -> str:
    out = []
    for color in (chess.WHITE, chess.BLACK):
        out.append(
            "".join(
                str(len(board.pieces(pt, color)))
                for pt in (chess.QUEEN, chess.ROOK, chess.BISHOP, chess.KNIGHT, chess.PAWN)
            )
        )
    return "/".join(out)


def _phase(board: chess.Board) -> str:
    nonpawn = sum(
        len(board.pieces(pt, color)) * VALUES[pt]
        for color in (chess.WHITE, chess.BLACK)
        for pt in (chess.KNIGHT, chess.BISHOP, chess.ROOK, chess.QUEEN)
    )
    if board.fullmove_number <= 12 and nonpawn >= 44:
        return "opening"
    if nonpawn <= 20:
        return "endgame"
    return "middlegame"


def _king_zone(board: chess.Board, color: chess.Color) -> str:
    sq = board.king(color)
    if sq is None:
        return "x"
    f = chess.square_file(sq)
    r = chess.square_rank(sq)
    side = "q" if f <= 2 else "k" if f >= 5 else "c"
    # home vs advanced is enough to separate castled/central king structures.
    home = "h" if (r <= 1 if color == chess.WHITE else r >= 6) else "a"
    return side + home


def _center_sig(board: chess.Board) -> str:
    """Very small structural signature used only as an O(1) bucket key.

    We intentionally keep it coarse. Exact position matching would fragment the
    master data too much, while this captures the centre shape that most often
    determines the practical plan.
    """
    parts: list[str] = []
    for color in (chess.WHITE, chess.BLACK):
        pawns = board.pieces(chess.PAWN, color)
        # Number of pawns on c/d/e/f files, plus occupation of d/e central squares.
        file_counts = []
        for file_idx in (2, 3, 4, 5):
            file_counts.append(sum(1 for r in range(8) if chess.square(file_idx, r) in pawns))
        core = 0
        for bit, sq in enumerate((chess.D3, chess.D4, chess.D5, chess.D6, chess.E3, chess.E4, chess.E5, chess.E6)):
            if sq in pawns:
                core |= 1 << bit
        parts.append("".join(map(str, file_counts)) + f"-{core:02x}")
    return "/".join(parts)


def index_keys(board: chess.Board) -> tuple[str, str, str]:
    turn = "w" if board.turn else "b"
    phase = _phase(board)
    material = _material_sig(board)
    kings = _king_zone(board, chess.WHITE) + _king_zone(board, chess.BLACK)
    center = _center_sig(board)
    exact = f"{turn}|{phase}|{material}|{kings}|{center}"
    medium = f"{turn}|{phase}|{material}|{kings}"
    broad = f"{turn}|{phase}|{material}"
    return exact, medium, broad


class MasterLibrary:
    """Latency-bounded master-position lookup.

    FAST mode never scans the raw master-position list. The build script creates
    an aggregated multi-level hash index, which is loaded once at API startup.
    A lookup is then a few dictionary reads and normally takes well below 1 ms.
    """

    def __init__(self):
        self._fast: dict | None = None
        self._fast_error: str | None = None
        self._loaded_ms: float | None = None

    def preload_fast(self) -> None:
        if self._fast is not None:
            return
        started = time.perf_counter()
        if not FAST_PATH.exists():
            self._fast = {}
            self._fast_error = "master_fast_index.json.gz not found"
            self._loaded_ms = round((time.perf_counter() - started) * 1000, 2)
            return
        try:
            with gzip.open(FAST_PATH, "rt", encoding="utf-8") as fh:
                payload = json.load(fh)
            if not isinstance(payload, dict):
                raise ValueError("invalid master index payload")
            self._fast = payload
            self._fast_error = None
        except Exception as exc:
            self._fast = {}
            self._fast_error = f"{type(exc).__name__}: {exc}"
        self._loaded_ms = round((time.perf_counter() - started) * 1000, 2)

    @property
    def count(self) -> int:
        self.preload_fast()
        return int((self._fast or {}).get("positions", 0))

    def status(self, force_load: bool = False) -> dict:
        if force_load:
            self.preload_fast()
        loaded = self._fast is not None
        payload = self._fast or {}
        return {
            "available": bool(payload.get("positions")) if loaded else FAST_PATH.exists(),
            "loaded": loaded,
            "mode": "fast-index",
            "positions": payload.get("positions") if loaded else None,
            "players": payload.get("players", len(MASTER_PLAYERS)) if loaded else len(MASTER_PLAYERS),
            "buckets": payload.get("bucket_count") if loaded else None,
            "path": FAST_PATH.name,
            "load_ms": self._loaded_ms,
            "error": self._fast_error,
        }

    @staticmethod
    def _format_bucket(bucket: dict | None, total_positions: int, lookup_ms: float) -> dict:
        if not bucket:
            return {
                "available": False,
                "positions": total_positions,
                "players": len(MASTER_PLAYERS),
                "plans": [],
                "top_players": [],
                "examples": [],
                "lookup_ms": round(lookup_ms, 3),
            }
        return {
            "available": True,
            "positions": total_positions,
            "players": len(MASTER_PLAYERS),
            "matched_positions": bucket.get("n", 0),
            "plans": [
                {"id": x[0], "name": PLAN_RU.get(x[0], x[0]), "weight": x[1]}
                for x in bucket.get("plans", [])[:4]
            ],
            "top_players": [x[0] for x in bucket.get("players", [])[:4]],
            "examples": bucket.get("examples", [])[:3],
            "lookup_ms": round(lookup_ms, 3),
        }

    def find_patterns(self, board: chess.Board, limit: int = 6, fast: bool = False) -> dict:
        started = time.perf_counter()
        self.preload_fast()
        payload = self._fast or {}
        total = int(payload.get("positions", 0))
        if not total:
            return self._format_bucket(None, 0, (time.perf_counter() - started) * 1000)

        exact, medium, broad = index_keys(board)
        levels = payload.get("levels", {})
        bucket = (levels.get("exact", {}) or {}).get(exact)
        match_level = "exact"
        if not bucket:
            bucket = (levels.get("medium", {}) or {}).get(medium)
            match_level = "medium"
        if not bucket:
            bucket = (levels.get("broad", {}) or {}).get(broad)
            match_level = "broad"

        result = self._format_bucket(bucket, total, (time.perf_counter() - started) * 1000)
        if result.get("available"):
            result["match_level"] = match_level
        return result


master_library = MasterLibrary()
