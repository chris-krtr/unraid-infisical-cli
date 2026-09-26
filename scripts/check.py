#!/usr/bin/env python3
"""Validate XML, generated shell scripts, and isolated lifecycle behavior."""
import argparse
from pathlib import Path
import shutil
import subprocess
import tempfile
import xml.etree.ElementTree as ET
from build import ROOT, render

parser = argparse.ArgumentParser(description=__doc__)
parser.add_argument("--require-shellcheck", action="store_true")
args = parser.parse_args()
shellcheck = shutil.which("shellcheck")
if args.require_shellcheck and not shellcheck:
    parser.error("shellcheck is required")
with tempfile.TemporaryDirectory() as tmp:
    doc = ET.fromstring(render("validation/unraid-infisical-cli"))
    for index, node in enumerate(doc.findall("FILE")):
        path = Path(tmp) / f"lifecycle-{index}.sh"
        path.write_text(node.find("INLINE").text.lstrip())
        subprocess.run(["bash", "-n", str(path)], check=True)
        if shellcheck:
            subprocess.run([shellcheck, str(path)], check=True)
if not shellcheck:
    print("ShellCheck unavailable; use --require-shellcheck in CI.", flush=True)
subprocess.run([shutil.which("python3"), "-m", "unittest", "discover", "-s", "tests", "-v"], cwd=ROOT, check=True)
