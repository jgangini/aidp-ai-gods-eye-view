#!/bin/bash
# Exercises the real activation function with only temporary fixtures and fake Docker.
set -euo pipefail
BOOTSTRAP=$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")/.." && pwd)/bootstrap.sh
WORK=$(mktemp -d "${TMPDIR:-/tmp}/gev-bootstrap-test.XXXXXXXX")
TEMP_ROOT=$(realpath "${TMPDIR:-/tmp}")
[[ "$(dirname "$(realpath "$WORK")")" == "$TEMP_ROOT" && "${WORK##*/}" == gev-bootstrap-test.* ]]
trap 'rm -rf -- "$WORK"' EXIT
source <(sed '/^case "${1:-}" in/,$d' "$BOOTSTRAP")
ROOT="$WORK/config"
STATE="$WORK/state"
SOURCE="$WORK/source"
mkdir -p "$ROOT/oci" "$ROOT/tls" "$STATE" "$SOURCE"
for file in oci/config tls/fullchain.pem tls/privkey.pem; do printf 'fixture\n' > "$ROOT/$file"; done

chown() { :; }
flock() { :; }
install() {
  local args=() directory=false
  while [[ $# -gt 0 ]]; do
    case "$1" in -o|-g|-m) shift 2 ;; -d) directory=true; shift ;; *) args+=("$1"); shift ;; esac
  done
  if "$directory"; then mkdir -p "${args[@]}"; else cp "${args[@]}"; fi
}
docker() {
  if [[ "${1:-} ${2:-}" == 'image inspect' ]]; then printf '%s\n' "$3"; return 0; fi
  local envfile="" previous=""
  for arg in "$@"; do
    [[ "$previous" != --env-file ]] || envfile="$arg"
    previous="$arg"
  done
  if [[ " $* " == *" up "* ]]; then
    if [[ -f "$WORK/fail-once" ]]; then rm "$WORK/fail-once"; return 1; fi
    if [[ -f "$WORK/check-rollback" ]]; then
      cmp -s "$ROOT/runtime.env" "$WORK/baseline.env"
      cmp -s "$envfile" "$WORK/baseline-release.env"
      printf 'verified\n' > "$WORK/rollback-verified"
    fi
  fi
}

write_env() {
  local version="$1" digest
  printf -v digest '%064d' "$version"
  printf 'API_IMAGE=sha256:%s\nVIEWER_IMAGE=sha256:%s\nGATEWAY_IMAGE=sha256:%s\nPUBLIC_HOST=viewer.example\nTOKEN=fixture-%s\n' "$digest" "$digest" "$digest" "$version" > "$ROOT/runtime.env"
}

write_env 1
cp "$ROOT/runtime.env" "$WORK/baseline.env"
(start)
pointer=$(cat "$STATE/current-release")
cp "$STATE/$pointer/release.env" "$WORK/baseline-release.env"
cmp -s "$STATE/$pointer/runtime.env" "$WORK/baseline.env"
(cd "$STATE/$pointer" && sha256sum --check receipt.sha256 >/dev/null)

write_env 2
touch "$WORK/fail-once" "$WORK/check-rollback"
if (start); then echo 'Expected candidate activation failure' >&2; exit 1; fi
[[ -f "$WORK/rollback-verified" ]]
[[ "$(cat "$STATE/current-release")" == "$pointer" ]]
cmp -s "$ROOT/runtime.env" "$WORK/baseline.env"
echo 'PASS: failed candidate restores matching runtime config, images and active receipt'
