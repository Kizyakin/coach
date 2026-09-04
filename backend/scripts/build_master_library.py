#!/usr/bin/env python3
"""Build a compact case-based library from public PGN collections.

Run locally once, commit only the generated .json.gz. Raw PGNs are not kept.
Source URLs are PGN Mentor player archives. The script extracts practical
positions and plan tags; it does NOT train a neural network.
"""
from __future__ import annotations
import argparse,gzip,io,json,random,sys,urllib.request,zipfile
from pathlib import Path

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT))
import chess, chess.pgn
from app.data.master_players import MASTER_PLAYERS

OUT=ROOT/"app"/"data"/"master_library"/"master_positions.json.gz"
VALUES={chess.PAWN:1,chess.KNIGHT:3,chess.BISHOP:3,chess.ROOK:5,chess.QUEEN:9,chess.KING:0}

def material_sig(b):
    out=[]
    for color in [chess.WHITE,chess.BLACK]:
        out.append("".join(str(len(b.pieces(pt,color))) for pt in [chess.QUEEN,chess.ROOK,chess.BISHOP,chess.KNIGHT,chess.PAWN]))
    return "/".join(out)

def phase(b):
    nonpawn=sum(len(b.pieces(pt,c))*VALUES[pt] for c in [chess.WHITE,chess.BLACK] for pt in [chess.KNIGHT,chess.BISHOP,chess.ROOK,chess.QUEEN])
    if b.fullmove_number<=12 and nonpawn>=44:return "opening"
    if nonpawn<=20:return "endgame"
    return "middlegame"

def plans_for(b,m):
    plans=[];piece=b.piece_at(m.from_square)
    if b.gives_check(m):plans.append("check")
    if b.is_capture(m):plans.append("capture")
    if b.is_castling(m):plans.append("castle")
    ff,fr=chess.square_file(m.from_square),chess.square_rank(m.from_square);tf,tr=chess.square_file(m.to_square),chess.square_rank(m.to_square)
    if piece and piece.piece_type==chess.PAWN:
        if tf in (3,4) and abs(tr-fr)>=1:plans.append("central_break")
        if tf>=5:plans.append("kingside_pawn")
        if tf<=2:plans.append("queenside_pawn")
    if piece and piece.piece_type==chess.KNIGHT and m.to_square in [chess.C4,chess.D4,chess.E4,chess.F4,chess.C5,chess.D5,chess.E5,chess.F5]:plans.append("knight_center")
    if piece and piece.piece_type==chess.ROOK:
        file=chess.square_file(m.to_square)
        if not any(chess.square(file,r) in b.pieces(chess.PAWN,piece.color) for r in range(8)):plans.append("rook_open_file")
    if piece and piece.piece_type==chess.QUEEN:plans.append("queen_activity")
    if piece and piece.piece_type in (chess.KNIGHT,chess.BISHOP) and not plans:plans.append("minor_improve")
    if not plans:plans.append("quiet")
    return plans[:3]

def score_game(game,player_name):
    h=game.headers;res=h.get("Result","")
    white=h.get("White","");black=h.get("Black","")
    player_white=player_name.lower().split()[-1] in white.lower() or white.lower() in player_name.lower()
    won=(player_white and res=="1-0") or ((not player_white) and res=="0-1")
    draw=res=="1/2-1/2"
    opp_elo=h.get("BlackElo" if player_white else "WhiteElo","")
    try:opp=int(opp_elo)
    except:opp=2400
    return (2 if won else 1 if draw else 0)*10000+opp

def download_pgn(slug):
    url=f"https://www.pgnmentor.com/players/{slug}.zip"
    req=urllib.request.Request(url,headers={"User-Agent":"ChessCoach/1.4 educational project"})
    with urllib.request.urlopen(req,timeout=90) as r:data=r.read()
    with zipfile.ZipFile(io.BytesIO(data)) as z:
        names=[n for n in z.namelist() if n.lower().endswith('.pgn')]
        if not names:raise RuntimeError(f"No PGN in {slug}")
        return z.read(names[0]).decode('utf-8',errors='replace')

def parse_games(text):
    f=io.StringIO(text)
    while True:
        g=chess.pgn.read_game(f)
        if g is None:break
        yield g

def extract(player,games_per_player=60,positions_per_game=12):
    text=download_pgn(player['slug']); games=list(parse_games(text))
    games.sort(key=lambda g:score_game(g,player['name']),reverse=True)
    chosen=games[:games_per_player]
    records=[]
    for game in chosen:
        h=game.headers;white=h.get('White','');black=h.get('Black','');res=h.get('Result','')
        player_is_white=(player['name'].split()[-1].lower() in white.lower()) or (player['slug'].lower() in white.lower().replace(' ',''))
        color=chess.WHITE if player_is_white else chess.BLACK
        opponent=black if player_is_white else white
        board=game.board();candidate=[]
        for ply,move in enumerate(game.mainline_moves()):
            if board.turn==color and 10<=ply<=110:
                candidate.append((ply,board.copy(stack=False),move))
            board.push(move)
        if not candidate:continue
        step=max(1,len(candidate)//positions_per_game)
        for ply,b,m in candidate[::step][:positions_per_game]:
            try:san=b.san(m)
            except:continue
            records.append({
                'player':player['name'],'player_ru':player['name_ru'],'opponent':opponent,'year':h.get('Date','')[:4],
                'result':res,'turn':'w' if b.turn else 'b','phase':phase(b),'material_sig':material_sig(b),
                'wp':b.pieces(chess.PAWN,chess.WHITE).mask,'bp':b.pieces(chess.PAWN,chess.BLACK).mask,'occ':b.occupied,
                'wk':b.king(chess.WHITE),'bk':b.king(chess.BLACK),'move_uci':m.uci(),'move_san':san,'plans':plans_for(b,m),
            })
    return records

def main():
    ap=argparse.ArgumentParser();ap.add_argument('--players',type=int,default=45);ap.add_argument('--games-per-player',type=int,default=60);ap.add_argument('--positions-per-game',type=int,default=12)
    args=ap.parse_args();allr=[]
    for i,p in enumerate(MASTER_PLAYERS[:max(1,min(args.players,len(MASTER_PLAYERS)))],1):
        print(f"[{i}/{min(args.players,len(MASTER_PLAYERS))}] {p['name_ru']}…",flush=True)
        try:
            r=extract(p,args.games_per_player,args.positions_per_game);allr.extend(r);print(f"  +{len(r)} positions",flush=True)
        except Exception as e:print(f"  ERROR: {e}",flush=True)
    OUT.parent.mkdir(parents=True,exist_ok=True)
    with gzip.open(OUT,'wt',encoding='utf-8',compresslevel=9) as f:json.dump(allr,f,ensure_ascii=False,separators=(',',':'))
    print(f"Saved {len(allr)} positions -> {OUT}")

if __name__=='__main__':main()
