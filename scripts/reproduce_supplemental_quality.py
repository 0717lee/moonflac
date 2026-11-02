"""Replay the six frozen stage18 quality observations; no TEMP inputs required.

Exit 1 means at least one supplemental size comparison exceeds 1.03, or a
correctness check fails. C95 is expected to fail the supplemental size check.
These cases do not redefine the separately declared performance quality gates.
"""
from pathlib import Path
import argparse
import hashlib
import json
import shutil
import subprocess

from validate import LibFLAC, library, packed

ROOT = Path(__file__).resolve().parents[1]
MANIFEST = ROOT / "validation/evidence/supplemental-quality-stage18/manifest.json"


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--cli", type=Path, required=True)
    parser.add_argument("--out", type=Path, required=True,
                        help="Fresh output directory; existing evidence is never overwritten")
    parser.add_argument("--flac", type=Path)
    parser.add_argument("--libflac", type=Path)
    args = parser.parse_args()
    cli = args.cli.resolve()
    assert cli.is_file(), cli
    flac = args.flac or shutil.which("flac") or (
        ROOT / "validation/cache/libflac/flac-1.5.0-win/Win64/flac.exe")
    flac = Path(flac).resolve()
    assert flac.is_file(), flac
    args.out.mkdir(parents=True, exist_ok=False)
    manifest = json.loads(MANIFEST.read_text(encoding="utf-8"))
    library_path = library(args.libflac)
    reference = LibFLAC(library_path)
    report = dict(status="running", manifest_sha256=sha(MANIFEST),
                  script_sha256=sha(Path(__file__)), cli_sha256=sha(cli),
                  flac_sha256=sha(flac),
                  reference_library=dict(identifier=str(library_path),
                                         sha256=sha(Path(library_path)) if Path(library_path).is_file() else None),
                  validation_helper_sha256=sha(ROOT / "scripts/validate.py"),
                  scope=manifest["scope"], cases=[])
    try:
        for case in manifest["cases"]:
            raw = ROOT / case["files"][".raw"]["path"]
            anchor = ROOT / case["files"]["-anchor.flac"]["path"]
            for suffix, path in [(".raw", raw), ("-anchor.flac", anchor)]:
                assert sha(path) == case["files"][suffix]["sha256"], path
            expected = raw.read_bytes()
            output = args.out / f'{case["index"]:03}-candidate.flac'
            command = [str(cli), "encode", str(raw), str(output), "--raw",
                       "--sample-rate", str(case["sample_rate"]),
                       "--bits", str(case["bits"]), "--channels", str(case["channels"]),
                       "--block-size", str(case["block"]), "--effort", str(case["effort"])]
            if case["variable"]:
                command.append("--variable-block")
            result = subprocess.run(command, capture_output=True, timeout=180)
            assert result.returncode == 0, (case["index"], result.stderr)
            for path in [anchor, output]:
                properties, decoded = reference.decode(path)
                assert properties == (case["channels"], case["bits"], case["sample_rate"])
                assert packed(decoded, case["bits"]) == expected, path
                integrity = subprocess.run([str(flac), "-s", "-t", str(path)],
                                           capture_output=True, timeout=60)
                assert integrity.returncode == 0, (path, integrity.stderr)
                assert path.read_bytes()[26:42] == hashlib.md5(expected).digest(), path
            ratio = output.stat().st_size / anchor.stat().st_size
            report["cases"].append(dict(
                index=case["index"], raw_sha256=sha(raw), command=command,
                anchor_sha256=sha(anchor), candidate_sha256=sha(output),
                anchor_bytes=anchor.stat().st_size, candidate_bytes=output.stat().st_size,
                ratio=ratio, pcm_crc_md5="pass",
                above_comparison_limit=ratio > manifest["per_case_comparison_limit"]))
        failures = [case["index"] for case in report["cases"] if case["above_comparison_limit"]]
        report.update(status="correctness_passed; supplemental_quality_failed" if failures
                      else "correctness_and_supplemental_quality_passed",
                      above_comparison_limit=failures,
                      declared_quality_gates_changed=False)
    except Exception as error:
        report.update(status="failed", error=repr(error))
        raise
    finally:
        (args.out / "report.json").write_text(json.dumps(report, indent=2) + "\n",
                                            encoding="utf-8")
    print(json.dumps({key: report[key] for key in ["status", "above_comparison_limit"]}))
    return int(bool(report["above_comparison_limit"]))


if __name__ == "__main__":
    raise SystemExit(main())
