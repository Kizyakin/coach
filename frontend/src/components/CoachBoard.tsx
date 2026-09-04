import {useMemo,useState} from 'react';
import {Chess} from 'chess.js';
import {Chessboard} from 'react-chessboard';
import {api} from '../lib/api';

type Mode='play'|'live';
type Side='white'|'black';

export default function CoachBoard({mode}:{mode:Mode}){
  const [game,setGame]=useState(new Chess());
  const [coach,setCoach]=useState<any>(null);
  const [busy,setBusy]=useState(false);
  const [history,setHistory]=useState<string[]>([]);
  const [side,setSide]=useState<Side>('white');
  const [depth,setDepth]=useState(10);
  const turn=game.turn();

  async function analyze(g=game){setBusy(true);try{setCoach(await api('/api/coach/analyze',{method:'POST',body:JSON.stringify({fen:g.fen(),depth,player_side:side})}))}catch(e:any){setCoach({error:e.message})}finally{setBusy(false)}}

  async function botMove(g:Chess){
    if(g.isGameOver()) return;
    setBusy(true);
    try{
      const r:any=await api('/api/engine/move',{method:'POST',body:JSON.stringify({fen:g.fen(),depth:Math.max(8,depth-1)})});
      if(r.move_uci){
        const next=new Chess(g.fen());
        next.move({from:r.move_uci.slice(0,2),to:r.move_uci.slice(2,4),promotion:r.move_uci[4]||'q'});
        setGame(next); setHistory(h=>[...h,r.move_san]); await analyze(next);
      }
    }catch(e:any){setCoach({error:e.message})}finally{setBusy(false)}
  }

  function drop(s:string,t:string){
    if(busy) return false;
    if(mode==='play' && turn!==side[0]) return false;
    const next=new Chess(game.fen());
    try{
      const m=next.move({from:s,to:t,promotion:'q'}); if(!m)return false;
      setGame(next);setHistory(h=>[...h,m.san]);analyze(next);
      if(mode==='play'&&!next.isGameOver()) setTimeout(()=>botMove(next),300);
      return true;
    }catch{return false}
  }

  function reset(newSide=side){
    const g=new Chess(); setGame(g); setHistory([]); setCoach(null);
    if(mode==='play'&&newSide==='black') setTimeout(()=>botMove(g),250);
  }
  function chooseSide(s:Side){setSide(s);reset(s)}

  const evalText=useMemo(()=>{const cp=coach?.best_move?.score_cp;if(cp==null)return '—';if(Math.abs(cp)>90000)return coach?.best_move?.mate?`мат ${Math.abs(coach.best_move.mate)}`:'—';return `${cp>=0?'+':''}${(cp/100).toFixed(2)}`},[coach]);

  return <div className="gameShell">
    <div className="gameToolbar">
      <div className="segmented"><span>{mode==='live'?'ОРИЕНТАЦИЯ':'МОЯ СТОРОНА'}</span><button className={side==='white'?'selected':''} onClick={()=>chooseSide('white')}>БЕЛЫЕ</button><button className={side==='black'?'selected':''} onClick={()=>chooseSide('black')}>ЧЁРНЫЕ</button></div>
      <div className="turnStatus"><i className={turn==='w'?'whiteDot':'blackDot'}></i><span>ХОД // {turn==='w'?'БЕЛЫЕ':'ЧЁРНЫЕ'}</span></div>
      <div className="segmented"><span>ГЛУБИНА</span>{[8,10,12].map(d=><button key={d} className={depth===d?'selected':''} onClick={()=>setDepth(d)}>{d===8?'FAST':d===10?'NORMAL':'DEEP'}</button>)}</div>
    </div>
    {mode==='live'&&<div className="liveRule">LIVE INPUT // ХОДЫ ОБЕИХ СТОРОН ВНОСИШЬ ТЫ · СТОРОНА ВЫШЕ МЕНЯЕТ ОРИЕНТАЦИЮ ДОСКИ</div>}
    <div className="boardLayout">
      <section className="boardCard">
        <div className="boardFrame"><Chessboard options={{position:game.fen(),boardOrientation:side,onPieceDrop:({sourceSquare,targetSquare})=>!!targetSquare&&drop(sourceSquare,targetSquare),boardStyle:{borderRadius:'0',boxShadow:'none'}}}/></div>
        <div className="boardActions"><button className="secondary" onClick={()=>reset()}>RESET//GAME</button><button className="primary" onClick={()=>analyze()} disabled={busy}>{busy?'ANALYZING…':'ANALYZE//NOW'}</button></div>
      </section>
      <aside className="coachPanel">
        <div className="coachHead"><div className="avatar">AI</div><div><b>COACH//{mode==='live'?'LIVE':'ENGINE'}</b><span>{busy?'CALCULATING VARIANTS…':`POSITION READY · ${side==='white'?'WHITE':'BLACK'} VIEW`}</span></div></div>
        {coach?.error?<div className="warning">API//ERROR · {coach.error}</div>:coach? <>
          <div className="bestMove"><span>BEST//MOVE</span><strong>{coach.best_move?.move_san||'—'}</strong><em>{evalText}</em></div>
          <div className="priority">POSITION//PRIORITY <b>{coach.priority}</b></div>
          {coach.hints?.map((h:string)=><div className="hint" key={h}>{h}</div>)}
          <div className="candidateTitle">CANDIDATE//MOVES</div>
          <div className="candidates">{coach.candidates?.map((c:any)=><div className="candidate" key={c.rank}><b>{String(c.rank).padStart(2,'0')}</b><div><strong>{c.move_san}</strong><p>{c.reason}</p><small>{c.line_san?.slice(0,5).join(' ')}</small></div></div>)}</div>
          <div className="facts"><div><span>PHASE</span><b>{coach.facts?.phase}</b></div><div><span>MATERIAL</span><b>{coach.facts?.material>0?'+':''}{coach.facts?.material}</b></div><div><span>CHECKS</span><b>{coach.facts?.checks?.length||0}</b></div><div><span>CAPTURES</span><b>{coach.facts?.captures?.length||0}</b></div></div>
        </>:<div className="emptyCoach"><b>SYSTEM//READY</b><p>{mode==='live'?'Вводи ходы обеих сторон вручную. После каждого хода я пересчитаю позицию и покажу конкретные варианты.':'Сделай ход. Если ты выбрал чёрные, первый ход белыми уже сделает движок.'}</p></div>}
        <div className="history"><b>MOVE//LOG</b><p>{history.length?history.join('  '):'no moves yet_'}</p></div>
      </aside>
    </div>
  </div>
}
