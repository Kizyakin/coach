import {Chess} from 'chess.js';
const P:Record<string,string>={p:'Пешка',n:'Конь',b:'Слон',r:'Ладья',q:'Ферзь',k:'Король'};
export function uciRu(game:Chess,uci:string){
  const from=uci.slice(0,2),to=uci.slice(2,4),promotion=uci[4];
  const piece=game.get(from as any); if(!piece)return `${from} → ${to}`;
  const clone=new Chess(game.fen());
  let move:any=null;try{move=clone.move({from,to,promotion:promotion||'q'} as any)}catch{}
  if(!move)return `${P[piece.type]||'Фигура'} → ${to}`;
  if(move.flags.includes('k'))return 'Рокировка 0-0';
  if(move.flags.includes('q'))return 'Рокировка 0-0-0';
  const capture=move.captured?' × ':' → ';
  let out=`${P[piece.type]||'Фигура'}${capture}${to}`;
  if(promotion)out+=` = ${P[promotion]||promotion}`;
  if(move.san.endsWith('#'))out+='#'; else if(move.san.endsWith('+'))out+='+';
  return out;
}
