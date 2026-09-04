import {useEffect,useMemo,useState} from 'react';
import {Chess} from 'chess.js';
import {Chessboard} from 'react-chessboard';
import {api} from '../lib/api';
import {uciRu} from '../lib/chessNotation';

type Puzzle={id:string;category:string;theme:string;themes:string[];title:string;prompt:string;fen:string;solution_uci:string[];rating?:number;plays?:number;source?:string};

export default function PuzzleTrainer({theme='mix',target=0,onExit}:{theme?:string;target?:number;onExit?:()=>void}){
 const [p,setP]=useState<Puzzle|null>(null),[game,setGame]=useState<Chess|null>(null),[step,setStep]=useState(0),[hint,setHint]=useState(0),[msg,setMsg]=useState(''),[loading,setLoading]=useState(false),[solved,setSolved]=useState(0),[difficulty,setDifficulty]=useState('normal');
 async function load(){setLoading(true);setMsg('');setHint(0);setStep(0);try{const x=await api<Puzzle>(`/api/training/next?theme=${encodeURIComponent(theme)}&difficulty=${difficulty}`);setP(x);setGame(new Chess(x.fen))}catch(e:any){setMsg(`Не удалось получить задачу: ${e.message}`)}finally{setLoading(false)}}
 useEffect(()=>{load()},[theme,difficulty]);
 const expected=p?.solution_uci?.[step];
 const hintText=useMemo(()=>{
   if(!p||!game||!expected||hint===0)return '';
   const ru=uciRu(game,expected),from=expected.slice(0,2),to=expected.slice(2,4);
   if(hint===1)return `ТЕМА // ${p.category}. Сначала перечисли шахи, взятия и угрозы.`;
   if(hint===2)return `Ищи ход фигурой с поля ${from}.`;
   if(hint===3)return `Целевое поле — ${to}.`;
   return `ТОЧНЫЙ ХОД // ${ru}`;
 },[p,game,expected,hint]);
 function playOpponent(base:Chess,nextStep:number){
   if(!p||nextStep>=p.solution_uci.length){finish();return}
   const u=p.solution_uci[nextStep];const next=new Chess(base.fen());
   try{next.move({from:u.slice(0,2),to:u.slice(2,4),promotion:u[4]||'q'} as any);setGame(next);setStep(nextStep+1);if(nextStep+1>=p.solution_uci.length)finish()}catch{setMsg('Ошибка линии задачи. Загрузим другую.');}
 }
 function finish(){setMsg('РЕШЕНО // последовательность найдена.');setSolved(s=>s+1)}
 function drop(s:string,t:string){if(!p||!game||!expected||loading)return false;const u=s+t;const promo=expected.length===5?expected[4]:'q';if(!expected.startsWith(u)){setMsg('НЕ ТОТ ХОД // позиция не изменена. Используй подсказку или попробуй другой кандидат.');return false}
   const next=new Chess(game.fen());try{next.move({from:s,to:t,promotion:promo} as any)}catch{return false};setGame(next);setMsg('ТОЧНО // теперь ответ соперника.');const ns=step+1;if(ns>=p.solution_uci.length){finish()}else{setTimeout(()=>playOpponent(next,ns),280)}return true}
 const done=target>0&&solved>=target;
 if(done)return <div className="puzzleDone card"><span className="tag">LESSON//COMPLETE</span><h2>{solved}/{target}</h2><p>Серия решена. Ты отработал тему на реальных позициях.</p><button className="primary" onClick={onExit}>К УРОКАМ</button></div>;
 return <div className="trainingPlay">
   <section className="boardCard"><div className="boardFrame">{game&&<Chessboard options={{position:game.fen(),boardOrientation:game.turn()==='w'?'white':'black',onPieceDrop:({sourceSquare,targetSquare})=>!!targetSquare&&drop(sourceSquare,targetSquare),boardStyle:{borderRadius:'0',boxShadow:'none'}}}/>}</div></section>
   <aside className="card trainingPrompt"><div className="tags"><span className="tag">{p?.category||theme}</span>{p?.rating&&<span className="tag muted">RATING {p.rating}</span>}</div><h2>{p?.title||'Загрузка…'}</h2><p>{p?.prompt}</p>{target>0&&<div className="lessonProgress">СЕРИЯ // {solved}/{target}</div>}
    <div className="segmented"><span>СЛОЖНОСТЬ</span>{[['easier','ЛЕГЧЕ'],['normal','НОРМА'],['harder','СЛОЖНЕЕ']].map(([v,n])=><button key={v} className={difficulty===v?'selected':''} onClick={()=>setDifficulty(v)}>{n}</button>)}</div>
    <div className="hintStack"><button className="secondary" disabled={!expected} onClick={()=>setHint(h=>Math.min(4,h+1))}>ПОДСКАЗКА {hint<4?`${hint+1}/4`:'MAX'}</button>{hintText&&<div className="hint">{hintText}</div>}</div>
    {msg&&<div className={msg.startsWith('РЕШЕНО')||msg.startsWith('ТОЧНО')?'result ok':'result bad'}>{msg}</div>}
    <div className="actions"><button className="secondary" onClick={load} disabled={loading}>{loading?'ЗАГРУЗКА…':'ДРУГАЯ ЗАДАЧА'}</button>{msg.startsWith('РЕШЕНО')&&<button className="primary" onClick={load}>СЛЕДУЮЩАЯ →</button>}</div>
    <small className="sourceLine">SOURCE // {p?.source||'Lichess public puzzle data'}</small>
   </aside>
 </div>
}
