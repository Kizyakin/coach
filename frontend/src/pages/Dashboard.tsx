export default function Dashboard({go}:{go:(p:any)=>void}){
 return <div className="dashboard">
  <section className="hero card"><div className="heroCode">READY //</div><h2>ШАХМАТЫ БЕЗ ДОГАДОК</h2><p>Пока профиль пуст. Сыграй первую тренировочную партию или подключи Chess.com / Lichess — после этого здесь появятся только реальные данные.</p><div className="actions"><button className="primary" onClick={()=>go('Играть')}>СЫГРАТЬ ПАРТИЮ</button><button className="secondary" onClick={()=>go('Профиль')}>ПОДКЛЮЧИТЬ АККАУНТ</button></div></section>
  <div className="dashboardGrid">
   <section className="card statEmpty"><span>ПАРТИИ</span><b>0</b><p>Нет данных</p></section>
   <section className="card statEmpty"><span>ЧАСТАЯ ОШИБКА</span><b>—</b><p>Появится после анализа партий</p></section>
   <section className="card statEmpty"><span>ДЕБЮТ</span><b>—</b><p>Добавь дебют в тренировке</p></section>
   <section className="card nextAction"><span>С ЧЕГО НАЧАТЬ</span><h3>Проверь базовый алгоритм мышления</h3><p>Угроза → мат → шах → взятие → атака → план.</p><button className="textBtn" onClick={()=>go('Учиться')}>ОТКРЫТЬ УРОКИ →</button></section>
  </div>
 </div>
}
