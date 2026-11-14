import { useState } from 'react';
import { Navigate, useLocation } from 'react-router';
import { LogIn, Snowflake } from 'lucide-react';
import { useData } from '../context.jsx';
import { ThemeToggle } from '../theme.jsx';

export default function Login() {
  const { data, user } = useData();
  const location = useLocation();
  const [email, setEmail] = useState('');
  const [password, setPassword] = useState('');
  const [error, setError] = useState('');
  const [busy, setBusy] = useState(false);

  if (user) return <Navigate to={location.state?.from || '/'} replace />;

  async function submit(e) {
    e.preventDefault();
    setBusy(true);
    setError('');
    try {
      await data.auth.signIn(email.trim(), password);
    } catch {
      setError('Wrong email or password.');
    } finally {
      setBusy(false);
    }
  }

  return (
    <div className="auth-page">
      <div className="auth-card">
        <ThemeToggle />
        <span className="brand-mark"><Snowflake size={26} strokeWidth={2.4} /></span>
        <h1>Cold Chain Monitor</h1>
        <p className="muted" style={{ marginTop: 0 }}>Sign in to see the vaccine storage units.</p>
        {data.demo && <p className="pill warn">Demo mode: any email and password work.</p>}
        <form onSubmit={submit}>
          <label>Email
            <input type="email" autoComplete="username" value={email} onChange={(e) => setEmail(e.target.value)} required={!data.demo} />
          </label>
          <label>Password
            <input type="password" autoComplete="current-password" value={password} onChange={(e) => setPassword(e.target.value)} required={!data.demo} />
          </label>
          {error && <p className="error">{error}</p>}
          <button type="submit" disabled={busy}>
            {busy ? <><span className="spinner" />Signing in…</> : <><LogIn size={18} />Sign in</>}
          </button>
        </form>
      </div>
    </div>
  );
}
