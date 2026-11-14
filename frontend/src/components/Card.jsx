// A figure card: icon, label, big value, small line under it.
// tone = "good" | "bad" colours the value and the icon. `icon` is a lucide-react icon component.
export default function Card({ label, value, sub, tone, icon: Icon }) {
  return (
    <div className={`card ${tone || ''}`}>
      <div className="card-head">
        <div className="label">{label}</div>
        {Icon && <span className="card-icon"><Icon size={18} strokeWidth={2.2} /></span>}
      </div>
      <div className={`value ${tone || ''}`}>{value}</div>
      {sub && <div className="sub">{sub}</div>}
    </div>
  );
}
