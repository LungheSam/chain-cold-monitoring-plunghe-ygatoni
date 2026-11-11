# Deploying the back end on Railway

Decision D4: Railway Hobby plan, always on, **one** instance. Prices and menu names change, so
**VERIFY** each step against the Railway dashboard.

## Steps

1. Push the repository to GitHub (private repo, shared with the TA).
2. railway.com → **New Project → Deploy from GitHub repo** → pick the repo.
3. In the service **Settings**:
   - **Root Directory**: `backend`
   - **Start Command**: `npm start` (Railway runs `npm install` itself; Node version comes from
     `engines` in `package.json`)
   - **Healthcheck Path**: `/health`
   - **Replicas**: 1. Two copies would both send every SMS and both answer commands.
   - Leave **serverless / app sleeping off**: the MQTT subscriber must run all the time.
4. **Networking → Generate Domain**. You get `https://<name>.up.railway.app`.
5. **Variables** (the same names as `backend/.env.example`):

   | Variable | Value |
   |---|---|
   | `PUBLIC_BASE_URL` | `https://<name>.up.railway.app` |
   | `CORS_ORIGIN` | `https://<project-id>.web.app,https://<project-id>.firebaseapp.com,http://localhost:5173` |
   | `UNIT_IDS` | `cold-unit-01` |
   | `STORE` | `firestore` |
   | `MQTT_URL` | `mqtts://<cluster>.hivemq.cloud:8883` |
   | `MQTT_CA_FILE` | (empty: HiveMQ has a public certificate) |
   | `MQTT_USERNAME` / `MQTT_PASSWORD` | the **back end's** HiveMQ credentials (not the node's) |
   | `FIREBASE_PROJECT_ID` | your project id |
   | `FIREBASE_SERVICE_ACCOUNT` | the whole content of the service-account JSON file |
   | `AT_USERNAME` / `AT_API_KEY` | live account for the demo, sandbox before |
   | `AT_SENDER_ID` | (empty) |

   Do **not** set `PORT` (Railway sets it) or `GOOGLE_APPLICATION_CREDENTIALS` or `DEV_AUTH`.
6. Deploy. In the **Logs** you should see `MQTT connected` and, when the node is on, `cold-unit-01 online`.
7. Check from a laptop:
   ```bash
   curl https://<name>.up.railway.app/health
   curl https://<name>.up.railway.app/things/cold-unit-01
   ```

## Notes

- On redeploy Railway sends SIGTERM: the back end writes its summaries and disconnects cleanly.
- Fallback for the demo day: run `npm start` on a laptop with the same variables in `backend/.env`.
- The dashboard (Firebase Hosting) reads Firestore directly, so live values still show even if the
  back end is down; only actions and SMS need it.
