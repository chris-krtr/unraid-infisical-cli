#!/bin/bash
# Run on Linux AMD64, independently of the Unraid installer.
set -euo pipefail
cd "$(dirname "$0")/.."
if [ "$(uname -s)" != Linux ] || [ "$(uname -m)" != x86_64 ]; then
    echo 'This smoke test requires Linux AMD64.' >&2
    exit 1
fi
version=$(python3 -c 'import json; print(json.load(open("release.json"))["cli_version"])')
checksum=$(python3 -c 'import json; print(json.load(open("release.json"))["sha256"])')
work=$(mktemp -d)
trap 'rm -rf "$work"' EXIT
curl --fail --location --silent --show-error --proto '=https' --proto-redir '=https' \
    --connect-timeout 20 --max-time 300 --retry 2 \
    "https://github.com/Infisical/cli/releases/download/v${version}/cli_${version}_linux_amd64.tar.gz" \
    --output "$work/cli.tar.gz"
echo "$checksum  $work/cli.tar.gz" | sha256sum -c -
tar -xOzf "$work/cli.tar.gz" infisical > "$work/infisical"
chmod 0755 "$work/infisical"
output=$("$work/infisical" --version)
echo "$output"
[[ "$output" =~ (^|[^0-9.])${version//./\.}([^0-9.]|$) ]]
