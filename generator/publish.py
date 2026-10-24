#!/usr/bin/env python3
"""Put finished videos on a temporary branch so Metricool can fetch them, then remove it.

  python3 generator/publish.py upload  --branch upload-2026-10-25 videos/2026-10-25_1.mp4 ...
      -> pushes the files to a fresh branch, waits until each public raw URL answers
         with the right size, prints one JSON line per file: {"file":..., "url":...}
  python3 generator/publish.py cleanup --branch upload-2026-10-25
      -> deletes the temporary branch (run it once Metricool has copied the videos;
         Metricool's post response then shows a static.metricool.com media URL)

Videos never land on main, so the repository stays small.
"""
import argparse
import json
import os
import shutil
import subprocess
import sys
import tempfile
import time

REPO_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def origin_url():
    return subprocess.check_output(["git", "-C", REPO_DIR, "remote", "get-url", "origin"], text=True).strip()


def owner_repo(url):
    path = url.rstrip("/").removesuffix(".git").split("github.com/")[-1]
    return path


def run(cmd, cwd=None):
    subprocess.run(cmd, cwd=cwd, check=True)


def upload(branch, files):
    url = origin_url()
    with tempfile.TemporaryDirectory() as tmp:
        run(["git", "init", "-q", "-b", branch], cwd=tmp)
        for f in files:
            shutil.copy(f, os.path.join(tmp, os.path.basename(f)))
        run(["git", "add", "."], cwd=tmp)
        run(["git", "commit", "-q", "-m", f"Temporary upload {branch}"], cwd=tmp)
        run(["git", "push", "-q", url, f"HEAD:refs/heads/{branch}"], cwd=tmp)
    out = []
    for f in files:
        name = os.path.basename(f)
        raw = f"https://raw.githubusercontent.com/{owner_repo(url)}/{branch}/{name}"
        size = os.path.getsize(f)
        ok = False
        for _ in range(10):
            r = subprocess.run(["curl", "-sSI", raw], capture_output=True, text=True)
            head = r.stdout.lower()
            status = [ln.split()[1] for ln in head.splitlines()
                      if ln.startswith("http/") and len(ln.split()) > 1]
            if status and status[-1] == "200" and f"content-length: {size}" in head:
                ok = True
                break
            time.sleep(3)
        if not ok:
            raise SystemExit(f"raw URL not reachable yet: {raw}")
        out.append({"file": name, "url": raw, "bytes": size})
        print(json.dumps(out[-1]), flush=True)
    return out


def cleanup(branch):
    run(["git", "push", "-q", origin_url(), "--delete", branch])
    print(json.dumps({"deleted_branch": branch}))


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("action", choices=["upload", "cleanup"])
    ap.add_argument("--branch", required=True)
    ap.add_argument("files", nargs="*")
    a = ap.parse_args()
    if not a.branch.startswith("upload-") or "/" in a.branch:
        sys.exit("branch must look like upload-YYYY-MM-DD")
    if a.action == "upload":
        if not a.files:
            sys.exit("no files given")
        upload(a.branch, a.files)
    else:
        cleanup(a.branch)


if __name__ == "__main__":
    main()
