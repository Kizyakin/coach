import {useEffect,useState} from 'react';
import {api} from '../lib/api';
import PuzzleTrainer from '../components/PuzzleTrainer';
type Theme={id:string;name:string;description:string};
export default function Training(){
 const [themes,setThemes]=useState<Theme[]>([]),[active,setActive]=useState<Theme|null>(null),[q,setQ]=useState('');
 useEffect(()=>{api<Theme[]>('/api/training/themes').then(setThemes)},[]);
 if(active)return <div><button className="backBtn" onClick={()=>setActive(null)}>← К ТРЕНАЖЁРАМ</button><PuzzleTrainer theme={active.id}/></div>;
 const list=themes.filter(x=>(x.name+x.description).toLowerCase().includes(q.toLowerCase()));
 return <div><div className="sectionIntro"><div className="sectionCode">TRAIN//OPEN DATA</div><h2>ТРЕНАЖЁРЫ // {themes.length} ТЕМ</h2><p>Задачи подгружаются из открытой базы Lichess. Это не шесть зашитых примеров: каждый запуск выдаёт новую реальную позицию.</p></div><input className="search" placeholder="ПОИСК ТЕМЫ…" value={q} onChange={e=>setQ(e.target.value)}/><div className="trainingGrid">{list.map(t=><button className="trainCard card" key={t.id} onClick={()=>setActive(t)}><span className="tag">{t.id}</span><h3>{t.name}</h3><p>{t.description}</p><span className="lessonGo">ТРЕНИРОВАТЬ →</span></button>)}</div></div>
}
