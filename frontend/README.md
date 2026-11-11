# Dashboard (React + Vite)

Scaffolded in **Phase 4**. Planned stack: React, Vite, React Router, Firebase JS SDK (Auth + Firestore
real-time listeners), Chart.js via `react-chartjs-2`, `qrcode.react`.

- Live data is read straight from Firestore. The back end is called only for actions.
- `npm run build` will write to `../firebase/public` so that `firebase deploy` (run from `firebase/`) hosts it.
- Config: copy `.env.example` to `.env.local`.
