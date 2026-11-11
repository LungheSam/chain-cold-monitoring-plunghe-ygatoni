import { Navigate, NavLink, Route, Routes, useLocation } from 'react-router';
import { useState } from 'react';
import { useData } from './context.jsx';
import { UNIT_ID } from './config.js';
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
  if (user === undefined) return <p className="page muted">Loading…</p>;
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

function Layout({ children }) {
  const { data, user, role } = useData();
  const [open, setOpen] = useState(false);
  const links = [
    ['/', 'Overview'], ['/history', 'History'], ['/analytics', 'Analytics'],
    ['/excursions', 'Excursions'], ['/events', 'Events'],
  ];
  if (role === 'supervisor') links.push(['/door-qr', 'Door QR'], ['/settings', 'Settings']);
  return (
    <>
      <DemoBanner />
      <header className="topbar">
        <div className="brand">❄ Cold Chain <span className="muted">{UNIT_ID}</span></div>
        <button type="button" className="menu-button" onClick={() => setOpen(!open)} aria-label="Menu">☰</button>
        <nav className={open ? 'open' : ''} onClick={() => setOpen(false)}>
          {links.map(([to, label]) => (
            <NavLink key={to} to={to} end={to === '/'}>{label}</NavLink>
          ))}
          <span className="user">
            {user?.email} <span className="role">{role}</span>
            <button type="button" className="link" onClick={() => data.auth.signOut()}>Sign out</button>
          </span>
        </nav>
      </header>
      <main>{children}</main>
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
