import { HashRouter, NavLink, Navigate, Route, Routes } from "react-router-dom";
import { IS_SNAPSHOT } from "./api/client";
import { ErrorBox } from "./components/States";
import { useEffect } from "react";
import { LangProvider, nounFor, useLang } from "./i18n";
import Dashboard from "./pages/Dashboard";
import Data from "./pages/Data";
import ItemDetail from "./pages/ItemDetail";
import Items from "./pages/Items";
import Effects from "./pages/Effects";
import Planner from "./pages/Planner";
import Replay from "./pages/Replay";
import Scorecard from "./pages/Scorecard";
import { SessionProvider, useSession } from "./state/session";
import { pct } from "./lib/format";

function Boot() {
  const { job, problem } = useSession();
  const { t } = useLang();
  const p = job?.progress ?? 0;
  return (
    <div className="boot" role="status" aria-live="polite">
      <h1>{t("boot.title")}</h1>
      <p className="muted">{t("boot.text")}</p>
      <div className="bar" role="progressbar" aria-valuemin={0} aria-valuemax={100} aria-valuenow={Math.round(p * 100)} aria-label={t("run.progress")}><span style={{ width: `${Math.max(3, p * 100)}%` }} /></div>
      <p className="fine">{t("run.done", { pct: pct(p) })}</p>
      {problem && <ErrorBox problem={problem} />}
    </div>
  );
}

function Shell() {
  const { dataset, overview, booting, problem } = useSession();
  const { t, lang, setLang, setNoun } = useLang();
  const header = dataset?.detection.item;
  useEffect(() => setNoun(nounFor(header)), [header, setNoun]);
  const ready = Boolean(dataset && overview);
  return (
    <>
      <a className="skip" href="#main">{t("app.skip")}</a>
      <section className="banner" aria-label="Data notice">
        {dataset && !dataset.is_sample ? t("banner.own", { name: dataset.filename }) : t("banner.sample")}
        {IS_SNAPSHOT && ` ${t("banner.snapshot")}`}
      </section>
      <header className="topbar">
        <NavLink to="/" className="brand" aria-label={t("app.brand")}>Hindsight<small>{t("brand.tag")}</small></NavLink>
        <nav className="nav" aria-label={t("nav.main")}>
          <NavLink to="/" end>{t("nav.dashboard")}</NavLink>
          <NavLink to="/items">{t("nav.items")}</NavLink>
          <NavLink to="/planner">{t("nav.planner")}</NavLink>
          <NavLink to="/effects">{t("nav.effects")}</NavLink>
          <NavLink to="/lab">{t("nav.lab")}</NavLink>
          <NavLink to="/scorecard">{t("nav.scorecard")}</NavLink>
          <NavLink to="/data">{t("nav.data")}</NavLink>
        </nav>
        <div className="top-end">
          <button className="lang" onClick={() => setLang(lang === "ar" ? "en" : "ar")} lang={lang === "ar" ? "en" : "ar"} aria-label={t("app.language")}>
            {lang === "ar" ? "English" : "العربية"}
          </button>
        </div>
      </header>
      <main className="main" id="main" tabIndex={-1}>
        {booting ? <Boot /> : !ready ? (
          <>
            {!problem && <ErrorBox problem={{ message: t("boot.failed") }} />}
            <Routes><Route path="/data" element={<Data />} /><Route path="*" element={<Navigate to="/data" replace />} /></Routes>
          </>
        ) : (
          <Routes>
            <Route path="/" element={<Dashboard />} />
            <Route path="/items" element={<Items />} />
            <Route path="/items/:id" element={<ItemDetail />} />
            <Route path="/planner" element={<Planner />} />
            <Route path="/effects" element={<Effects />} />
            <Route path="/lab" element={<Replay />} />
            <Route path="/scorecard" element={<Scorecard />} />
            <Route path="/data" element={<Data />} />
            <Route path="*" element={<Navigate to="/" replace />} />
          </Routes>
        )}
      </main>
      <footer className="foot"><p>{t("app.footer")}</p></footer>
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
