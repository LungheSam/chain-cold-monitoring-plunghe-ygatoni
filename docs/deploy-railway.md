# Deployment: Railway (back end + dashboard) and EMQX Cloud (MQTT)

Two hosting services (decisions D3, D4, D18):

| Part | Where | Address |
|---|---|---|
| MQTT broker | EMQX Cloud Serverless (free) | `mqtts://<deployment>.<region>.emqxsl.com:8883` |
| Back end | Railway service 1, root `backend/` | `https://<backend>.up.railway.app` |
| Dashboard + unlock page | Railway service 2, root `frontend/` | `https://<dashboard>.up.railway.app` |
| Database + sign-in | Firebase (Firestore + Authentication, no hosting) | console.firebase.google.com |

Railway's and EMQX's menu names change from time to time: **VERIFY** each step against their consoles.
Keep every password and key in Railway's Variables only, never in the repository.

## 0. Before you start

- The repository is on GitHub (private, shared with the TA), and `git status` shows no `.env` files.
- Firebase is set up: Email/Password sign-in on, both users created and given roles, Firestore rules
  published (`docs/firebase-setup.md`).
- You have `backend/secrets/service-account.json` on your laptop.

## 1. EMQX Cloud Serverless (the broker)

(HiveMQ's free plan closed to new clusters on 30 Sep 2026, see D3.)

1. Sign up at **emqx.com → Cloud** (EMQX Cloud console) and create a new deployment:
   choose **Serverless**, any region near Europe, and keep the **monthly spend limit at 0**
   (free quota only: it can never be billed).
2. Open the deployment. On its **Overview** note the **connection address** (it ends in
   `emqxsl.com`) and the **MQTT over TLS port 8883**. You do not need the CA file: the certificate
   is public, so leave `MQTT_CA_FILE` empty.
3. **Access Control → Authentication → Add**: create two users with strong, different passwords:
   - `backend` (for the Railway back end)
   - `cold-unit-1` (for the Pi; the Thing is still called `cold-unit-01`)
   If **Authorization** (topic rules) is offered, allow both users only `coldchain/#`.
4. Test it from the laptop first: in `backend/.env` and `edge/.env` switch to the commented
   cloud-broker lines (address, port 8883, TLS on, the two users), then run `npm run dev`
   (backend) and the node. Both must log `MQTT connected`. Then VERIFY that killing the node makes
   the dashboard show OFFLINE within seconds (Last Will) and that the status survives a back-end
   restart (retained message).

## 2. Railway service 1: the back end

1. railway.com → **New Project → Deploy from GitHub repo** → pick the repo.
2. Service **Settings**:
   - **Root Directory**: `backend`
   - **Start Command**: `npm start` (Railway runs `npm install` itself; Node version from `engines`)
   - **Healthcheck Path**: `/health`
   - **Replicas: 1.** Two copies would both send every SMS and both answer commands.
   - **App sleeping / serverless: off.** The MQTT subscriber must run all the time.
3. **Networking → Generate Domain** → note `https://<backend>.up.railway.app`.
4. **Variables**:

   | Variable | Value |
   |---|---|
   | `PUBLIC_BASE_URL` | `https://<backend>.up.railway.app` |
   | `CORS_ORIGIN` | `https://<dashboard>.up.railway.app,http://localhost:5173` (fill in after step 3) |
   | `UNIT_IDS` | `cold-unit-01` |
   | `STORE` | `firestore` |
   | `FIREBASE_PROJECT_ID` | your project id |
   | `FIREBASE_SERVICE_ACCOUNT` | the **whole content** of `service-account.json` (Railway holds no files) |
   | `MQTT_URL` | `mqtts://<deployment>.<region>.emqxsl.com:8883` (the address from step 1) |
   | `MQTT_USERNAME` / `MQTT_PASSWORD` | the **`backend`** EMQX user |
   | `AT_USERNAME` / `AT_API_KEY` | Africa's Talking live app (`coldchainmonitoring`); empty key = SMS only in the log |
   | `TELEGRAM_BOT_TOKEN` / `TELEGRAM_CHAT_IDS` | Telegram backup channel (optional; see `backend/README.md`) |

   Do **not** set `PORT` (Railway sets it), `DEV_AUTH`, `GOOGLE_APPLICATION_CREDENTIALS` or `MQTT_CA_FILE`.
5. Deploy. The **Logs** must show `HTTP on port ...` and `MQTT connected to mqtts://...`.
6. Check: `https://<backend>.up.railway.app/health` answers `{"ok":true,...}` and
   `https://<backend>.up.railway.app/things/cold-unit-01` shows the Thing Description.

## 3. Railway service 2: the dashboard

1. In the same project: **New → GitHub Repo** → the same repo again.
2. Service **Settings**:
   - **Root Directory**: `frontend`
   - **Build Command**: `npm run build` (Railway usually finds it by itself)
   - **Start Command**: `npm start` (runs `frontend/server.mjs`, a small server with no dependencies)
   - **Healthcheck Path**: `/health`
3. **Networking → Generate Domain** → note `https://<dashboard>.up.railway.app`.
4. **Variables**. These are put **into the build**, so after changing one, redeploy:

   | Variable | Value |
   |---|---|
   | `VITE_FIREBASE_API_KEY`, `VITE_FIREBASE_AUTH_DOMAIN`, `VITE_FIREBASE_PROJECT_ID`, `VITE_FIREBASE_APP_ID` | same as in `frontend/.env.local` |
   | `VITE_BACKEND_URL` | `https://<backend>.up.railway.app` |
   | `VITE_UNIT_ID` | `cold-unit-01` |

5. Deploy, and check that `https://<dashboard>.up.railway.app/health` answers `ok`.

## 4. Connect them

1. **Back end → Variables → `CORS_ORIGIN`**: put the dashboard address
   (`https://<dashboard>.up.railway.app,http://localhost:5173`). Railway redeploys the back end.
2. **Firebase console → Authentication → Settings → Authorized domains → Add domain**:
   `<dashboard>.up.railway.app`. Without it, sign-in on the deployed dashboard is refused.
3. Open the dashboard on a phone, sign in as a supervisor, then run the node (laptop or Pi) with
   `edge/.env` on EMQX with the `cold-unit-1` user. Type `temp 9.5`: the dashboard turns
   WARNING then ALARM, and **Acknowledge** works (that call goes through Railway).
4. **Door QR** page: print the label **from the deployed dashboard** (the code contains its address).

## When something goes wrong

| Symptom | Likely cause |
|---|---|
| Back end log: `MQTT error: Not authorized` | wrong `MQTT_USERNAME`/`MQTT_PASSWORD`, or the node's user used by the back end |
| Back end log: `Cannot listen on port` | `PORT` was set by hand: delete it |
| Back end crashes at start mentioning credentials | `FIREBASE_SERVICE_ACCOUNT` is not the complete JSON (copy the whole file) |
| Dashboard sign-in: "unauthorized domain" | step 4.2 missing |
| Dashboard works, buttons fail with a CORS error | `CORS_ORIGIN` on the back end lacks the dashboard address (exact, with `https://`, no trailing `/`) |
| Dashboard still calls `localhost:3000` / `8080` | `VITE_BACKEND_URL` set after the build: redeploy the dashboard |
| Unit stays OFFLINE | the node is not connected to EMQX (check `edge/.env`) |
| Everything stops connecting one day | EMQX free quota used up (check Usage in the EMQX console; it resets monthly) |

## Notes

- Redeploys: Railway sends SIGTERM; the back end saves its summaries and disconnects cleanly.
- Every push to GitHub redeploys both services (Railway's default). Push before the demo, not during it.
- Live values still show if the back end is down (the dashboard reads Firestore directly); only
  actions (acknowledge, thresholds, unlock), SMS and the Web Thing API need it.
- Demo-day fallback: run the back end and dashboard on a laptop (`npm run dev` in both) with the
  EMQX settings in `backend/.env`.
