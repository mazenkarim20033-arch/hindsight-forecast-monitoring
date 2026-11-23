import { HashRouter, NavLink, Route, Routes, Navigate } from "react-router-dom";
import { Mark } from "./components/Mark";
import NextWeek from "./pages/NextWeek";
import Replay from "./pages/Replay";
import Scorecard from "./pages/Scorecard";
import Start from "./pages/Start";
import { SessionProvider, useSession } from "./state/session";

function Shell() {
  const { dataset, overview, forget } = useSession();
  const ready = Boolean(dataset && overview);
  return (
    <>
      <a className="skip" href="#main">Skip to the content</a>
      <header className="topbar">
        <NavLink to="/" className="brand" aria-label="Hindsight, start page"><Mark /><span>Hindsight</span></NavLink>
        <nav aria-label="Main">
          {ready ? (
            <>
              <NavLink to="/replay">Replay</NavLink>
              <NavLink to="/scorecard">Scorecard</NavLink>
              <NavLink to="/next">Next week</NavLink>
            </>
          ) : null}
        </nav>
        {dataset && (
          <div className="filechip" title={dataset.filename}>
            <span className="fname">{dataset.is_sample ? "Sample data" : dataset.filename}</span>
            <NavLink to="/" onClick={forget} className="change">Change file</NavLink>
          </div>
        )}
      </header>
      <main id="main" tabIndex={-1}>
        <Routes>
          <Route path="/" element={<Start />} />
          <Route path="/replay" element={<Replay />} />
          <Route path="/scorecard" element={<Scorecard />} />
          <Route path="/next" element={<NextWeek />} />
          <Route path="*" element={<Navigate to="/" replace />} />
        </Routes>
      </main>
      <footer className="foot">
        <p>Hindsight shows what a forecast would have said in the past. A good record is evidence, not a guarantee. Sample data: M5 Walmart sales, CC BY 4.0, US retail.</p>
      </footer>
    </>
  );
}

export default function App() {
  return (
    <HashRouter>
      <SessionProvider>
        <Shell />
      </SessionProvider>
    </HashRouter>
  );
}
