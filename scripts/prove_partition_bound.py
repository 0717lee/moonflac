"""Independent integer proof checks for adaptive FLAC partition refinement.

python scripts/prove_partition_bound.py
No MoonFLAC decoder, encoder, parameter-search helper or generated answer used.
"""
import hashlib
import itertools
import json
import random
from pathlib import Path


def width(value):
    if value == 0:
        return 0
    # Definition by representable signed interval, independent of CLZ.
    result = 1
    while not -(1 << (result - 1)) <= value < (1 << (result - 1)):
        result += 1
    return result


def lower(samples):
    widths = [width(x) for x in samples]
    rice = 4 + sum(w + 1 for w in widths)
    escaped = 9 + len(samples) * max(widths)
    return min(rice, escaped) if max(widths) <= 31 else rice


def exact(samples):
    folded = [(-v * 2 - 1 if v < 0 else v * 2) for v in samples]
    best = None
    w = max(map(width, samples))
    for pb, maximum in [(4, 14), (5, 30)]:
        for k in range(maximum + 1):
            cost = pb + sum((v >> k) + k + 1 for v in folded)
            assert lower(samples) <= cost
            best = cost if best is None else min(best, cost)
        if w <= 31:
            escaped = pb + 5 + len(samples) * w
            assert lower(samples) <= escaped
            best = min(best, escaped)
    return best


def main():
    scalar_count = 0
    scalar_values = list(range(-65536, 65536)) + [-(1 << b) + d for b in range(17, 32) for d in [-1, 0, 1]] + [(1 << b) + d for b in range(17, 32) for d in [-1, 0, 1]]
    for value in scalar_values:
        folded = -value * 2 - 1 if value < 0 else value * 2
        w = width(value)
        assert w == folded.bit_length()
        for k in range(31):
            assert (folded >> k) + k + 1 >= w + 1
            scalar_count += 1
    partitions = 0
    equality = 0
    for count in range(1, 6):
        for values in itertools.product([-8, -1, 0, 1, 7], repeat=count):
            best = exact(values)
            equality += lower(values) == best
            partitions += 1
    rng = random.Random(963929092026)
    extremes = [-(1 << 31), -(1 << 30) - 1, -(1 << 30), -1, 0, 1, (1 << 30) - 1, 1 << 30, (1 << 31) - 1]
    for _ in range(1000):
        values = [rng.choice(extremes) for _ in range(rng.randrange(1, 65))]
        exact(values)
        partitions += 1
    warmup_checks = 0
    for size in [16, 32, 64, 128, 256, 512, 1024]:
        values = [rng.randrange(-64, 64) if i % 97 else rng.choice(extremes) for i in range(size)]
        for predictor in [0, 1, 4, 15, 31]:
            if predictor >= size:
                continue
            for order in range(16):
                if size % (1 << order) or size // (1 << order) <= predictor:
                    continue
                step = size // (1 << order)
                chunks = [values[predictor:step]] + [values[i:i + step] for i in range(step, size, step)]
                assert sum(map(len, chunks)) == size - predictor
                assert 6 + sum(map(lower, chunks)) <= 6 + sum(map(exact, chunks))
                warmup_checks += 1
    proof = {
        'status': 'pass', 'scalar_parameter_checks': scalar_count,
        'partition_checks': partitions, 'tight_bound_partitions': equality,
        'partition_order_warmup_checks': warmup_checks,
        'proof': [
            'For signed residual v, folded u=2v if v>=0 else -2v-1 has bit_length w equal to signed width (zero width0).',
            'If k>=w, quotient+k+1>=w+1. Otherwise d=w-k>=1, u>>k>=2^(d-1)>=d, giving quotient+k+1>=w+1.',
            'Summing per-symbol inequalities and optimistic parameter width4 bounds both Rice and Rice2. Escape cost is at least9+n*maxw when maxw<=31; taking min preserves a lower bound across all legal representations.',
            'Partitions cover samples[predictor:size] exactly, and adding global6bits preserves the bound. Integer sums stay below2^48+overhead for65535 legal32bit residuals.',
            'If every higher order has lower_bound>=exact coarse cost, none can win: equality loses because existing policy prefers smaller partition order. If a higher order can win it must satisfy lower_bound<coarse cost; full refinement to highest such order includes every potentially winning lower order.',
        ],
        'limitations': 'Finite exhaustive and deterministic boundary checks support, but do not replace, the algebraic proof. This script does not measure performance or validate the production implementation.',
        'script_sha256': hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
    }
    output = Path(__file__).resolve().parents[1] / 'validation/evidence/partition-bound-proof.json'
    output.write_text(json.dumps(proof, indent=2) + '\n', encoding='utf-8')
    print(json.dumps({k: v for k, v in proof.items() if k not in ['proof', 'limitations']}))


if __name__ == '__main__':
    main()
