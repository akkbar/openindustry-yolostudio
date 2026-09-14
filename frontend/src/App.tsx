import { useEffect, useState } from 'react';
import {
  ArrowRight, Box, Camera, Check, ChevronRight, CircleHelp, Cpu, FolderOpen,
  Images, LayoutDashboard, Monitor, Play, RefreshCw, Scan, Settings, ShieldCheck,
} from 'lucide-react';
import { fetchSystem, type SystemInfo } from './api';
import { APP_LOCALE, en, type Page } from './locales/en';

const icons = { Dashboard: LayoutDashboard, Projects: FolderOpen, Dataset: Images, Models: Box, Cameras: Camera, Runtime: Play, Settings };
const workflowIcons = [Images, Box, Camera, Scan];

export default function App() {
  const [page, setPage] = useState<Page>('Dashboard');
  const [info, setInfo] = useState<SystemInfo | null>(null);
  const [status, setStatus] = useState<'connecting' | 'connected' | 'disconnected'>('connecting');
  const [refresh, setRefresh] = useState(0);

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
  const systemRows = [
    [en.operatingSystem, info ? `${info.os} ${info.os_version}` : en.waiting],
    [en.architecture, info?.architecture ?? en.waiting],
    [en.logicalCores, info ? new Intl.NumberFormat(APP_LOCALE).format(info.logical_cpu_count) : en.waiting],
    [en.version, info?.app_version ?? en.waiting],
  ];

  return (
    <div className="app-shell">
      <aside className="sidebar">
        <div className="brand"><span className="brand-mark"><Scan size={25} /></span><div><strong>{en.brand}</strong><span>{en.company}</span></div></div>
        <div className="workspace-switch"><span className="workspace-icon"><Monitor size={18} /></span><div><strong>{en.localWorkspace}</strong><span>{en.devBuild}</span></div></div>
        <p className="nav-caption">{en.workspace}</p>
        <nav aria-label={en.workspace}>
          {(Object.keys(en.navigation) as Page[]).map((item) => {
            const Icon = icons[item];
            return <button key={item} className={`nav-item ${page === item ? 'active' : ''} ${item === 'Settings' ? 'settings-nav' : ''}`} aria-current={page === item ? 'page' : undefined} onClick={() => setPage(item)}><Icon size={19} /><span>{en.navigation[item]}</span>{page === item && <span className="active-dot" />}</button>;
          })}
        </nav>
        <div className="local-note"><ShieldCheck size={20} /><strong>{en.localFirst}</strong><p>{en.localDetail}</p></div>
        <div className="sidebar-footer"><span className="tiny-dot" />{en.versionLabel}<span>{en.devBuild}</span></div>
      </aside>

      <div className="main-shell">
        <header className="topbar"><div>{en.workspace}<ChevronRight size={14} /><strong>{en.navigation[page]}</strong></div><span className={`connection ${status}`} role="status"><span className="status-dot" />{statusLabel}</span></header>
        <main>
          <div className="page-heading"><div><p className="eyebrow">{page === 'Dashboard' ? en.setup : en.localWorkspace}</p><h1>{page === 'Dashboard' ? en.overview : en.navigation[page]}</h1><p>{page === 'Dashboard' ? en.intro : page === 'Settings' ? en.settingsDetail : en.tagline}</p></div><span className="phase-badge">{en.foundation}</span></div>

          {status === 'disconnected' && <div className="error-banner" role="alert"><CircleHelp size={20} /><span>{en.connectionFailure}</span><button onClick={() => setRefresh((value) => value + 1)}>{en.retry}</button></div>}

          {page === 'Dashboard' ? <>
            <section className="hero"><div className="hero-copy"><span className="hero-kicker"><span className="tiny-dot" />{en.brand}</span><h2>{en.welcome}</h2><p>{en.welcomeDetail}</p><button className="primary-button" onClick={() => setPage('Settings')}>{en.viewSystem}<ArrowRight size={17} /></button></div><div className="vision-art" aria-hidden="true"><div className="art-grid" /><div className="scan-frame"><i /><i /><i /><i /><Box size={88} strokeWidth={0.8} /><div className="scan-line" /></div><span className="art-cross top">+</span><span className="art-cross bottom">+</span></div></section>
            <section className="workflow-section"><div className="section-title"><div><p className="eyebrow">{en.workflow}</p><h2>{en.workflowDetail}</h2></div></div><div className="workflow-grid">{en.steps.map((step, index) => { const Icon = workflowIcons[index]; return <article className="workflow-card" key={step.title}><div className="card-top"><span className="workflow-icon"><Icon size={23} /></span><span className="step-number">0{index + 1}</span></div><h3>{step.title}</h3><p>{step.detail}</p><span className="planned"><span />{en.planned}</span></article>; })}</div></section>
          </> : page !== 'Settings' ? <section className="empty-state"><span className="empty-icon"><FolderOpen size={32} /></span><span className="planned">{en.planned}</span><h2>{en.futureTitle}</h2><p>{en.futureDetail}</p><button className="primary-button" onClick={() => setPage('Dashboard')}>{en.back}<ArrowRight size={17} /></button></section> : null}

          {(page === 'Dashboard' || page === 'Settings') && <section className="system-panel"><div className="system-heading"><span className="system-icon"><Cpu size={21} /></span><div><h2>{en.system}</h2><p>{en.systemDetail}</p></div><button className="icon-button" title={en.refresh} aria-label={en.refresh} onClick={() => setRefresh((value) => value + 1)}><RefreshCw size={17} /></button></div><dl className="system-grid">{systemRows.map(([label, value]) => <div key={label}><dt>{label}</dt><dd>{value}</dd></div>)}</dl>{page === 'Settings' && <dl className="settings-details"><div><dt>{en.processor}</dt><dd>{info?.cpu ?? en.waiting}</dd></div><div><dt>{en.python}</dt><dd>{info?.python_version ?? en.waiting}</dd></div><div><dt>{en.storage}</dt><dd className="storage-path">{info?.data_directory ?? en.waiting}</dd><p>{en.storageDetail}</p></div><div><dt>{en.language}</dt><dd>{en.english}</dd><p>{en.languageDetail}</p></div></dl>}<div className="system-footer"><span className={status === 'connected' ? 'available' : ''}>{status === 'connected' ? <Check size={14} /> : <RefreshCw size={14} />}{status === 'connected' ? en.ready : statusLabel}</span><span>{en.localWorkspace}</span></div></section>}
          <footer className="main-footer"><span>{en.brand}</span><span>{en.tagline}</span></footer>
        </main>
      </div>
    </div>
  );
}
