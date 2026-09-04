import {useEffect,useMemo,useState} from 'react';
import {api} from '../lib/api';
import PuzzleTrainer from '../components/PuzzleTrainer';
type Lesson={id:string;section:string;title:string;level:string;summary:string;theme:string;exercise_count:number;format:string;source:string;order:number};
export default function Lessons(){
 const [items,setItems]=useState<Lesson[]>([]),[active,setActive]=useState<Lesson|null>(null),[section,setSection]=useState('Все');
 useEffect(()=>{api<Lesson[]>('/api/lessons').then(setItems)},[]);
 const sections=useMemo(()=>['Все',...Array.from(new Set(items.map(x=>x.section)))],[items]);
 if(active)return <div><button className="backBtn" onClick={()=>setActive(null)}>← К УРОКАМ</button><div className="sectionIntro compact"><div className="sectionCode">INTERACTIVE//{active.theme}</div><h2>{active.title}</h2><p>{active.summary} Урок = {active.exercise_count} интерактивных позиций, без текстовой простыни.</p></div><PuzzleTrainer theme={active.theme} target={active.exercise_count} onExit={()=>setActive(null)}/></div>;
 const list=items.filter(x=>section==='Все'||x.section===section);
 return <div><div className="sectionIntro"><div className="sectionCode">LEARN//BOARD FIRST</div><h2>ИНТЕРАКТИВНЫЕ УРОКИ // {items.length}</h2><p>Теория заменена практикой на доске: короткая цель → позиция → твой ход → ответ → подсказки. Серия из пяти задач закрепляет один паттерн.</p></div><div className="segmented lessonFilters">{sections.map(s=><button key={s} className={section===s?'selected':''} onClick={()=>setSection(s)}>{s.toUpperCase()}</button>)}</div><div className="lessonGrid">{list.map(l=><button className="lessonCard" onClick={()=>setActive(l)} key={l.id}><span className="tag">{l.section}</span><h3>{l.title}</h3><p>{l.summary}</p><small>{l.exercise_count} ПОЗИЦИЙ · {l.level}</small><span className="lessonGo">НАЧАТЬ →</span></button>)}</div></div>
}
