"""Independent exact Rice parameter-window proof checks; no codec or timing run.

Reproduce: python scripts/prove_rice_parameter_window.py
Unsigned folded residuals 0..2**32-1, 1..65535 samples, maximum k 14 or 30.
"""
import hashlib
import itertools
import json
import random
from pathlib import Path

U32_MAX = (1 << 32) - 1


def window(total, count, maximum):
    """At most three parameters, using only CLZ-equivalent bit lengths/shifts."""
    assert 1 <= count <= 65535 and 0 <= total <= count * U32_MAX
    if total <= count:
        return 0, 0
    d = total.bit_length() - count.bit_length()
    m = d if total >= count << d else d - 1
    lo = max(0, m - 1)
    hi = m if total == count << m else m + 1
    return min(lo, maximum), min(hi, maximum)


def tighter_window(total, count, maximum):
    """Optional exact tightening; never necessary for the three-column bound."""
    if total <= count:
        return 0, 0
    d = total.bit_length() - count.bit_length()
    m = d if total >= count << d else d - 1
    lo = max(0, m - 1)
    # S > 2**(k+1)*N + N*(2**k-1) implies T_k>N.
    if m >= 1 and total > count * (3 * (1 << (m - 1)) - 1):
        lo = m
    # T_m <= floor(S/2**m) <= N implies C(m+1)>=C(m).
    hi = m if total < (count + 1) << m else m + 1
    return min(lo, maximum), min(hi, maximum)


def main():
    arrays = 0
    parameter_costs = 0
    method_checks = 0
    sizes = {1: 0, 2: 0, 3: 0}
    tight_sizes = {1: 0, 2: 0, 3: 0}
    witnesses = {}

    def check(values, category):
        nonlocal arrays, parameter_costs, method_checks
        count = len(values)
        total = sum(values)
        assert all(0 <= v <= U32_MAX for v in values)
        # Compute every candidate independently; no convexity, early stop or
        # window is used to form the reference answer.
        costs = [sum(v >> k for v in values) + count * (k + 1) for k in range(31)]
        arrays += 1
        parameter_costs += 31
        for maximum in (14, 30):
            expected = min(range(maximum + 1), key=costs.__getitem__)
            lo, hi = window(total, count, maximum)
            assert 0 <= lo <= hi <= maximum and hi - lo <= 2
            actual = min(range(lo, hi + 1), key=costs.__getitem__)
            assert actual == expected, (category, total, count, maximum, lo, hi, expected)
            a, b = tighter_window(total, count, maximum)
            assert min(range(a, b + 1), key=costs.__getitem__) == expected
            sizes[hi - lo + 1] += 1
            tight_sizes[b - a + 1] += 1
            # Skipped parameters must be strictly decreasing: equal-cost
            # minima below the window must never be discarded.
            assert all(costs[k + 1] < costs[k] for k in range(lo))
            if hi < maximum:
                assert costs[hi + 1] >= costs[hi]
            method_checks += 1
        if total > count and count <= 8:
            m = (total // count).bit_length() - 1  # Independent floor-log reference.
            offset = expected - m
            if offset in (-1, 0, 1) and str(offset) not in witnesses:
                witnesses[str(offset)] = dict(values=list(values), mean_floor_log2=m,
                                              earliest_parameter=expected, nearby_costs=costs[:min(31, m + 3)])

    # Every ordered small distribution, including all-zero and earliest ties.
    for count in range(1, 6):
        for values in itertools.product(range(8), repeat=count):
            check(values, 'exhaustive-small')
    for a in range(256):
        for b in range(256):
            check((a, b), 'exhaustive-byte-pairs')
    rng = random.Random(20260930)
    for trial in range(2000):
        count = rng.randrange(1, 257)
        mode = trial % 5
        if mode == 0:
            values = [rng.randrange(1 << 32) for _ in range(count)]
        elif mode == 1:
            values = [0] * count
            values[rng.randrange(count)] = rng.randrange(1 << 32)
        elif mode == 2:
            values = [rng.randrange(1 << rng.randrange(1, 33)) for _ in range(count)]
        elif mode == 3:
            value = rng.randrange(1 << 32)
            values = [value] * count
        else:
            values = [rng.choice([0, 1, 2, U32_MAX - 1, U32_MAX]) for _ in range(count)]
        check(values, 'random-u32')
    for count in [1, 2, 3, 7, 31, 255, 1024, 65535]:
        for bit in range(33):
            value = min(U32_MAX, 1 << bit)
            for delta in [-1, 0, 1]:
                v = max(0, min(U32_MAX, value + delta))
                # Full-length maximum-count checks remain bounded in number.
                if count == 65535 and bit not in [0, 15, 30, 31, 32]:
                    continue
                check([v] * count, 'power-threshold-constant')
                check([v] + [0] * (count - 1), 'one-outlier')
    assert all(str(x) in witnesses for x in [-1, 0, 1])
    report = {
        'status': 'pass', 'arrays_checked': arrays, 'full_parameter_costs': parameter_costs,
        'rice_and_rice2_window_checks': method_checks, 'window_width_histogram': sizes,
        'optional_tighter_window_width_histogram': tight_sizes,
        'necessary_offset_witnesses': witnesses,
        'domain': '1<=N<=65535, 0<=u_i<=2^32-1, maximum parameter14 or30; earliest tie wins',
        'exact_window': 'S<=N: [0,0]. Else d=bit_length(S)-bit_length(N); m=d if S>=N<<d else d-1; lo=max(0,m-1); hi=m if S==N<<m else m+1; clamp both endpoints to maximum.',
        'proof': [
            'Let T_k=sum ceil(floor(u_i/2^k)/2). Then C(k+1)-C(k)=N-T_k, nondecreasing in k. The earliest minimizer is the first nonnegative difference, or the last permitted k.',
            'For each u, t=ceil(floor(u/2^k)/2)<=u/2^k. Hence T_k<=floor(S/2^k). If S<=N*2^k then T_k<=N, so the earliest minimizer is at most k.',
            'For each t, u<=(2*t+1)*2^k-1, including t=0. Therefore S<=2^(k+1)*T_k+N*(2^k-1). If S>N*(3*2^k-1), then T_k>N and C(k+1)<C(k) strictly.',
            'For m=floor(log2(S/N)) and k<=m-2, S>=N*2^m>=N*4*2^k>N*(3*2^k-1). Thus every k below m-1 is strictly suboptimal. At k=ceil(log2(S/N)), the upper-bound condition holds. This leaves at most three consecutive parameters.',
            'For S<=N, T_0<=S<=N, so parameter0 is the earliest minimum. Clamping bounds to the allowed maximum retains the earliest restricted minimum by convexity.',
            'The division-free m calculation follows from bit lengths: floor(log2(S/N)) is either d or d-1. For S>N, d>=0; N<<d is below2^49 and every cost below2^48+65535*31, safely within signed64.',
            'Optional tightening uses the exact same strict lower condition at k=m-1, and T_m<=floor(S/2^m)<=N when S<(N+1)*2^m. Strictness preserves ties.',
        ],
        'tree_reuse_note': 'Parent sums of quotients at a fixed k equal the sum of child columns at that same k. However each node has its own mean-based window; a parent-needed k may be absent from both child windows. It is unsafe to merge only matching selected child columns without retaining/recomputing missing data. Safe options: determine every node window from sum/count first and propagate requested k down the tree; or compute requested quotient sums directly/prefix-wise from immutable folded samples. Computing only the global window for every partition is not justified.',
        'escape_note': 'Add the constant parameter field (4 or5) after minimizing Rice cost, and separately compare exact escape cost using the existing strict tie rule. This window does not remove escape candidates.',
        'limitations': 'Algebra covers the stated domain; finite exhaustive/random checks are supporting evidence, not a full formal proof assistant certificate. No performance or implementation claim is made.',
        'script_sha256': hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
    }
    path = Path(__file__).resolve().parents[1] / 'validation/evidence/faster-than-libflac-rice-window-proof.json'
    path.write_text(json.dumps(report, indent=2) + '\n', encoding='utf-8')
    print(json.dumps({k: report[k] for k in ['status', 'arrays_checked', 'full_parameter_costs', 'rice_and_rice2_window_checks', 'window_width_histogram', 'necessary_offset_witnesses']}))


if __name__ == '__main__':
    main()
