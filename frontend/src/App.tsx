import { useEffect, useRef, useState } from 'react';
import {
  ArrowRight, Box, Camera, Check, ChevronRight, CircleHelp, Cpu, FolderOpen,
  Images, LayoutDashboard, Monitor, Play, RefreshCw, Scan, Settings, ShieldCheck,
} from 'lucide-react';
import { fetchSystem, getDesktopInfo, openAppFolder, type DesktopInfo, type SystemInfo } from './api';
import { APP_LOCALE, APP_VERSION, en, type Page } from './locales/en';
import Projects from './pages/Projects';
import Dataset from './pages/Dataset';

const icons = { Dashboard: LayoutDashboard, Projects: FolderOpen, Dataset: Images, Models: Box, Cameras: Camera, Runtime: Play, Settings };
const workflowIcons = [Images, Box, Camera, Scan];
const readPage = (): Page => {
  const candidate = window.location.hash.slice(1).split('/')[0];
  return Object.hasOwn(en.navigation, candidate) ? candidate as Page : 'Dashboard';
};

export default function App() {
  const [page, updatePage] = useState<Page>(readPage);
  const setPage = (target: Page) => { window.location.hash = target; };
  const heading = useRef<HTMLHeadingElement>(null);
  const previousPage = useRef(page);
  const [desktop, setDesktop] = useState<DesktopInfo | null>(null);
  const [folderError, setFolderError] = useState(false);
  const [info, setInfo] = useState<SystemInfo | null>(null);
  const [status, setStatus] = useState<'connecting' | 'connected' | 'disconnected'>('connecting');
  const [refresh, setRefresh] = useState(0);

  useEffect(() => {
    const onHash = () => updatePage(readPage());
    window.addEventListener('hashchange', onHash);
    return () => window.removeEventListener('hashchange', onHash);
  }, []);

  useEffect(() => {
    const preventFileNavigation = (event: DragEvent) => event.preventDefault();
    window.addEventListener('dragover', preventFileNavigation);
    window.addEventListener('drop', preventFileNavigation);
    return () => {
      window.removeEventListener('dragover', preventFileNavigation);
      window.removeEventListener('drop', preventFileNavigation);
    };
  }, []);

  useEffect(() => {
    document.title = `${en.navigation[page]} | ${en.brand}`;
    if (previousPage.current !== page) heading.current?.focus();
    previousPage.current = page;
  }, [page]);

  useEffect(() => {
    let active = true;
    void getDesktopInfo().then(value => { if (active) setDesktop(value); }).catch(() => {});
    return () => { active = false; };
  }, []);

  const openFolder = async (kind: 'data' | 'logs') => {
    setFolderError(false);
    try { await openAppFolder(kind); } catch { setFolderError(true); }
  };

  useEffect(() => {
    let disposed = false;
    let timer: ReturnType<typeof setTimeout>;
    let controller: AbortController;
    setStatus('connecting');
    const check = async () => {
      controller = new AbortController();
      const timeout = setTimeout(() => controller.abort(), 4000);
      try {
        const result = await fetchSystem(controller.signal);
        if (!disposed) { setInfo(result); setStatus('connected'); }
      } catch {
        if (!disposed) { setInfo(null); setStatus('disconnected'); }
      } finally {
        clearTimeout(timeout);
        if (!disposed) timer = setTimeout(check, 5000);
      }
    };
    void check();
    return () => { disposed = true; clearTimeout(timer); controller?.abort(); };
  }, [refresh]);

  const statusLabel = en[status];
  const buildLabel = desktop?.mode === 'packaged' ? en.packagedBuild : desktop?.mode === 'development' ? en.devBuild : en.browserBuild;
  const appVersion = desktop?.version ?? APP_VERSION;
  const systemRows = [
    [en.operatingSystem, info ? `${info.os} ${info.os_version}` : en.waiting],
    [en.architecture, info?.architecture ?? en.waiting],
    [en.logicalCores, info ? new Intl.NumberFormat(APP_LOCALE).format(info.logical_cpu_count) : en.waiting],
    [en.version, appVersion],
  ];

  return (
    <div className="app-shell">
      <a className="skip-link" href="#main-content" onClick={event => { event.preventDefault(); heading.current?.focus(); }}>{en.skipNavigation}</a>
      <aside className="sidebar">
        <div className="brand"><span className="brand-mark"><Scan size={25} /></span><div><strong>{en.brand}</strong><span>{en.company}</span></div></div>
        <div className="workspace-switch"><span className="workspace-icon"><Monitor size={18} /></span><div><strong>{en.localWorkspace}</strong><span>{buildLabel}</span></div></div>
        <p className="nav-caption">{en.workspace}</p>
        <nav aria-label={en.workspace}>
          {(Object.keys(en.navigation) as Page[]).map((item) => {
            const Icon = icons[item];
            return <button key={item} aria-label={en.navigation[item]} className={`nav-item ${page === item ? 'active' : ''} ${item === 'Settings' ? 'settings-nav' : ''}`} aria-current={page === item ? 'page' : undefined} onClick={() => setPage(item)}><Icon size={19} /><span>{en.navigation[item]}</span>{page === item && <span className="active-dot" />}</button>;
          })}
        </nav>
        <div className="local-note"><ShieldCheck size={20} /><strong>{en.localFirst}</strong><p>{en.localDetail}</p></div>
        <div className="sidebar-footer"><span className="tiny-dot" />v{appVersion}<span>{buildLabel}</span></div>
      </aside>

      <div className="main-shell">
        <header className="topbar"><div>{en.workspace}<ChevronRight size={14} /><strong>{en.navigation[page]}</strong></div><span className={`connection ${status}`} role="status"><span className="status-dot" />{statusLabel}</span></header>
        <main id="main-content">
          <div className="page-heading"><div><p className="eyebrow">{page === 'Dashboard' ? en.setup : en.localWorkspace}</p><h1 ref={heading} tabIndex={-1}>{page === 'Dashboard' ? en.overview : en.navigation[page]}</h1><p>{page === 'Dashboard' ? en.intro : page === 'Settings' ? en.settingsDetail : page === 'Projects' ? en.projects.intro : en.tagline}</p></div><span className="phase-badge">{en.foundation}</span></div>

          {status === 'disconnected' && <div className="error-banner" role="alert"><CircleHelp size={20} /><span>{desktop?.startup_error ?? en.connectionFailure}</span><button onClick={() => setRefresh((value) => value + 1)}>{en.retry}</button></div>}

          {page === 'Dashboard' ? <>
            <section className="hero"><div className="hero-copy"><span className="hero-kicker"><span className="tiny-dot" />{en.brand}</span><h2>{en.welcome}</h2><p>{en.welcomeDetail}</p><button className="primary-button" onClick={() => setPage('Settings')}>{en.viewSystem}<ArrowRight size={17} /></button></div><div className="vision-art" aria-hidden="true"><div className="art-grid" /><div className="scan-frame"><i /><i /><i /><i /><Box size={88} strokeWidth={0.8} /><div className="scan-line" /></div><span className="art-cross top">+</span><span className="art-cross bottom">+</span></div></section>
            <section className="workflow-section"><div className="section-title"><div><p className="eyebrow">{en.workflow}</p><h2>{en.workflowDetail}</h2></div></div><div className="workflow-grid">{en.steps.map((step, index) => { const Icon = workflowIcons[index]; return <article className="workflow-card" key={step.title}><div className="card-top"><span className="workflow-icon"><Icon size={23} /></span><span className="step-number">0{index + 1}</span></div><h3>{step.title}</h3><p>{step.detail}</p><span className="planned"><span />{en.planned}</span></article>; })}</div></section>
          </> : page === 'Projects' ? <Projects /> : page === 'Dataset' ? <Dataset /> : page !== 'Settings' ? <section className="empty-state"><span className="empty-icon"><FolderOpen size={32} /></span><span className="planned">{en.planned}</span><h2>{en.futureTitle}</h2><p>{en.pageDetails[page]}</p><button className="primary-button" onClick={() => setPage('Dashboard')}>{en.back}<ArrowRight size={17} /></button></section> : null}

          {(page === 'Dashboard' || page === 'Settings') && <section className="system-panel"><div className="system-heading"><span className="system-icon"><Cpu size={21} /></span><div><h2>{en.system}</h2><p>{en.systemDetail}</p></div><button className="icon-button" title={en.refresh} aria-label={en.refresh} onClick={() => setRefresh((value) => value + 1)}><RefreshCw size={17} /></button></div><dl className="system-grid">{systemRows.map(([label, value]) => <div key={label}><dt>{label}</dt><dd>{value}</dd></div>)}</dl>{page === 'Settings' && <dl className="settings-details"><div><dt>{en.processor}</dt><dd>{info?.cpu ?? en.waiting}</dd></div><div><dt>{en.python}</dt><dd>{info?.python_version ?? en.waiting}</dd></div><div><dt>{en.storage}</dt><dd className="storage-path">{info?.data_directory ?? en.waiting}</dd><p>{en.storageDetail}</p></div><div><dt>{en.database}</dt><dd className="storage-path database-path">{info?.database_path ?? en.waiting}</dd><p>{en.databaseDetail}</p></div><div><dt>{en.language}</dt><dd>{en.english}</dd><p>{en.languageDetail}</p></div></dl>}<div className="system-footer"><span className={status === 'connected' ? 'available' : ''}>{status === 'connected' ? <Check size={14} /> : <RefreshCw size={14} />}{status === 'connected' ? en.ready : statusLabel}</span><span>{en.localWorkspace}</span></div></section>}
          {page === 'Settings' && desktop && <section className="desktop-tools"><div><strong>{en.buildType}</strong><p>{buildLabel}</p></div>{desktop.mode !== 'browser' && <div className="folder-actions"><button onClick={() => void openFolder('data')}><FolderOpen size={16} />{en.openData}</button><button onClick={() => void openFolder('logs')}><FolderOpen size={16} />{en.openLogs}</button></div>}{folderError && <p role="alert">{en.folderError}</p>}</section>}
          <footer className="main-footer"><span>{en.brand}</span><span>{en.tagline}</span></footer>
        </main>
      </div>
    </div>
  );
}
