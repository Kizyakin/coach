#!/usr/bin/env python3
"""Build Chess Coach's latency-bounded master-position index.

The script downloads public PGN player archives, extracts practical positions,
and writes one compact aggregated index used by FAST Live Coach.

FAST runtime does *not* scan 30k positions. It performs O(1) hash lookups at
three structural resolutions (exact/medium/broad), so master guidance normally
adds much less than 1 ms after startup.

Raw PGNs are never stored. Raw extracted positions are optional and disabled by
default; the committed artifact is master_fast_index.json.gz.
"""
from __future__ import annotations

import argparse
import gzip
import io
import json
import sys
import urllib.request
import zipfile
from collections import Counter, defaultdict
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

import chess
import chess.pgn

from app.data.master_players import MASTER_PLAYERS

OUT_DIR = ROOT / "app" / "data" / "master_library"
FAST_OUT = OUT_DIR / "master_fast_index.json.gz"
RAW_OUT = OUT_DIR / "master_positions.json.gz"

VALUES = {
    chess.PAWN: 1,
    chess.KNIGHT: 3,
    chess.BISHOP: 3,
    chess.ROOK: 5,
    chess.QUEEN: 9,
    chess.KING: 0,
}


def material_sig(board: chess.Board) -> str:
    out = []
    for color in (chess.WHITE, chess.BLACK):
        out.append(
            "".join(
                str(len(board.pieces(pt, color)))
                for pt in (chess.QUEEN, chess.ROOK, chess.BISHOP, chess.KNIGHT, chess.PAWN)
            )
        )
    return "/".join(out)


def phase(board: chess.Board) -> str:
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


def king_zone_from_sq(sq: int | None, color: chess.Color) -> str:
    if sq is None:
        return "x"
    f = chess.square_file(sq)
    r = chess.square_rank(sq)
    side = "q" if f <= 2 else "k" if f >= 5 else "c"
    home = "h" if (r <= 1 if color == chess.WHITE else r >= 6) else "a"
    return side + home


def center_sig_from_masks(wp: int, bp: int) -> str:
    parts = []
    for pawns in (wp, bp):
        file_counts = []
        for file_idx in (2, 3, 4, 5):
            file_counts.append(sum(1 for r in range(8) if (pawns >> chess.square(file_idx, r)) & 1))
        core = 0
        for bit, sq in enumerate((chess.D3, chess.D4, chess.D5, chess.D6, chess.E3, chess.E4, chess.E5, chess.E6)):
            if (pawns >> sq) & 1:
                core |= 1 << bit
        parts.append("".join(map(str, file_counts)) + f"-{core:02x}")
    return "/".join(parts)


def record_keys(record: dict) -> tuple[str, str, str]:
    turn = record["turn"]
    ph = record["phase"]
    material = record["material_sig"]
    kings = king_zone_from_sq(record.get("wk"), chess.WHITE) + king_zone_from_sq(record.get("bk"), chess.BLACK)
    center = center_sig_from_masks(int(record.get("wp", 0)), int(record.get("bp", 0)))
    return (
        f"{turn}|{ph}|{material}|{kings}|{center}",
        f"{turn}|{ph}|{material}|{kings}",
        f"{turn}|{ph}|{material}",
    )


def plans_for(board: chess.Board, move: chess.Move) -> list[str]:
    plans = []
    piece = board.piece_at(move.from_square)
    if board.gives_check(move):
        plans.append("check")
    if board.is_capture(move):
        plans.append("capture")
    if board.is_castling(move):
        plans.append("castle")
    fr = chess.square_rank(move.from_square)
    tf, tr = chess.square_file(move.to_square), chess.square_rank(move.to_square)
    if piece and piece.piece_type == chess.PAWN:
        if tf in (3, 4) and abs(tr - fr) >= 1:
            plans.append("central_break")
        if tf >= 5:
            plans.append("kingside_pawn")
        if tf <= 2:
            plans.append("queenside_pawn")
    if piece and piece.piece_type == chess.KNIGHT and move.to_square in (
        chess.C4, chess.D4, chess.E4, chess.F4, chess.C5, chess.D5, chess.E5, chess.F5
    ):
        plans.append("knight_center")
    if piece and piece.piece_type == chess.ROOK:
        file_idx = chess.square_file(move.to_square)
        if not any(chess.square(file_idx, r) in board.pieces(chess.PAWN, piece.color) for r in range(8)):
            plans.append("rook_open_file")
    if piece and piece.piece_type == chess.QUEEN:
        plans.append("queen_activity")
    if piece and piece.piece_type in (chess.KNIGHT, chess.BISHOP) and not plans:
        plans.append("minor_improve")
    if not plans:
        plans.append("quiet")
    return plans[:3]


def score_game(game: chess.pgn.Game, player_name: str) -> int:
    h = game.headers
    result = h.get("Result", "")
    white = h.get("White", "")
    player_white = player_name.lower().split()[-1] in white.lower() or white.lower() in player_name.lower()
    won = (player_white and result == "1-0") or ((not player_white) and result == "0-1")
    draw = result == "1/2-1/2"
    opp_elo = h.get("BlackElo" if player_white else "WhiteElo", "")
    try:
        opp = int(opp_elo)
    except Exception:
        opp = 2400
    return (2 if won else 1 if draw else 0) * 10000 + opp


def download_pgn(slug: str) -> str:
    url = f"https://www.pgnmentor.com/players/{slug}.zip"
    req = urllib.request.Request(url, headers={"User-Agent": "ChessCoach/1.6 educational project"})
    with urllib.request.urlopen(req, timeout=90) as response:
        data = response.read()
    with zipfile.ZipFile(io.BytesIO(data)) as archive:
        names = [n for n in archive.namelist() if n.lower().endswith(".pgn")]
        if not names:
            raise RuntimeError(f"No PGN in {slug}")
        return archive.read(names[0]).decode("utf-8", errors="replace")


def parse_games(text: str):
    source = io.StringIO(text)
    while True:
        game = chess.pgn.read_game(source)
        if game is None:
            break
        yield game


def extract(player: dict, games_per_player: int = 60, positions_per_game: int = 12) -> list[dict]:
    text = download_pgn(player["slug"])
    games = list(parse_games(text))
    games.sort(key=lambda game: score_game(game, player["name"]), reverse=True)
    chosen = games[:games_per_player]
    records = []

    for game in chosen:
        h = game.headers
        white, black, result = h.get("White", ""), h.get("Black", ""), h.get("Result", "")
        player_is_white = (
            player["name"].split()[-1].lower() in white.lower()
            or player["slug"].lower() in white.lower().replace(" ", "")
        )
        color = chess.WHITE if player_is_white else chess.BLACK
        opponent = black if player_is_white else white
        board = game.board()
        candidates = []
        for ply, move in enumerate(game.mainline_moves()):
            if board.turn == color and 10 <= ply <= 110:
                candidates.append((ply, board.copy(stack=False), move))
            board.push(move)
        if not candidates:
            continue
        step = max(1, len(candidates) // positions_per_game)
        for _, board, move in candidates[::step][:positions_per_game]:
            try:
                san = board.san(move)
            except Exception:
                continue
            records.append(
                {
                    "player": player["name"],
                    "player_ru": player["name_ru"],
                    "opponent": opponent,
                    "year": h.get("Date", "")[:4],
                    "result": result,
                    "turn": "w" if board.turn else "b",
                    "phase": phase(board),
                    "material_sig": material_sig(board),
                    "wp": board.pieces(chess.PAWN, chess.WHITE).mask,
                    "bp": board.pieces(chess.PAWN, chess.BLACK).mask,
                    "wk": board.king(chess.WHITE),
                    "bk": board.king(chess.BLACK),
                    "move_uci": move.uci(),
                    "move_san": san,
                    "plans": plans_for(board, move),
                }
            )
    return records


class Aggregate:
    __slots__ = ("n", "plans", "players", "examples")

    def __init__(self):
        self.n = 0
        self.plans = Counter()
        self.players = Counter()
        self.examples: list[dict] = []

    def add(self, record: dict) -> None:
        self.n += 1
        self.plans.update(record.get("plans", []))
        player = record.get("player_ru") or record.get("player")
        if player:
            self.players[player] += 1
        if len(self.examples) < 4:
            self.examples.append(
                {
                    "player": player,
                    "opponent": record.get("opponent"),
                    "year": record.get("year"),
                    "move_san": record.get("move_san"),
                    "move_uci": record.get("move_uci"),
                    "plans": record.get("plans", []),
                    "result": record.get("result"),
                }
            )

    def dump(self) -> dict:
        return {
            "n": self.n,
            "plans": self.plans.most_common(6),
            "players": self.players.most_common(6),
            "examples": self.examples[:3],
        }


def build_fast_index(records: list[dict]) -> dict:
    levels = {
        "exact": defaultdict(Aggregate),
        "medium": defaultdict(Aggregate),
        "broad": defaultdict(Aggregate),
    }
    for record in records:
        exact, medium, broad = record_keys(record)
        levels["exact"][exact].add(record)
        levels["medium"][medium].add(record)
        levels["broad"][broad].add(record)

    # Exact singletons are not useful as a "pattern" and waste RAM; medium and
    # broad levels guarantee a fallback.
    exact = {k: v.dump() for k, v in levels["exact"].items() if v.n >= 2}
    medium = {k: v.dump() for k, v in levels["medium"].items()}
    broad = {k: v.dump() for k, v in levels["broad"].items()}
    return {
        "version": 2,
        "positions": len(records),
        "players": len(MASTER_PLAYERS),
        "bucket_count": len(exact) + len(medium) + len(broad),
        "levels": {"exact": exact, "medium": medium, "broad": broad},
    }


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--players", type=int, default=45)
    parser.add_argument("--games-per-player", type=int, default=60)
    parser.add_argument("--positions-per-game", type=int, default=12)
    parser.add_argument("--keep-raw", action="store_true")
    args = parser.parse_args()

    selected = MASTER_PLAYERS[: max(1, min(args.players, len(MASTER_PLAYERS)))]
    records: list[dict] = []
    for i, player in enumerate(selected, 1):
        print(f"[{i}/{len(selected)}] {player['name_ru']}…", flush=True)
        try:
            extracted = extract(player, args.games_per_player, args.positions_per_game)
            records.extend(extracted)
            print(f"  +{len(extracted)} positions", flush=True)
        except Exception as exc:
            print(f"  ERROR: {exc}", flush=True)

    OUT_DIR.mkdir(parents=True, exist_ok=True)
    index = build_fast_index(records)
    with gzip.open(FAST_OUT, "wt", encoding="utf-8", compresslevel=9) as fh:
        json.dump(index, fh, ensure_ascii=False, separators=(",", ":"))

    if args.keep_raw:
        with gzip.open(RAW_OUT, "wt", encoding="utf-8", compresslevel=9) as fh:
            json.dump(records, fh, ensure_ascii=False, separators=(",", ":"))

    print(
        f"Saved {len(records)} positions -> {FAST_OUT}\n"
        f"Buckets: {index['bucket_count']} | raw kept: {args.keep_raw}",
        flush=True,
    )


if __name__ == "__main__":
    main()
