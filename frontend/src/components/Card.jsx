// A figure card: label, big value, small line under it. tone = "good" | "bad" colours the value.
export default function Card({ label, value, sub, tone }) {
  return (
    <div className="card">
      <div className="label">{label}</div>
      <div className={`value ${tone || ''}`}>{value}</div>
      {sub && <div className="sub">{sub}</div>}
    </div>
  );
}
