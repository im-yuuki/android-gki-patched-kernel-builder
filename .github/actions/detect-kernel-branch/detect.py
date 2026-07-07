#!/usr/bin/env python3
"""Fetch the Android CI manifest XML for a given build number and detect the kernel version."""

import json
import os
import re
import sys
import urllib.request
import xml.etree.ElementTree as ET


def fetch_url(url: str) -> str:
    with urllib.request.urlopen(url) as resp:
        return resp.read().decode("utf-8")


def extract_artifact_url(html: str) -> str:
    match = re.search(r"var JSVariables = (\{.*?\});", html, re.S)
    if not match:
        print("Unable to find JSVariables in Android CI artifact page", file=sys.stderr)
        sys.exit(1)

    data = json.loads(match.group(1))
    artifact_url = data.get("artifactUrl")
    if not artifact_url:
        print("Android CI artifact page did not include artifactUrl", file=sys.stderr)
        sys.exit(1)

    return artifact_url


def detect_kernel_version(xml_path: str) -> str:
    root = ET.parse(xml_path).getroot()
    if root.tag != "manifest":
        print(f"Expected manifest root tag, got {root.tag!r}", file=sys.stderr)
        sys.exit(1)

    for project in root.findall("project"):
        if project.get("path") == "common":
            upstream = project.get("upstream")
            if not upstream:
                break
            # Extract kernel version (e.g., "android14-6.1" from "android14-6.1-2025-12")
            version = re.sub(r'-\d{4}-\d{2}$', '', upstream)
            if not version:
                print(f"Regex match failed for upstream={upstream!r}", file=sys.stderr)
                break
            return version

    print('Could not find project with path="common" in manifest XML', file=sys.stderr)
    sys.exit(1)


def main():
    if len(sys.argv) != 2:
        print(f"Usage: {sys.argv[0]} <build_number>", file=sys.stderr)
        sys.exit(1)

    build_number = sys.argv[1]

    # Fetch artifact page and extract download URL
    page_url = f"https://ci.android.com/builds/submitted/{build_number}/kernel_aarch64/latest/manifest_{build_number}.xml"
    html = fetch_url(page_url)
    artifact_url = extract_artifact_url(html)

    # Download manifest XML to a temp file
    xml_content = fetch_url(artifact_url)
    xml_path = f"manifest_{build_number}.xml"
    with open(xml_path, "w", encoding="utf-8") as f:
        f.write(xml_content)

    # Detect kernel version from the manifest
    kernel_version = detect_kernel_version(xml_path)
    manifest_branch = f"common-{kernel_version}"
    susfs_branch = f"gki-{kernel_version}-dev"

    print(f"Detected kernel version: {kernel_version}")
    print(f"Derived manifest branch: {manifest_branch}")
    print(f"Derived susfs branch:    {susfs_branch}")

    # Write outputs for GitHub Actions
    github_output = os.environ.get("GITHUB_OUTPUT")
    if github_output:
        with open(github_output, "a") as f:
            f.write(f"manifest-branch={manifest_branch}\n")
            f.write(f"susfs-branch={susfs_branch}\n")
            f.write(f"kernel-version={kernel_version}\n")


if __name__ == "__main__":
    main()
