#!/bin/bash
set -euo pipefail
umask 077
ROOT=/etc/gods-eye-view
STATE=/var/lib/gods-eye-view
SOURCE=$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)

prepare() {
  if ! command -v docker >/dev/null; then
    dnf -y install dnf-plugins-core openssl
    dnf config-manager --add-repo https://download.docker.com/linux/centos/docker-ce.repo
    dnf -y install docker-ce docker-ce-cli containerd.io docker-compose-plugin
  fi
  systemctl enable --now docker
  docker compose version >/dev/null
  if command -v firewall-cmd >/dev/null && firewall-cmd --state >/dev/null 2>&1; then
    firewall-cmd --permanent --add-service=https
    firewall-cmd --reload
  fi
  install -d -m 0700 "$ROOT/bootstrap" "$ROOT/oci" "$ROOT/tls" "$STATE"
  if [[ ! -f "$ROOT/bootstrap/private.pem" ]]; then
    openssl genpkey -algorithm RSA -pkeyopt rsa_keygen_bits:3072 -out "$ROOT/bootstrap/private.pem" 2>/dev/null
    chmod 0600 "$ROOT/bootstrap/private.pem"
  fi
  openssl pkey -in "$ROOT/bootstrap/private.pem" -pubout -out "$ROOT/bootstrap/public.pem"
  chmod 0644 "$ROOT/bootstrap/public.pem"
}

start() {
  for required in runtime.env oci/config tls/fullchain.pem tls/privkey.pem; do
    [[ -s "$ROOT/$required" ]] || { echo "Missing prepared runtime input: $required" >&2; exit 1; }
  done
  install -d -m 0700 "$STATE"
  exec 9>"$STATE/release.lock"
  flock -n 9 || { echo 'Another viewer release operation is active' >&2; exit 1; }
  install -d -m 0700 -o 65534 -g 65534 "$STATE/api" "$STATE/native-cache"
  chown -R 65534:65534 "$ROOT/oci"
  chmod 0600 "$ROOT/runtime.env"
  local candidate current="" receipt_name
  if [[ -f "$STATE/current-release" ]]; then
    receipt_name=$(cat "$STATE/current-release")
    [[ "$receipt_name" =~ ^release-[A-Za-z0-9]+$ ]] || { echo 'Invalid active release receipt' >&2; exit 1; }
    current="$STATE/$receipt_name"
    (cd "$current" && sha256sum --check receipt.sha256 >/dev/null) || { echo 'Active release receipt is incomplete' >&2; exit 1; }
  fi
  candidate=$(mktemp -d "$STATE/release-XXXXXXXX")
  install -m 0600 "$ROOT/runtime.env" "$candidate/runtime.env"
  # Parse only public release coordinates. Never execute the credential-bearing env file.
  for name in API_IMAGE VIEWER_IMAGE GATEWAY_IMAGE PUBLIC_HOST; do
    local value
    value=$(sed -n "s/^$name=//p" "$candidate/runtime.env")
    if [[ "$name" == PUBLIC_HOST ]]; then
      [[ "$value" =~ ^[A-Za-z0-9]([A-Za-z0-9.-]*[A-Za-z0-9])?$ ]] || { echo 'Invalid PUBLIC_HOST' >&2; exit 1; }
    else
      [[ "$value" =~ ^sha256:[a-f0-9]{64}$ ]] || { echo "Immutable local image ID required for $name" >&2; exit 1; }
      [[ "$(docker image inspect "$value" --format '{{.Id}}')" == "$value" ]] || { echo "Verified image is unavailable for $name" >&2; exit 1; }
    fi
    printf '%s=%s\n' "$name" "$value" >> "$candidate/release.env"
  done
  chmod 0600 "$candidate/release.env"
  (cd "$candidate" && sha256sum release.env runtime.env > receipt.sha256)
  local compose=(docker compose --project-directory "$SOURCE" --env-file "$candidate/release.env" -f "$SOURCE/compose.yml")
  "${compose[@]}" config --quiet
  if ! "${compose[@]}" up -d --wait --wait-timeout 180; then
    if [[ -n "$current" ]]; then
      install -m 0600 "$current/runtime.env" "$ROOT/runtime.env.pending"
      mv "$ROOT/runtime.env.pending" "$ROOT/runtime.env"
      docker compose --project-directory "$SOURCE" --env-file "$current/release.env" -f "$SOURCE/compose.yml" up -d --wait --wait-timeout 180 || { echo 'Rollback health failed; retained runtime data requires operator recovery' >&2; exit 1; }
    fi
    echo 'Candidate activation failed; no release pointer was changed' >&2
    exit 1
  fi
  if [[ -n "$current" ]]; then
    printf '%s\n' "${current##*/}" > "$STATE/previous-release.pending"
    mv "$STATE/previous-release.pending" "$STATE/previous-release"
  fi
  printf '%s\n' "${candidate##*/}" > "$STATE/current-release.pending"
  mv "$STATE/current-release.pending" "$STATE/current-release"
}

case "${1:-}" in
  prepare) prepare ;;
  start) start ;;
  *) echo 'Usage: bootstrap.sh prepare|start' >&2; exit 2 ;;
esac
