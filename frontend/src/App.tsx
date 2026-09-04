import {useState} from 'react';
import {BookOpen, GraduationCap, Home, Swords, Radio, Dumbbell, UserRound, Menu, X} from 'lucide-react';
import Dashboard from './pages/Dashboard';
import Lessons from './pages/Lessons';
import Openings from './pages/Openings';
import Play from './pages/Play';
import LiveCoach from './pages/LiveCoach';
import Training from './pages/Training';
import Profile from './pages/Profile';

type Page='Главная'|'Учиться'|'Дебюты'|'Играть'|'Live Coach'|'Тренировки'|'Профиль';
const nav:[Page,any][]=[['Главная',Home],['Учиться',GraduationCap],['Дебюты',BookOpen],['Играть',Swords],['Live Coach',Radio],['Тренировки',Dumbbell],['Профиль',UserRound]];
export default function App(){const [page,setPage]=useState<Page>('Главная'); const [mobile,setMobile]=useState(false);
 const content={Главная:<Dashboard go={setPage}/>,Учиться:<Lessons/>,Дебюты:<Openings/>,Играть:<Play/>,"Live Coach":<LiveCoach/>,Тренировки:<Training/>,Профиль:<Profile/>}[page];
 return <div className="app"><aside className={mobile?'sidebar open':'sidebar'}><div className="brand"><div className="brandMark">♞</div><div><b>Шахматный тренер</b><span>Играй. Понимай. Расти.</span></div></div>{nav.map(([n,I])=><button key={n} className={page===n?'nav active':'nav'} onClick={()=>{setPage(n);setMobile(false)}}><I size={19}/><span>{n}</span></button>)}<div className="sidebarFoot">Версия 1.0 · Русский</div></aside><main><header><button className="mobileMenu" onClick={()=>setMobile(!mobile)}>{mobile?<X/>:<Menu/>}</button><div><div className="eyebrow">ТВОЙ ПЕРСОНАЛЬНЫЙ ТРЕНЕР</div><h1>{page}</h1></div><div className="levelPill">Уровень навыков <b>41</b></div></header><div className="content">{content}</div></main></div>}
