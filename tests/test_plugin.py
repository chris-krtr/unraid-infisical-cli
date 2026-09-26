"""Run the generated PLG lifecycle in temporary roots with fixture release archives."""
import hashlib
import importlib.util
import io
import os
from pathlib import Path
import shutil
import subprocess
import sys
import tarfile
import tempfile
import unittest
import xml.etree.ElementTree as ET

ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location("build", ROOT / "scripts/build.py")
build = importlib.util.module_from_spec(spec)
spec.loader.exec_module(build)


class PluginTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.mock = self.root / "mock"
        self.mock.mkdir()
        self.cache = self.root / "boot/config/plugins/unraid-infisical-cli"
        self.runtime = self.root / "usr/local/lib/unraid-infisical-cli"
        self.binary = self.root / "usr/local/bin/infisical"
        self.binary.parent.mkdir(parents=True)
        (self.root / "var/lock").mkdir(parents=True)
        (self.root / "etc").mkdir()
        (self.root / "etc/unraid-version").write_text('version="7.0.0"\n')
        self.env = dict(os.environ, PATH=f"{self.mock}:{self.binary.parent}:/usr/bin:/bin")
        self.write_mock("id", '#!/bin/sh\necho 0\n')
        self.write_mock("uname", '#!/bin/sh\nif [ "$1" = -s ]; then echo Linux; else echo "${TEST_ARCH:-x86_64}"; fi\n')
        self.write_mock("curl", '''#!/bin/bash
[ "${TEST_DOWNLOAD_FAIL:-0}" = 0 ] || exit 22
while [ "$#" -gt 0 ]; do
    if [ "$1" = --output ]; then cp "$TEST_ARCHIVE" "$2"; exit; fi
    shift
done
exit 1
''')
        # macOS portability shims only; Linux CI exercises the native utilities.
        if not shutil.which("sha256sum", path=self.env["PATH"]):
            self.write_mock("sha256sum", f'''#!{sys.executable}
import hashlib, sys
expected, filename = sys.stdin.read().strip().split(None, 1)
sys.exit(0 if hashlib.sha256(open(filename, "rb").read()).hexdigest() == expected else 1)
''')
        if not shutil.which("flock", path=self.env["PATH"]):
            self.write_mock("flock", f'''#!{sys.executable}
import fcntl, sys
fcntl.flock(int(sys.argv[-1]), fcntl.LOCK_EX | fcntl.LOCK_NB)
''')
        self.version = build.metadata()["cli_version"]
        self.fixture(self.version)

    def write_mock(self, name, content):
        path = self.mock / name
        path.write_text(content)
        path.chmod(0o755)

    def fixture(self, version, script=None):
        self.version = version
        archive = self.root / f"fixture-{version}.tar.gz"
        payload = (script or f'#!/bin/sh\necho "infisical version {version}"\n').encode()
        with tarfile.open(archive, "w:gz") as tar:
            info = tarfile.TarInfo("infisical")
            info.mode = 0o755
            info.size = len(payload)
            tar.addfile(info, io.BytesIO(payload))
        self.digest = hashlib.sha256(archive.read_bytes()).hexdigest()
        self.env["TEST_ARCHIVE"] = str(archive)
        return archive

    def scripts(self):
        xml = build.render("test-owner/unraid-infisical-cli")
        doc = ET.fromstring(xml)
        result = []
        for node in doc.findall("FILE"):
            source = node.find("INLINE").text
            for prefix in ("/boot/", "/usr/local/", "/var/lock/", "/etc/unraid-version"):
                source = source.replace(prefix, str(self.root) + prefix)
            source = source.replace(build.metadata()["cli_version"], self.version)
            source = source.replace(build.metadata()["sha256"], self.digest)
            result.append(source)
        return result

    def run_plugin(self, remove=False, success=True):
        source = self.scripts()[1 if remove else 0]
        result = subprocess.run(["/bin/bash"], input=source, text=True, env=self.env, capture_output=True)
        self.assertEqual(result.returncode == 0, success, result.stdout + result.stderr)
        return result.stdout + result.stderr

    def assert_version(self, version):
        self.assertTrue(self.binary.is_symlink())
        self.assertIn(version, subprocess.check_output([str(self.binary), "--version"], text=True))

    def test_fresh_and_repeated_install(self):
        self.run_plugin()
        self.assert_version(self.version)
        self.env["TEST_DOWNLOAD_FAIL"] = "1"
        self.run_plugin()
        self.assert_version(self.version)

    def test_offline_reboot(self):
        self.run_plugin()
        self.binary.unlink()
        shutil.rmtree(self.runtime)
        self.env["TEST_DOWNLOAD_FAIL"] = "1"
        self.run_plugin()
        self.assert_version(self.version)

    def test_upgrade(self):
        self.run_plugin()
        self.fixture("0.43.138")
        self.run_plugin()
        self.assert_version("0.43.138")
        self.assertEqual(len(list(self.cache.glob("*.tar.gz"))), 1)

    def test_failed_download_preserves_previous(self):
        self.run_plugin()
        previous = self.version
        self.fixture("0.43.138")
        self.env["TEST_DOWNLOAD_FAIL"] = "1"
        self.assertIn("Download failed", self.run_plugin(success=False))
        self.assert_version(previous)
        self.assertEqual(list(self.cache.glob(".download.*")), [])

    def test_bad_download_checksum(self):
        self.run_plugin()
        previous = self.version
        self.fixture("0.43.138")
        self.digest = "0" * 64
        self.assertIn("checksum mismatch", self.run_plugin(success=False))
        self.assert_version(previous)

    def test_bad_cached_checksum(self):
        self.run_plugin()
        next(self.cache.glob("*.tar.gz")).write_bytes(b"corrupt")
        self.assertIn("Checksum mismatch", self.run_plugin(success=False))
        self.assert_version(self.version)

    def test_version_check_failure_preserves_previous(self):
        self.run_plugin()
        previous = self.version
        self.fixture("0.43.138", '#!/bin/sh\necho "infisical version 9.9.9"\n')
        self.assertIn("unexpected version", self.run_plugin(success=False))
        self.assert_version(previous)

    def test_conflicting_binary(self):
        self.binary.write_text("user binary")
        self.assertIn("Installation conflict", self.run_plugin(success=False))
        self.assertEqual(self.binary.read_text(), "user binary")
        self.assertFalse(self.cache.exists())

    def test_conflicting_dangling_symlink(self):
        self.binary.symlink_to(self.root / "missing")
        self.assertIn("Installation conflict", self.run_plugin(success=False))
        self.assertTrue(self.binary.is_symlink())

    def test_conflicting_path_binary(self):
        self.write_mock("infisical", "#!/bin/sh\nexit 0\n")
        self.assertIn("already exists", self.run_plugin(success=False))

    def test_unsupported_platform(self):
        self.env["TEST_ARCH"] = "aarch64"
        self.assertIn("x86_64", self.run_plugin(success=False))
        self.env.pop("TEST_ARCH")
        (self.root / "etc/unraid-version").write_text('version="6.12.0"\n')
        self.assertIn("Unraid 7.x", self.run_plugin(success=False))

    def test_uninstall_and_repeat(self):
        self.run_plugin()
        user_file = self.root / ".infisical.json"
        user_file.write_text("user configuration")
        self.run_plugin(remove=True)
        self.assertFalse(self.binary.is_symlink())
        self.assertFalse(self.runtime.exists())
        self.assertFalse(self.cache.exists())
        self.assertEqual(user_file.read_text(), "user configuration")
        self.run_plugin(remove=True)

    def test_uninstall_preserves_replaced_binary_and_unknown_files(self):
        self.run_plugin()
        self.binary.unlink()
        self.binary.write_text("replacement")
        unknown = self.cache / "user-file"
        unknown.write_text("keep")
        self.run_plugin(remove=True)
        self.assertEqual(self.binary.read_text(), "replacement")
        self.assertEqual(unknown.read_text(), "keep")

    def test_generated_descriptor(self):
        doc = ET.fromstring(build.render("test-owner/unraid-infisical-cli"))
        self.assertEqual(doc.attrib["min"], "7.0.0")
        self.assertTrue(doc.attrib["pluginURL"].endswith("/releases/latest/download/unraid-infisical-cli.plg"))
        self.assertEqual(doc.findall("FILE")[1].attrib["Method"], "remove")
        for source in self.scripts():
            subprocess.run(["bash", "-n"], input=source, text=True, check=True)
        for invalid in ("", "owner", "https://github.com/owner/repo", "owner/repo;bad"):
            with self.assertRaises(ValueError):
                build.render(invalid)


if __name__ == "__main__":
    unittest.main()
