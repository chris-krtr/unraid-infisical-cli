#!/bin/bash
set -euo pipefail
umask 022
NAME=unraid-infisical-cli
CACHE=/boot/config/plugins/unraid-infisical-cli
RUNTIME=/usr/local/lib/unraid-infisical-cli
BIN=/usr/local/bin/infisical
LOCK=/var/lock/unraid-infisical-cli.lock
STAGE=
DOWNLOAD=
fail() { echo "$NAME: $*" >&2; exit 1; }
cleanup() {
    [ -z "$STAGE" ] || rm -rf -- "$STAGE"
    [ -z "$DOWNLOAD" ] || rm -f -- "$DOWNLOAD"
}
trap cleanup EXIT
trap 'exit 130' INT
trap 'exit 143' TERM
[ "$(id -u)" = 0 ] || fail 'Run through the Unraid plugin manager as root.'
if [ "$(uname -s)" != Linux ] || [ "$(uname -m)" != x86_64 ]; then
    fail 'Only Linux x86_64 is supported.'
fi
[ -f /etc/unraid-version ] || fail 'Unraid 7.x is required.'
grep -Eq '^version="?7\.' /etc/unraid-version || fail 'Unraid 7.x is required.'
exec 9>"$LOCK"
flock -n 9 || fail 'Another plugin operation is in progress.'
owned_link() { [ -L "$BIN" ] && [ "$(readlink "$BIN")" = "$RUNTIME/infisical" ]; }
