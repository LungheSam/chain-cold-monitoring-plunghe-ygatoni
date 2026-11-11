#!/usr/bin/env bash
# Creates a self-signed CA and a broker certificate for development.
#
# Usage (Git Bash on Windows, or Linux/macOS):
#   ./make-certs.sh                      # valid for localhost and 127.0.0.1
#   ./make-certs.sh 192.168.1.50 mylaptop.local   # also valid for your laptop's LAN IP/name,
#                                                 # so the Pi can connect to it
# Output goes to broker/mosquitto/certs/ (git-ignored). Copy ca.crt to the Pi.
set -euo pipefail

# Stop Git Bash from turning "/CN=..." into a Windows path
export MSYS_NO_PATHCONV=1

cd "$(dirname "$0")"
OUT="${CERT_DIR:-mosquitto/certs}"
mkdir -p "$OUT"

# Subject Alternative Names: always localhost, plus anything given on the command line
SAN="DNS:localhost,IP:127.0.0.1"
for h in "$@"; do
  if [[ "$h" =~ ^[0-9.]+$ ]]; then SAN="$SAN,IP:$h"; else SAN="$SAN,DNS:$h"; fi
done

# 1. Certificate authority (CA)
openssl req -x509 -newkey rsa:2048 -nodes -days 825 \
  -subj "/CN=coldchain-dev-ca" \
  -addext "basicConstraints=critical,CA:TRUE" \
  -addext "keyUsage=critical,keyCertSign,cRLSign" \
  -keyout "$OUT/ca.key" -out "$OUT/ca.crt"

# 2. Broker key and signing request
openssl req -newkey rsa:2048 -nodes \
  -subj "/CN=coldchain-broker" \
  -keyout "$OUT/server.key" -out "$OUT/server.csr"

# 3. Sign the broker certificate with the CA
EXT="$OUT/server.ext"
cat > "$EXT" <<EOF
subjectAltName=$SAN
basicConstraints=CA:FALSE
keyUsage=critical,digitalSignature,keyEncipherment
extendedKeyUsage=serverAuth
subjectKeyIdentifier=hash
authorityKeyIdentifier=keyid,issuer
EOF
openssl x509 -req -in "$OUT/server.csr" -CA "$OUT/ca.crt" -CAkey "$OUT/ca.key" \
  -CAcreateserial -days 825 -extfile "$EXT" -out "$OUT/server.crt"
rm -f "$OUT/server.csr" "$EXT"

echo "Done. SAN = $SAN"
openssl verify -x509_strict -CAfile "$OUT/ca.crt" "$OUT/server.crt"
