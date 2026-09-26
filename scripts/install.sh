# Appended to common.sh by the builder, after pinned release constants.
if [ -e "$BIN" ] || [ -L "$BIN" ]; then
    owned_link || fail "Installation conflict: $BIN is not owned by this plugin."
fi
# Catch an installation elsewhere on PATH as well.
EXISTING=$(command -v infisical || true)
[ -z "$EXISTING" ] || [ "$EXISTING" = "$BIN" ] || fail "Installation conflict: infisical already exists at $EXISTING."
mkdir -p "$CACHE" "$RUNTIME" "$(dirname "$BIN")"
ARCHIVE="$CACHE/cli_${CLI_VERSION}_linux_amd64.tar.gz"
verify() { echo "$SHA256  $1" | sha256sum -c - >/dev/null 2>&1; }
if [ -f "$ARCHIVE" ]; then
    verify "$ARCHIVE" || fail "Checksum mismatch in cached archive: $ARCHIVE. Remove that file and retry."
else
    DOWNLOAD=$(mktemp "$CACHE/.download.XXXXXX")
    curl --fail --location --silent --show-error --proto '=https' --proto-redir '=https' \
        --connect-timeout 20 --max-time 300 --retry 2 --output "$DOWNLOAD" "$URL" \
        || fail 'Download failed; existing installation was preserved.'
    verify "$DOWNLOAD" || fail 'Downloaded archive SHA-256 checksum mismatch.'
    mv -f -- "$DOWNLOAD" "$ARCHIVE"
    DOWNLOAD=
fi
STAGE=$(mktemp -d "$RUNTIME/.stage.XXXXXX")
# Stream only the named binary, never extract arbitrary archive paths onto the host.
tar -xOzf "$ARCHIVE" infisical > "$STAGE/infisical" || fail 'Cannot extract infisical from archive.'
chmod 0755 "$STAGE/infisical"
VERSION_OUTPUT=$("$STAGE/infisical" --version) || fail 'Staged CLI failed its version check.'
[[ "$VERSION_OUTPUT" =~ (^|[^0-9.])${CLI_VERSION//./\.}([^0-9.]|$) ]] \
    || fail "Staged CLI reports an unexpected version: $VERSION_OUTPUT"
# Rename on the same filesystem leaves the old executable intact until activation.
mv -f -- "$STAGE/infisical" "$RUNTIME/infisical"
if ! owned_link; then
    ln -s "$RUNTIME/infisical" "$BIN" || fail "Could not create $BIN."
fi
# Keep only the successful release in the flash cache.
for old in "$CACHE"/cli_*_linux_amd64.tar.gz; do
    [ "$old" = "$ARCHIVE" ] || [ ! -f "$old" ] || rm -f -- "$old"
done
echo "$NAME: installed $VERSION_OUTPUT"
