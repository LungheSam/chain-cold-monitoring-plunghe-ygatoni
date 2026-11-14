// Supervisor settings: alarm thresholds and delays (sent to the node through the back end) and
// the SMS contacts (stored by the back end; phone numbers never live in the code).
import { useEffect, useState } from 'react';
import { MessageSquare, Plus, Save, Settings as SettingsIcon, SlidersHorizontal, Trash2 } from 'lucide-react';
import { useData, useUnit } from '../context.jsx';
import { UNIT_ID } from '../config.js';

function Thresholds() {
  const { data } = useData();
  const unit = useUnit();
  const [form, setForm] = useState(null);
  const [result, setResult] = useState(null);

  useEffect(() => {
    if (unit?.thresholds && !form) setForm({ ...unit.thresholds });
  }, [unit, form]);

  if (!form) return <p className="muted">Loading…</p>;

  const field = (name, label, step, unitText) => (
    <label>{label} ({unitText})
      <input type="number" step={step} value={form[name]} onChange={(e) => setForm({ ...form, [name]: e.target.value })} required />
    </label>
  );

  async function save(e) {
    e.preventDefault();
    const body = {
      minC: Number(form.minC), maxC: Number(form.maxC),
      confirmDelayS: Math.round(Number(form.confirmDelayS)), doorLimitS: Math.round(Number(form.doorLimitS)),
    };
    if (!(body.minC < body.maxC)) return setResult({ error: 'The minimum must be below the maximum.' });
    setResult({ busy: true });
    const res = await data.api.putThresholds(UNIT_ID, body);
    setResult(res.ok ? { ok: 'Saved on the unit.' } : { error: res.data?.error || `failed (${res.status})` });
  }

  return (
    <form className="panel" onSubmit={save}>
      <div className="grid-2" style={{ gap: '0 16px' }}>
        {field('minC', 'Minimum temperature', '0.1', '°C')}
        {field('maxC', 'Maximum temperature', '0.1', '°C')}
        {field('confirmDelayS', 'Alarm after out of range for', '1', 's')}
        {field('doorLimitS', 'Door alarm after open for', '1', 's')}
      </div>
      <p className="muted" style={{ fontSize: '0.85rem' }}>
        WHO range for most vaccines: +2 to +8 °C. The change is sent to the unit; it fails if the unit is offline.
      </p>
      {result?.ok && <p className="success">{result.ok}</p>}
      {result?.error && <p className="error">{result.error}</p>}
      <button type="submit" disabled={result?.busy}>{result?.busy ? <><span className="spinner" />Saving…</> : <><Save size={16} />Save thresholds</>}</button>
    </form>
  );
}

function Contacts() {
  const { data } = useData();
  const [contacts, setContacts] = useState(null);
  const [form, setForm] = useState({ name: '', phone: '' });
  const [message, setMessage] = useState(null);

  async function reload() {
    const res = await data.api.listContacts();
    if (res.ok) setContacts(res.data);
    else setMessage({ error: res.data?.error || `could not load contacts (${res.status})` });
  }

  useEffect(() => {
    reload();
  }, [data]); // eslint-disable-line react-hooks/exhaustive-deps

  async function add(e) {
    e.preventDefault();
    const res = await data.api.saveContact(null, { name: form.name.trim(), phone: form.phone.replace(/\s/g, '') });
    if (!res.ok) return setMessage({ error: res.data?.error || `failed (${res.status})` });
    setForm({ name: '', phone: '' });
    setMessage({ ok: 'Contact added.' });
    reload();
  }

  async function toggle(c) {
    const { id, ...body } = c;
    await data.api.saveContact(id, { ...body, active: !c.active });
    reload();
  }

  async function remove(c) {
    if (!window.confirm(`Remove ${c.name} (${c.phone})?`)) return;
    await data.api.deleteContact(c.id);
    reload();
  }

  return (
    <>
      <div className="table-wrap">
        <table>
          <thead><tr><th>Name</th><th>Phone</th><th>SMS</th><th /></tr></thead>
          <tbody>
            {!contacts && <tr><td colSpan="4" className="muted">Loading…</td></tr>}
            {contacts?.length === 0 && <tr><td colSpan="4" className="muted">No contacts: alerts will not be sent.</td></tr>}
            {(contacts || []).map((c) => (
              <tr key={c.id}>
                <td>{c.name}</td>
                <td>{c.phone}</td>
                <td><button type="button" className="small secondary" onClick={() => toggle(c)}>{c.active === false ? 'off' : 'on'}</button></td>
                <td><button type="button" className="small danger" onClick={() => remove(c)}><Trash2 size={14} />Remove</button></td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
      <form className="panel" style={{ marginTop: 12 }} onSubmit={add}>
        <div className="grid-2" style={{ gap: '0 16px' }}>
          <label>Name<input value={form.name} onChange={(e) => setForm({ ...form, name: e.target.value })} required maxLength={60} /></label>
          <label>Phone (international format)
            <input value={form.phone} placeholder="+250788123456" onChange={(e) => setForm({ ...form, phone: e.target.value })} required />
          </label>
        </div>
        {message?.ok && <p className="success">{message.ok}</p>}
        {message?.error && <p className="error">{message.error}</p>}
        <button type="submit"><Plus size={16} />Add contact</button>
      </form>
    </>
  );
}

export default function Settings() {
  const { role } = useData();
  if (role !== 'supervisor') return <p>Only supervisors can change settings.</p>;
  return (
    <>
      <h1 className="page-title"><SettingsIcon size={24} />Settings</h1>
      <h2 className="page-title"><SlidersHorizontal size={18} />Alarm thresholds</h2>
      <Thresholds />
      <h2 className="page-title"><MessageSquare size={18} />SMS contacts</h2>
      <p className="muted">These numbers get the alert SMS (at most one per alarm type every 15 minutes) and the follow-up when it clears.</p>
      <Contacts />
    </>
  );
}
