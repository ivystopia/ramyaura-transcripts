"""Validate the public transcript edition without network or model calls."""
from __future__ import annotations

import argparse
from collections import Counter
import hashlib
import json
from pathlib import Path
import re
import subprocess
from urllib.parse import unquote, urlsplit


ROOT = Path(__file__).resolve().parents[1]


def sha(data):
    return hashlib.sha256(data).hexdigest()


def require(condition, message):
    if not condition:
        raise SystemExit(message)


def records(name):
    return [json.loads(line) for line in (ROOT / "data" / name).read_text().splitlines()]


def private_fields(value, location):
    forbidden = {"request_id", "api_key", "access_token", "refresh_token", "password", "cookies", "cookie", "archive_paths_relative_to_project", "verbatim_user_text", "manifest_path"}
    if isinstance(value, dict):
        require(not forbidden.intersection(value), f"Private metadata field at {location}")
        if "path" in value:
            require(value["path"] == "data/visual-captions.jsonl", f"Unpublished path at {location}")
        for key, item in value.items():
            private_fields(item, location + "." + key)
    elif isinstance(value, list):
        for i, item in enumerate(value):
            private_fields(item, location + f"[{i}]")


def main(update_manifest=False):
    manifest = json.loads((ROOT / "manifest.json").read_text())
    sources = records("sources.jsonl")
    rows = records("corpus.jsonl")
    captions = records("visual-captions.jsonl")
    checks = records("visual-caption-checks.jsonl")
    by_id = {row["video_id"]: row for row in sources}
    by_key = {row["chunk_key"]: row for row in rows}
    require(len(by_id) == len(sources), "Duplicate video IDs")
    require(len(by_key) == len(rows), "Duplicate passage IDs")
    counts = Counter(row["video_id"] for row in rows)
    observed = dict(
        videos=len(sources), passage_records=len(rows),
        nonempty_spoken_passages=sum(bool(row["text"].strip()) for row in rows),
        videos_with_spoken_text=len({row["video_id"] for row in rows if row["text"].strip()}),
        audio_hours=round(sum(row["decoded_duration_seconds"] for row in sources) / 3600, 8),
        terminology_corrections=sum(len(row["terminology_corrections"]) for row in rows),
        corrected_passages=sum(bool(row["terminology_corrections"]) for row in rows),
        known_unresolved_terminology_candidates=sum(len(row["terminology_uncertainties"]) for row in rows),
        visual_caption_groups=len(captions), assistant_visual_checks=len(checks),
        matchup_encounters=sum(len(row["encounters"]) for row in sources),
        opponents=len({e["champion_id"] for row in sources for e in row["encounters"]}),
    )
    require(observed == manifest["counts"], "Manifest counts differ from data")
    for source in sources:
        video_id = source["video_id"]
        require(re.fullmatch(r"[\w-]{11}", video_id), "Invalid video ID")
        require(source["url"] == f"https://www.youtube.com/watch?v={video_id}", "Unexpected source URL")
        require(counts[video_id] == source["passage_count"], f"Missing passages for {video_id}")
        require(source["recording_patch"] is None and source["current_patch_applicability"] == "unvalidated", "Unreviewed patch promotion")
        require((ROOT / source["transcript_path"]).is_file(), "Missing readable transcript")
        for encounter in source["encounters"]:
            require(0 <= encounter["start"] < encounter["end"] <= source["decoded_duration_seconds"] + 0.01, f"Invalid encounter interval: {video_id}")
            for key in encounter["evidence_keys"]:
                require(key in by_key and by_key[key]["video_id"] == video_id, "Missing matchup evidence")
        private_fields(source, "source." + video_id)
    for row in rows:
        key = row["chunk_key"]
        require(row["video_id"] in by_id, "Orphan passage")
        require(row["recording_patch"] is None and row["current_patch_applicability"] == "unvalidated", "Unreviewed patch promotion")
        require(bool(row["review_status"]) and bool(row["quality_flags"]), "Missing review metadata")
        require(0 <= row["start_seconds"] < row["end_seconds"] <= by_id[row["video_id"]]["decoded_duration_seconds"] + 0.02, f"Invalid passage bounds: {key}")
        require(row["source_audio_sha256"] == by_id[row["video_id"]]["audio_sha256"], "Audio identity mismatch")
        require(sha(row["text"].encode()) == row["text_sha256"], "Reading text hash mismatch")
        require(sha(row["text_original"].encode()) == row["text_original_sha256"], "Original text hash mismatch")
        value = row["text_original"]
        previous = 0
        for edit in sorted(row["terminology_corrections"], key=lambda edit: edit["start"]):
            require(previous <= edit["start"] <= edit["end"] <= len(value), "Overlapping or invalid correction offsets")
            require(value[edit["start"]:edit["end"]] == edit["original"], "Correction source mismatch")
            previous = edit["end"]
        for edit in sorted(row["terminology_corrections"], key=lambda edit: edit["start"], reverse=True):
            value = value[:edit["start"]] + edit["replacement"] + value[edit["end"]:]
        require(value == row["text"], "Corrections do not reproduce reading")
        private_fields(row, "passage." + key)
    for row in captions + checks:
        require(row["video_id"] in by_id, "Orphan visual record")
        private_fields(row, "visual")
    files = sorted(path for path in ROOT.rglob("*") if path.is_file() and ".git" not in path.relative_to(ROOT).parts and "__pycache__" not in path.parts)
    actual = {}
    patterns = [r"\bsk-[A-Za-z0-9_-]{20,}", r"\bgh[pousr]_[A-Za-z0-9]{25,}", r"\bgithub_pat_[A-Za-z0-9_]{25,}", r"-----BEGIN [A-Z ]*PRIVATE KEY-----", r"/(?:home|Users)/[A-Za-z0-9_.-]+/", r"\breq_[A-Za-z0-9]{12,}", r"\bproj_[A-Za-z0-9]{12,}", r"\b(?:pi4\.)?home\.arpa\b", r"\b(?:192\.168|10\.\d+)\.\d+\.\d+\b"]
    for path in files:
        relative = path.relative_to(ROOT).as_posix()
        require(not path.is_symlink(), f"Symlink in publication: {relative}")
        require(path.suffix in {".md", ".jsonl", ".json", ".py"} or relative == ".gitignore", f"Unexpected publication file: {relative}")
        data = path.read_bytes()
        require(len(data) < 50 * 1024 * 1024, f"Oversized file: {relative}")
        content = data.decode("utf-8")
        for number, pattern in enumerate(patterns):
            require(not re.search(pattern, content), f"Private data pattern {number} in {relative}; matched value withheld")
        if relative != "manifest.json":
            actual[relative] = {"sha256": sha(data), "bytes": len(data)}
        if path.suffix == ".md":
            for href in re.findall(r"\]\(([^)]+)\)", content):
                if urlsplit(href).scheme:
                    continue
                filename, _, anchor = href.partition("#")
                target = (path.parent / unquote(filename)).resolve() if filename else path
                require(target.is_relative_to(ROOT), "Link escapes repository")
                require(target.is_file(), f"Broken relative link in {relative}")
                if anchor:
                    require(f'id="{anchor}"' in target.read_text(), f"Broken anchor in {relative}")
    if update_manifest:
        manifest["files"] = actual
        (ROOT / "manifest.json").write_text(json.dumps(manifest, ensure_ascii=False, indent=2) + "\n")
    else:
        require(actual == manifest["files"], "Published files differ from manifest")
    if (ROOT / ".git").is_dir():
        roots = subprocess.run(["git", "rev-list", "--max-parents=0", "HEAD"], cwd=ROOT, capture_output=True, text=True, check=True).stdout.splitlines()
        require(len(roots) == 1, "Expected one root commit")
        tree = subprocess.run(["git", "ls-tree", "-r", roots[0]], cwd=ROOT, capture_output=True, text=True, check=True).stdout
        require(not tree.strip(), "The first commit must be empty")
    print(json.dumps({"status": "passed", "files": len(actual) + 1, "counts": observed}, indent=2))


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--update-manifest", action="store_true")
    main(parser.parse_args().update_manifest)
