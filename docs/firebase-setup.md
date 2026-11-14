# Firebase setup (database and sign-in)

Firebase gives us **Firestore** (the database) and **Authentication** (dashboard sign-in). The
dashboard itself is hosted on Railway, not Firebase Hosting (`docs/deploy-railway.md`, D18).

## In the Firebase console (once)

1. **Authentication → Get started → Sign-in method → Email/Password → Enable**
   (leave "Email link (passwordless)" off).
2. **Authentication → Users → Add user** for every person who will sign in.
3. **Firestore Database → Create database → Production mode**. Location: `africa-south1`
   (Johannesburg), the closest to Kigali. It cannot be changed later.
4. **Firestore → Rules**: replace everything with `firebase/firestore.rules` and **Publish**.
   Signed-in users can only read; only the back end writes.
5. No indexes to create: every query uses one field, which Firestore indexes by itself.
6. **Project settings → Service accounts → Generate new private key**. Save it as
   `backend/secrets/service-account.json` (git-ignored). It gives full access to the database:
   never commit it, send it or paste it anywhere except Railway's `FIREBASE_SERVICE_ACCOUNT` variable.
   Delete the downloaded copy from your Downloads folder afterwards.
7. **Project settings → General → Your apps → Web app**: copy the four values into
   `frontend/.env.local` (`VITE_FIREBASE_API_KEY`, `_AUTH_DOMAIN`, `_PROJECT_ID`, `_APP_ID`).
8. Once the dashboard is deployed: **Authentication → Settings → Authorized domains → Add domain**
   `<dashboard>.up.railway.app`.

## On the laptop

In `backend/.env`:

```
STORE=firestore
DEV_AUTH=0
GOOGLE_APPLICATION_CREDENTIALS=./secrets/service-account.json
FIREBASE_PROJECT_ID=<your project id>
```

Give each person a role (the account must exist first, step 2), from `backend/`:

```bash
npm run set-role -- someone@example.org supervisor
npm run set-role -- someone@example.org viewer
```

Optional: `npm run seed` writes a generated week of history (about 3 300 writes; the free plan
allows 20 000 per day), so History and Analytics have something to show.

## Problems

| You see | Cause / fix |
|---|---|
| "No access yet" after signing in | no role: run `set-role` with the exact email |
| "Missing or insufficient permissions" in the browser console | rules not published (step 4) |
| `set-role`: "There is no user record" | create the user first (step 2) |
| `set-role`: "Unable to detect a Project Id" | `backend/.env` still on `STORE=memory` or the key path is wrong |
| Actions give 401 | back end still has `DEV_AUTH=1` |
