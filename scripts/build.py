#!/usr/bin/env python3
"""Render a self-contained Unraid descriptor; no network access during builds."""
import argparse
import datetime
import json
from pathlib import Path
import re
import xml.etree.ElementTree as ET
from xml.sax.saxutils import escape, quoteattr

ROOT = Path(__file__).resolve().parents[1]
NAME = "unraid-infisical-cli"


def metadata():
    data = json.loads((ROOT / "release.json").read_text())
    version = data["plugin_version"]
    if not re.fullmatch(r"\d{4}\.\d{2}\.\d{2}(?:\.\d{2})?", version):
        raise ValueError("plugin_version must be YYYY.MM.DD or YYYY.MM.DD.NN")
    datetime.datetime.strptime(version[:10], "%Y.%m.%d")
    if not re.fullmatch(r"\d+\.\d+\.\d+", data["cli_version"]):
        raise ValueError("cli_version must be a stable numeric release")
    if not re.fullmatch(r"[a-f0-9]{64}", data["sha256"]):
        raise ValueError("sha256 must contain 64 lowercase hex characters")
    return data


def render(repository):
    if not re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9-]*/[A-Za-z0-9_][A-Za-z0-9_.-]*", repository):
        raise ValueError("repository must be an explicit GitHub owner/repository")
    data = metadata()
    version = data["cli_version"]
    url = f"https://github.com/Infisical/cli/releases/download/v{version}/cli_{version}_linux_amd64.tar.gz"
    common = (ROOT / "scripts/common.sh").read_text()
    install = common + f"\nCLI_VERSION='{version}'\nSHA256='{data['sha256']}'\nURL='{url}'\n"
    install += (ROOT / "scripts/install.sh").read_text()
    remove = common + (ROOT / "scripts/remove.sh").read_text()
    attrs = {
        "name": NAME, "author": repository.split("/")[0],
        "version": data["plugin_version"], "min": "7.0.0",
        "pluginURL": f"https://github.com/{repository}/releases/latest/download/{NAME}.plg",
        "support": f"https://github.com/{repository}/issues",
    }
    attributes = " ".join(f"{key}={quoteattr(value)}" for key, value in attrs.items())
    def script(text, method=""):
        if "]]>" in text:
            raise ValueError("Shell script contains CDATA terminator")
        return f'<FILE Run="/bin/bash"{method}><INLINE><![CDATA[\n{text}]]></INLINE></FILE>'
    xml = f'''<?xml version="1.0" standalone="yes"?>
<PLUGIN {attributes}>
<CHANGES>{escape((ROOT / "CHANGELOG.md").read_text())}</CHANGES>
{script(install)}
{script(remove, ' Method="remove"')}
</PLUGIN>
'''
    ET.fromstring(xml)
    return xml


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--repo", required=True, help="GitHub owner/repository hosting this plugin")
    parser.add_argument("--output", type=Path, default=ROOT / "dist" / f"{NAME}.plg")
    args = parser.parse_args()
    try:
        xml = render(args.repo)
    except (ValueError, KeyError) as error:
        parser.error(str(error))
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(xml)
    print(args.output)


if __name__ == "__main__":
    main()
