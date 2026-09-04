import {useState, type ReactNode} from 'react';
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

export default function App(){
  const [page,setPage]=useState<Page>('Главная');
  const [mobile,setMobile]=useState(false);
  const content:Record<Page, ReactNode>={Главная:<Dashboard go={setPage}/>,Учиться:<Lessons/>,Дебюты:<Openings/>,Играть:<Play/>,"Live Coach":<LiveCoach/>,Тренировки:<Training/>,Профиль:<Profile/>};
  return <div className="app">
    <header className="topbar">
      <button className="brand" onClick={()=>setPage('Главная')}>
        <span className="brandMark">C</span>
        <span className="brandWords"><b>CHESS//COACH</b><small>learn · play · analyze</small></span>
      </button>
      <nav className={mobile?'topnav open':'topnav'}>{nav.map(([n,I])=><button key={n} className={page===n?'nav active':'nav'} onClick={()=>{setPage(n);setMobile(false)}}><I size={14}/><span>{n}</span></button>)}</nav>
      <div className="systemBadge"><i></i><span>ONLINE</span></div>
      <button className="mobileMenu" onClick={()=>setMobile(!mobile)}>{mobile?<X/>:<Menu/>}</button>
    </header>
    <main>
      <div className="pageHead">
        <div className="eyebrow">// PERSONAL TRAINING SYSTEM</div>
        <div className="pageTitleRow"><h1>{page}</h1><span className="pageIndex">{String(nav.findIndex(([n])=>n===page)+1).padStart(2,'0')} / {String(nav.length).padStart(2,'0')}</span></div>
      </div>
      <div className="content">{content[page]}</div>
    </main>
  </div>
}
