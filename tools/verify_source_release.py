#!/usr/bin/env python3
"""Verify source-only packaging and its SHA-256 inventory. MIT; stdlib only."""
from __future__ import annotations

import argparse
import hashlib
import ipaddress
import json
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
MANIFEST = "SOURCE-MANIFEST.json"
EXCLUDED = {".git", ".audit", ".validation", ".venv", "bin", "obj", "__pycache__", ".pytest_cache", ".vs", "node_modules", "artifacts"}
SUFFIXES = {".md", ".cs", ".csproj", ".ps1", ".py", ".json", ".yml", ".yaml",
            ".config", ".html", ".js", ".css", ".cfg", ".gsc", ".csv"}
SPECIAL = {"LICENSE", ".gitignore", ".gitattributes"}
SPECIAL_PATHS = {"tools/lua-syntax-checker/requirements.txt"}
SECRET = re.compile(
    r"(?:AKIA[0-9A-Z]{16}|gh[pousr]_[A-Za-z0-9_]{30,}|github_pat_[A-Za-z0-9_]{40,}"
    r"|sk-proj-[A-Za-z0-9_-]{40,}|tskey-[A-Za-z0-9_-]{16,}"
    r"|-----BEGIN (?:RSA |EC |OPENSSH |DSA )?PRIVATE KEY-----)"
)
PERSONAL_PATH = re.compile(r"[A-Za-z]:[\\/]Users[\\/][^\s]+", re.IGNORECASE)
PRIVATE_NETS = [ipaddress.ip_network(value) for value in ("10.0.0.0/8", "172.16.0.0/12", "192.168.0.0/16", "100.64.0.0/10")]


def files(root: Path) -> list[Path]:
    selected = []

    def visit(directory: Path) -> None:
        for path in directory.iterdir():
            if path.name in EXCLUDED:
                continue
            relative = path.relative_to(root)
            if path.is_symlink() or getattr(path, "is_junction", lambda: False)():
                raise ValueError("Linked content: " + relative.as_posix())
            if path.is_dir():
                visit(path)
            elif path.is_file():
                selected.append(path)

    visit(root)
    return sorted(selected)


def inspect(root: Path) -> list[dict]:
    license_text = (root / "LICENSE").read_text(encoding="utf-8-sig")
    if not license_text.startswith("MIT License") or "Permission is hereby granted" not in license_text:
        raise ValueError("Expected the collection's MIT license.")
    records = []
    for path in files(root):
        relative = path.relative_to(root).as_posix()
        if path.name == MANIFEST:
            continue
        if path.name not in SPECIAL and relative not in SPECIAL_PATHS and path.suffix.lower() not in SUFFIXES:
            raise ValueError("Unexpected publication file type: " + relative)
        data = path.read_bytes()
        if len(data) > 2 * 1024 * 1024 or b"\0" in data:
            raise ValueError("Binary or oversized publication file: " + relative)
        source = data.decode("utf-8-sig")
        if SECRET.search(source):
            raise ValueError("Potential credential in: " + relative)
        if PERSONAL_PATH.search(source):
            raise ValueError("Personal Windows path in: " + relative)
        # The scanner's own generic private-network ranges are intentional rules.
        if path.resolve() != Path(__file__).resolve():
            for address in re.findall(r"(?<![\d.])(?:\d{1,3}\.){3}\d{1,3}(?![\d.])", source):
                try:
                    parsed = ipaddress.ip_address(address)
                except ValueError:
                    continue
                if any(parsed in network for network in PRIVATE_NETS):
                    raise ValueError("Private network endpoint in: " + relative)
        if path.suffix.lower() == ".json":
            json.loads(source)
        if path.suffix.lower() == ".md":
            for target in re.findall(r"\]\(([^\s)]+)\)", source):
                if ":" not in target and not target.startswith("#"):
                    target = target.split("#", 1)[0]
                    linked = path.parent / target
                    if target and linked.resolve() != (root / MANIFEST).resolve() and not linked.exists():
                        raise ValueError("Broken local documentation link in: " + relative)
        records.append({"path": relative, "bytes": len(data), "sha256": hashlib.sha256(data).hexdigest()})
    return records


def verify(root: Path, write_manifest: bool = False) -> dict:
    root = root.resolve(strict=True)
    records = inspect(root)
    target = root / MANIFEST
    if write_manifest:
        target.write_text(json.dumps({"schema_version": 1, "license": "MIT", "files": records}, indent=2) + "\n", encoding="utf-8")
    else:
        manifest = json.loads(target.read_text(encoding="utf-8-sig"))
        if manifest.get("schema_version") != 1 or manifest.get("license") != "MIT" or manifest.get("files") != records:
            raise ValueError("Source inventory differs; review changes before regenerating the manifest.")
    return {"status": "PASS", "source_files": len(records), "bytes": sum(row["bytes"] for row in records),
            "binary_payloads": 0, "gameplay_validation": False}


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", type=Path, default=ROOT)
    parser.add_argument("--write-manifest", action="store_true", help="Record the reviewed source inventory")
    args = parser.parse_args()
    try:
        print(json.dumps(verify(args.root, args.write_manifest)))
    except (OSError, ValueError, UnicodeError, KeyError) as exc:
        parser.exit(1, "Release verification failed: " + str(exc) + "\n")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
