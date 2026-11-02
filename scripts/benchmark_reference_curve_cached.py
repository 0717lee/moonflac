"""Run the existing reference curve with explicit identical-output verification.

All timing, warmup, calibration, ordering, quality and identity gates come from
benchmark_faster_than_libflac. Each distinct encoded output is independently
verified; later identical outputs inherit that result within the same case and
process. No timing observation is reused. Historical runners remain unchanged.
"""
import json
from pathlib import Path
import sys

import benchmark_faster_than_libflac as benchmark
from verified_output_cache import VerifiedOutputCache


def main():
    if len(sys.argv) < 2 or sys.argv[1] != 'curve':
        raise SystemExit('This wrapper supports only the curve action')
    sources = [Path(__file__), Path(benchmark.__file__),
               Path(__file__).with_name('verified_output_cache.py')]
    bindings = [benchmark.describe(path) for path in sources]
    original_validate = benchmark.validate_sized
    original_save = benchmark.save
    caches = {}

    def validate(output, case, ref, args):
        # Include the complete case and invocation options, not just its name.
        # No cache or reference instance survives this invocation of main().
        context = json.dumps(dict(case=case, options=vars(args)),
                             sort_keys=True, default=str)
        key = (id(ref), context)
        if key not in caches:
            caches[key] = VerifiedOutputCache(
                lambda path: original_validate(path, case, ref, args))
        return caches[key].check(output.name, output)

    def save(path, report):
        if report.get('action') == 'curve':
            report['verification_protocol'] = dict(
                sources=bindings,
                policy='Full independent PCM/CRC/MD5 verification for every distinct '
                       'output; SHA-256 checked for every produced file; identical '
                       'bytes inherit explicit first-verification provenance within '
                       'one case/process. No timing reuse.',
            )
            report['policy'] = ('fixed manifest; no data generation or substitution; '
                                'verification outside timing as described by '
                                'verification_protocol')
            for source, binding in zip(sources, bindings):
                if benchmark.sha(source) != binding['sha256']:
                    raise AssertionError('Verification source changed during curve')
        original_save(path, report)

    benchmark.validate_sized = validate
    benchmark.save = save
    try:
        benchmark.main()
    finally:
        benchmark.validate_sized = original_validate
        benchmark.save = original_save


if __name__ == '__main__':
    main()
