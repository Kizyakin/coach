from __future__ import annotations
import gzip, json, math
from collections import Counter
from pathlib import Path
import chess
from app.data.master_players import MASTER_PLAYERS

LIB_PATH = Path(__file__).resolve().parents[1] / "data" / "master_library" / "master_positions.json.gz"

PLAN_RU = {
    "check":"форсированный шах",
    "capture":"тактическое взятие",
    "castle":"рокировка и безопасность короля",
    "central_break":"пешечный прорыв в центре",
    "kingside_pawn":"пешечное наступление на королевском фланге",
    "queenside_pawn":"пешечное наступление на ферзевом фланге",
    "knight_center":"перевод коня на сильное центральное поле",
    "rook_open_file":"активизация ладьи по открытой/полуоткрытой линии",
    "queen_activity":"активизация ферзя",
    "minor_improve":"улучшение лёгкой фигуры",
    "quiet":"улучшение позиции без форсирования",
}

VALUES={chess.PAWN:1,chess.KNIGHT:3,chess.BISHOP:3,chess.ROOK:5,chess.QUEEN:9,chess.KING:0}

class MasterLibrary:
    def __init__(self):
        self._records=None
        self._buckets={}

    def _load(self):
        if self._records is not None:return
        self._records=[]
        if LIB_PATH.exists():
            try:
                with gzip.open(LIB_PATH,"rt",encoding="utf-8") as f:self._records=json.load(f)
            except Exception:self._records=[]
        for i,r in enumerate(self._records):
            key=(r.get("turn"),r.get("material_sig"))
            self._buckets.setdefault(key,[]).append(i)

    @property
    def count(self):
        self._load();return len(self._records)

    def status(self):
        self._load()
        return {"available":bool(self._records),"positions":len(self._records),"players":len(MASTER_PLAYERS),"path":str(LIB_PATH.name)}

    def _material_sig(self,b:chess.Board):
        out=[]
        for color in [chess.WHITE,chess.BLACK]:
            out.append("".join(str(len(b.pieces(pt,color))) for pt in [chess.QUEEN,chess.ROOK,chess.BISHOP,chess.KNIGHT,chess.PAWN]))
        return "/".join(out)

    def _sim(self,b:chess.Board,r:dict):
        # We compare structures and material, not exact positions.
        wp=int(r.get("wp",0));bp=int(r.get("bp",0));occ=int(r.get("occ",0))
        cur_wp=b.pieces(chess.PAWN,chess.WHITE).mask;cur_bp=b.pieces(chess.PAWN,chess.BLACK).mask
        cur_occ=b.occupied
        pawn_diff=((cur_wp^wp).bit_count()+(cur_bp^bp).bit_count())
        pawn_sim=max(0,1-pawn_diff/16)
        occ_diff=(cur_occ^occ).bit_count();occ_sim=max(0,1-occ_diff/24)
        king_sim=0
        for color,k in [(chess.WHITE,"wk"),(chess.BLACK,"bk")]:
            sq=b.king(color);rs=r.get(k)
            if sq is not None and rs is not None:
                f1,r1=chess.square_file(sq),chess.square_rank(sq);f2,r2=chess.square_file(rs),chess.square_rank(rs)
                king_sim += max(0,1-(abs(f1-f2)+abs(r1-r2))/8)
        king_sim/=2
        phase_bonus=1 if r.get("phase")==self.phase(b) else .65
        return (0.50*pawn_sim+0.20*occ_sim+0.20*king_sim+0.10*phase_bonus)

    def phase(self,b:chess.Board):
        nonpawn=sum(len(b.pieces(pt,c))*VALUES[pt] for c in [chess.WHITE,chess.BLACK] for pt in [chess.KNIGHT,chess.BISHOP,chess.ROOK,chess.QUEEN])
        if b.fullmove_number<=12 and nonpawn>=44:return "opening"
        if nonpawn<=20:return "endgame"
        return "middlegame"

    def find_patterns(self,b:chess.Board,limit:int=10):
        self._load()
        if not self._records:
            return {"available":False,"positions":0,"players":len(MASTER_PLAYERS),"plans":[],"examples":[]}
        key=("w" if b.turn else "b",self._material_sig(b))
        idxs=self._buckets.get(key)
        if not idxs:
            idxs=range(len(self._records))
        scored=[]
        # cap full scans so free Render remains responsive
        for i in idxs:
            r=self._records[i];s=self._sim(b,r)
            if s>=.34:scored.append((s,r))
        scored.sort(key=lambda x:x[0],reverse=True)
        top=scored[:limit]
        plans=Counter();players=Counter()
        for s,r in top:
            for p in r.get("plans",[]):plans[p]+=s
            players[r.get("player_ru") or r.get("player")]+=s
        plan_list=[{"id":k,"name":PLAN_RU.get(k,k),"weight":round(v,2)} for k,v in plans.most_common(4)]
        examples=[]
        for s,r in top[:5]:
            examples.append({
                "player":r.get("player_ru") or r.get("player"),"opponent":r.get("opponent"),"year":r.get("year"),
                "move_san":r.get("move_san"),"move_uci":r.get("move_uci"),"plans":[PLAN_RU.get(x,x) for x in r.get("plans",[])],"similarity":round(s,2),"result":r.get("result")
            })
        return {"available":True,"positions":len(self._records),"players":len(MASTER_PLAYERS),"plans":plan_list,"top_players":[p for p,_ in players.most_common(4)],"examples":examples}

master_library=MasterLibrary()
