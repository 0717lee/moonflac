#!/usr/bin/env python3
"""Require explicit bounded CLI rejection for every public faulty case."""
import argparse
import json
from pathlib import Path
import subprocess
import time

root=Path(__file__).resolve().parents[1]
p=argparse.ArgumentParser()
p.add_argument("--cli",type=Path,required=True)
args=p.parse_args()
results=[]
for path in sorted((root/"validation/cache/flac-test-files/faulty").glob("*.flac")):
    entry={"path":str(path.relative_to(root))}
    start=time.perf_counter()
    try:
        proc=subprocess.run([str(args.cli.resolve()),"verify",str(path),"--json"],capture_output=True,timeout=30)
        diagnostic=proc.stderr.decode(errors="replace")+proc.stdout.decode(errors="replace")
        entry.update(exit=proc.returncode,seconds=time.perf_counter()-start,diagnostic=diagnostic,status="pass" if proc.returncode==3 and diagnostic.strip() else "fail")
    except subprocess.TimeoutExpired: entry.update(status="fail",error="30-second timeout")
    results.append(entry)
    print(entry,flush=True)
folder=root/"validation/results"
folder.mkdir(parents=True,exist_ok=True)
(folder/"faulty.json").write_text(json.dumps(results,indent=2)+"\n")
raise SystemExit(0 if len(results)==11 and all(x["status"]=="pass" for x in results) else 1)
