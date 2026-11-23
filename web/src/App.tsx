import { HashRouter, NavLink, Route, Routes, Navigate } from "react-router-dom";
import { LangProvider, useLang } from "./i18n";
import { Mark } from "./components/Mark";
import NextWeek from "./pages/NextWeek";
import Replay from "./pages/Replay";
import Scorecard from "./pages/Scorecard";
import Start from "./pages/Start";
import { SessionProvider, useSession } from "./state/session";

function Shell() {
  const { dataset, overview, forget } = useSession();
  const { t, lang, setLang } = useLang();
  const ready = Boolean(dataset && overview);
  return (
    <>
      <a className="skip" href="#main">{t("app.skip")}</a>
      <header className="topbar">
        <NavLink to="/" className="brand" aria-label={t("app.brand")}><Mark /><span>Hindsight</span></NavLink>
        <nav aria-label={t("nav.main")}>
          {ready ? (
            <>
              <NavLink to="/replay">{t("nav.replay")}</NavLink>
              <NavLink to="/scorecard">{t("nav.scorecard")}</NavLink>
              <NavLink to="/next">{t("nav.next")}</NavLink>
            </>
          ) : null}
        </nav>
        <div className="top-end">
          {dataset && (
            <div className="filechip" title={dataset.filename}>
              <span className="fname">{dataset.is_sample ? t("app.sample") : dataset.filename}</span>
              <NavLink to="/" onClick={forget} className="change">{t("app.change")}</NavLink>
            </div>
          )}
          <button className="lang" onClick={() => setLang(lang === "ar" ? "en" : "ar")} lang={lang === "ar" ? "en" : "ar"} aria-label={t("app.language")}>
            {lang === "ar" ? "English" : "العربية"}
          </button>
        </div>
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
        <p>{t("app.footer")}</p>
      </footer>
    </>
  );
}

export default function App() {
  return (
    <HashRouter>
      <LangProvider>
        <SessionProvider>
          <Shell />
        </SessionProvider>
      </LangProvider>
    </HashRouter>
  );
}
