# Infisical CLI for Unraid

A CLI-only plugin for **Unraid 7.x, x86_64**. Installs the official Infisical CLI and restores it from a verified flash cache after reboot. No settings page, background service, or credential management is included.

The initial plugin release is `2026.09.26`, pinning Infisical CLI `0.43.137`. The archive and SHA-256 are pinned through `release.json`; rebooting never upgrades the CLI.

## Build and install

Python 3.9+ is required on the development machine, not on Unraid. Choose the real GitHub repository that will host releases:

```sh
python3 scripts/build.py --repo YOUR_OWNER/unraid-infisical-cli
```

This produces `dist/unraid-infisical-cli.plg`, containing all installation and removal scripts. The build requires an explicit repository and performs no downloads. No hosted repository has been configured or published yet.

After publishing a release, open **Plugins → Install Plugin** in Unraid and paste:

```text
https://github.com/YOUR_OWNER/unraid-infisical-cli/releases/latest/download/unraid-infisical-cli.plg
```

Replace `YOUR_OWNER` with the same owner used for the build. For a local trial, copy the generated file to `/boot/unraid-infisical-cli.plg`, then run from the Unraid terminal:

```sh
plugin install /boot/unraid-infisical-cli.plg
infisical --version
```

The plugin manager registers the descriptor and reinstalls it at boot. The first installation needs HTTPS access to GitHub release downloads; subsequent boots use the cached archive. Keep the plugin's cache on the flash drive.

## Use

Use the upstream CLI directly from the Unraid terminal or scripts:

```sh
infisical --help
infisical login
infisical init
infisical run -- your-command
```

See the [official CLI documentation](https://infisical.com/docs/cli/overview) for authentication, self-hosted endpoints, and machine identities. Authentication and project configuration follow upstream CLI behavior. This plugin does not persist credentials across reboot or inject secrets into containers. Unraid's RAM-backed home directory is not persistent storage.

## Updates and removal

Use **Plugins → Check for Updates / Update** to install a newer plugin release and its pinned CLI. No background updater runs. Use **Plugins → Remove** to uninstall.

Installed paths:

- `/usr/local/bin/infisical`: symlink to the plugin-owned executable.
- `/usr/local/lib/unraid-infisical-cli/infisical`: executable in RAM.
- `/boot/config/plugins/unraid-infisical-cli/`: verified release archive on flash.

The installer refuses to overwrite an unrelated `infisical` command. Remove or relocate that installation yourself before installing this plugin. Downloads have bounded timeouts, SHA-256 checks precede extraction, and the staged executable must report the pinned version before activation. Failed downloads, checksum validation, extraction, and version checks preserve the active executable.

A corrupt cached archive causes an explicit failure. Remove only the archive named in the error and reinstall with network access to fetch a clean copy. Old release archives are removed only after successful activation. Removal preserves a replaced command, unrelated files, user authentication, and project configuration.

## Maintaining releases

1. Choose a stable release from [Infisical/cli releases](https://github.com/Infisical/cli/releases). Download `cli_VERSION_linux_amd64.tar.gz` and the release's `checksums.txt`. Confirm the exact archive name and SHA-256 entry; similarly named checksum assets may cover different platforms.
2. Update `cli_version` and `sha256` in `release.json`. The archive URL is derived from this version.
3. Increase `plugin_version` using `YYYY.MM.DD` or `YYYY.MM.DD.NN` for additional releases that day. Add the corresponding entry to `CHANGELOG.md`.
4. Run validation and the Unraid acceptance checks below.
5. Commit and push a tag matching `vPLUGIN_VERSION`, for example `v2026.09.26`. The release workflow rejects a tag that does not match metadata, validates the plugin, and publishes its `.plg` asset. Repository Actions must be enabled; the publish job requests contents-write permission.

The descriptor's update URL uses the latest GitHub release asset. Publish monotonically increasing plugin versions and keep released tags immutable. The plugin date is independent of the upstream CLI version.

## Validation

```sh
python3 scripts/check.py --require-shellcheck
shellcheck scripts/verify-upstream.sh
# Requires a Linux AMD64 environment and network access:
bash scripts/verify-upstream.sh
```

Install ShellCheck on the development machine, or omit `--require-shellcheck` to run XML, Bash syntax, and lifecycle tests locally without it. CI requires ShellCheck and runs the real upstream executable on Linux AMD64. Lifecycle tests use disposable filesystem roots, fixture archives, and mocked network/platform responses; they never install into the developer's host paths. macOS tests shim missing Linux utilities, while Linux CI uses native utilities.

### Unraid acceptance checklist

Run on a test Unraid 7.x x86_64 server before treating a release as validated for deployment:

- Install through the Plugins page; confirm plugin version and `infisical --version`.
- Reinstall the same release and confirm the cache is reused.
- Disconnect network access, reboot, and confirm `infisical --version` still works.
- Publish a newer test release and verify plugin-manager update detection and CLI replacement.
- Force a failed download or corrupt the cached archive; verify an existing installation remains usable and an actionable error is shown.
- Remove through the Plugins page; confirm the command and owned archive are gone and user configuration remains.

Automated lifecycle tests are not a substitute for boot and plugin-manager testing on Unraid itself.

## Upstream

This is an independent Unraid integration, not an official Infisical product. It downloads upstream artifacts without modifying them. Upstream licensing is included in the release archive; see [Infisical CLI](https://github.com/Infisical/cli).
