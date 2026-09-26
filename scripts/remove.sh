# Appended to common.sh by the builder.
if owned_link; then
    rm -f -- "$BIN"
elif [ -e "$BIN" ] || [ -L "$BIN" ]; then
    echo "$NAME: preserving $BIN because it is no longer owned by this plugin."
fi
rm -f -- "$RUNTIME/infisical"
rmdir "$RUNTIME" 2>/dev/null || true
for archive in "$CACHE"/cli_*_linux_amd64.tar.gz; do
    [ ! -f "$archive" ] || rm -f -- "$archive"
done
rmdir "$CACHE" 2>/dev/null || true
echo "$NAME: removed; user authentication and project files were preserved."
