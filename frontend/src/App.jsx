import { Navigate, NavLink, Route, Routes, useLocation } from 'react-router';
import { useState } from 'react';
import {
  ChartColumn, ChartLine, LayoutDashboard, LogOut, Menu, QrCode, ScrollText, Settings as SettingsIcon,
  Snowflake, ThermometerSun, X,
} from 'lucide-react';
import { useData } from './context.jsx';
import { UNIT_ID } from './config.js';
import { ThemeToggle } from './theme.jsx';
import Login from './pages/Login.jsx';
import Overview from './pages/Overview.jsx';
import History from './pages/History.jsx';
import Analytics from './pages/Analytics.jsx';
import Excursions from './pages/Excursions.jsx';
import EventsLog from './pages/EventsLog.jsx';
import Settings from './pages/Settings.jsx';
import Unlock from './pages/Unlock.jsx';
import DoorQr from './pages/DoorQr.jsx';

function RequireAuth({ children }) {
  const { user, role } = useData();
  const location = useLocation();
  if (user === undefined) return <p className="page loading"><span className="spinner" />Loading…</p>;
  if (!user) return <Navigate to="/login" state={{ from: location.pathname }} replace />;
  if (!role) {
    return (
      <div className="page narrow">
        <h1>No access yet</h1>
        <p>You are signed in as {user.email}, but you have no role. Ask a supervisor to run
          <code> npm run set-role -- {user.email} viewer</code> in the back end.</p>
      </div>
    );
  }
  return children;
}

function DemoBanner() {
  const { data } = useData();
  const [heating, setHeating] = useState(false);
  if (!data.demo) return null;
  return (
    <div className="demo-banner">
      Demo mode: generated data, no Firebase.
      <button type="button" className="small" onClick={() => setHeating(data.simulateAlarm())}>
        {heating ? 'Cool the probe again' : 'Simulate a warm probe'}
      </button>
    </div>
  );
}

const LINKS = [
  ['/', 'Overview', LayoutDashboard],
  ['/history', 'History', ChartLine],
  ['/analytics', 'Analytics', ChartColumn],
  ['/excursions', 'Excursions', ThermometerSun],
  ['/events', 'Events', ScrollText],
];
const SUPERVISOR_LINKS = [['/door-qr', 'Door QR', QrCode], ['/settings', 'Settings', SettingsIcon]];

function Layout({ children }) {
  const { data, user, role } = useData();
  const location = useLocation();
  const [open, setOpen] = useState(false);
  const links = role === 'supervisor' ? [...LINKS, ...SUPERVISOR_LINKS] : LINKS;
  return (
    <>
      <DemoBanner />
      <header className="topbar">
        {/* Row 1: logo on the left, account on the right */}
        <div className="topbar-row">
          <div className="brand">
            <span className="brand-mark"><Snowflake size={20} strokeWidth={2.4} /></span>
            <span>Cold Chain <span className="unit-id">{UNIT_ID}</span></span>
          </div>
          <div className="account desktop-only">
            <span className="avatar" aria-hidden="true">{(user?.email || '?')[0].toUpperCase()}</span>
            <span className="account-text">
              <span className="email">{user?.email}</span>
              <span className="role">{role}</span>
            </span>
            <ThemeToggle />
            <button type="button" className="icon-button" onClick={() => data.auth.signOut()} aria-label="Sign out" title="Sign out">
              <LogOut size={17} />
            </button>
          </div>
          {/* Phones: theme + menu button instead */}
          <div className="topbar-actions menu-button">
            <ThemeToggle />
            <button type="button" className="icon-button" onClick={() => setOpen(!open)} aria-label="Menu" aria-expanded={open}>
              {open ? <X size={18} /> : <Menu size={18} />}
            </button>
          </div>
        </div>

        {/* Row 2: the menu (on phones it folds open under the button) */}
        <nav className={open ? 'open' : ''} onClick={() => setOpen(false)}>
          <div className="nav-links">
            {links.map(([to, label, Icon]) => (
              <NavLink key={to} to={to} end={to === '/'}><Icon size={16} strokeWidth={2.2} />{label}</NavLink>
            ))}
          </div>
          <div className="user mobile-only">
            <span className="email">{user?.email}</span>
            <span className="role">{role}</span>
            <button type="button" className="icon-button" onClick={() => data.auth.signOut()} aria-label="Sign out" title="Sign out">
              <LogOut size={17} />
            </button>
          </div>
        </nav>
      </header>
      {/* key: replays the fade-in each time the page changes */}
      <main key={location.pathname} className="page-enter">{children}</main>
    </>
  );
}

export default function App() {
  const page = (element) => <RequireAuth><Layout>{element}</Layout></RequireAuth>;
  return (
    <Routes>
      <Route path="/login" element={<Login />} />
      <Route path="/" element={page(<Overview />)} />
      <Route path="/history" element={page(<History />)} />
      <Route path="/analytics" element={page(<Analytics />)} />
      <Route path="/excursions" element={page(<Excursions />)} />
      <Route path="/events" element={page(<EventsLog />)} />
      <Route path="/settings" element={page(<Settings />)} />
      <Route path="/door-qr" element={page(<DoorQr />)} />
      {/* Opened from the QR code on the fridge: phone layout, no menu */}
      <Route path="/unlock/:unitId" element={<RequireAuth><DemoBanner /><Unlock /></RequireAuth>} />
      <Route path="*" element={<Navigate to="/" replace />} />
    </Routes>
  );
}
