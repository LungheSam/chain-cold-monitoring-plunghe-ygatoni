# Development broker (Mosquitto in Docker)

Needs Docker Desktop (Windows: with the WSL 2 back end). It is **not installed** on the laptop yet.

## One-time setup

1. Make the certificates. Put your laptop's LAN IP on the command line so the Pi can connect to it
   (find it with `ipconfig`):

   ```bash
   cd broker
   ./make-certs.sh 192.168.1.50
   ```

2. Create the password file with one user per client (choose your own passwords and put the same
   ones in `edge/.env` and `backend/.env`):

   ```bash
   docker compose run --rm mosquitto mosquitto_passwd -c -b /mosquitto/config/passwd cold-unit-01 'PASSWORD1'
   docker compose run --rm mosquitto mosquitto_passwd -b /mosquitto/config/passwd backend 'PASSWORD2'
   docker compose run --rm mosquitto mosquitto_passwd -b /mosquitto/config/passwd dev 'PASSWORD3'
   ```

   `mosquitto/config/passwd` and `mosquitto/certs/` are git-ignored.

3. Start it:

   ```bash
   docker compose up -d
   docker compose logs -f
   ```

## Quick check

```bash
# Terminal 1: watch everything
mosquitto_sub -h localhost -p 8883 --cafile mosquitto/certs/ca.crt -u dev -P 'PASSWORD3' -t 'coldchain/#' -v
# Terminal 2: publish a test message
mosquitto_pub -h localhost -p 8883 --cafile mosquitto/certs/ca.crt -u dev -P 'PASSWORD3' -t coldchain/test -m hello
```

(`mosquitto_sub`/`mosquitto_pub` can also be run inside the container with `docker exec -it coldchain-mosquitto ...`.)

Windows Firewall must allow inbound TCP 8883 for the Pi to reach the laptop.

## Demo broker

For Open Day we use EMQX Cloud Serverless (free tier, TLS on 8883). See `docs/decisions.md` (D3).
