#!/usr/bin/env python3
"""Fetch the public corpus at one pinned revision; validate each Git blob hash."""
from concurrent.futures import ThreadPoolExecutor
import hashlib
import json
from pathlib import Path
import subprocess
import time
import urllib.parse
import urllib.request

root = Path(__file__).resolve().parents[1] / "validation/cache/flac-test-files"
tree = json.loads(subprocess.check_output(["gh", "api", "repos/ietf-wg-cellar/flac-test-files/git/trees/main?recursive=1"]))
root.mkdir(parents=True,exist_ok=True)
(root / "source.json").write_text(json.dumps(tree,indent=2)+"\n")
def fetch(item):
    path=root/item["path"]
    def valid(data): return hashlib.sha1(b"blob "+str(len(data)).encode()+b"\0"+data).hexdigest()==item["sha"]
    if path.exists() and valid(path.read_bytes()): return
    url="https://raw.githubusercontent.com/ietf-wg-cellar/flac-test-files/"+tree["sha"]+"/"+urllib.parse.quote(item["path"])
    if item["size"] > 32*1024*1024:
        def part(start):
            end=min(start+4*1024*1024,item["size"])-1
            for attempt in range(5):
                try:
                    request=urllib.request.Request(url,headers={"Range":f"bytes={start}-{end}"})
                    with urllib.request.urlopen(request,timeout=60) as response:
                        if response.status!=206 or response.headers.get("Content-Range")!=f"bytes {start}-{end}/{item['size']}":
                            raise ValueError("Server did not honor exact byte range")
                        chunk=response.read()
                    if len(chunk)!=end-start+1: raise ValueError("Truncated range")
                    return chunk
                except Exception:
                    if attempt==4: raise
                    time.sleep(attempt+1)
        with ThreadPoolExecutor(max_workers=6) as pool:
            data=b"".join(pool.map(part,range(0,item["size"],4*1024*1024)))
        if not valid(data): raise ValueError("Git blob SHA-1 mismatch")
        path.parent.mkdir(parents=True,exist_ok=True)
        path.write_bytes(data)
        print(item["path"],flush=True)
        return
    for attempt in range(5):
        try:
            with urllib.request.urlopen(url,timeout=90) as response: data=response.read()
            if not valid(data): raise ValueError("Git blob SHA-1 mismatch")
            path.parent.mkdir(parents=True,exist_ok=True)
            path.write_bytes(data)
            print(item["path"],flush=True)
            return
        except Exception:
            if attempt==4: raise
            time.sleep(attempt+1)
items=sorted((x for x in tree["tree"] if x["type"]=="blob"), key=lambda x:(not x["path"].startswith("uncommon"),x["size"]))
with ThreadPoolExecutor(max_workers=6) as pool: list(pool.map(fetch,items))
print(f"Verified {len(items)} files at {tree['sha']}")
