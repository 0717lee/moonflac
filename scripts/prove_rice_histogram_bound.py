"""Independent width-histogram partition lower-bound checks, no codec execution.

python scripts/prove_rice_histogram_bound.py
Uses the previously proved exact parameter window, but exhaustive all-k costs
are computed separately for every reference decision.
"""
import hashlib
import itertools
import json
import random
from pathlib import Path

from prove_rice_parameter_window import window


def metadata(values):
    h = [0] * 33
    for value in values:
        assert 0 <= value < 1 << 32
        h[value.bit_length()] += 1
    return h, sum(values)


def quotient_bounds(histogram, total, count, k):
    hist = sum(histogram[w] * (1 << (w - k - 1)) for w in range(k + 1, 33))
    mean = total if k == 0 else max(0, (total >> k) - (count - 1))
    # Since sum remainders <= N*(2**k-1), this is at least as strong
    # as mean, and costs only an additional integer add before shifting.
    tight_mean = max(0, ((total + count - 1) >> k) - (count - 1))
    max_remainders = sum(histogram[w] * ((1 << min(w, k)) - 1) for w in range(33))
    histogram_remainder = max(0, (total - max_remainders + (1 << k) - 1) >> k)
    return hist, mean, tight_mean, histogram_remainder


def partition_bounds(histogram, total, count):
    lo, hi = window(total, count, 30)
    widths = sum(histogram[w] * (w + 1) for w in range(33))
    maximum = max(w for w in range(33) if histogram[w])
    data = []
    tighter_data = []
    for k in range(lo, hi + 1):
        h, mean, tight_mean, remainder = quotient_bounds(histogram, total, count, k)
        data.append(max(h, mean) + count * (k + 1))
        tighter_data.append(max(h, tight_mean, remainder) + count * (k + 1))
    proposed = 4 + max(widths, min(data))
    tighter = 4 + max(widths, min(tighter_data))
    old_width = 4 + widths
    if maximum <= 31:
        escape = 9 + count * maximum
        proposed = min(proposed, escape)
        tighter = min(tighter, escape)
        old_width = min(old_width, escape)
    return proposed, tighter, old_width


def main():
    partitions = 0
    quotient_checks = 0
    improved_width = 0
    improved_mean = 0
    tight = 0
    quotient_witness = None
    partition_witness = None

    def check(values):
        nonlocal partitions, quotient_checks, improved_width, improved_mean, tight
        nonlocal quotient_witness, partition_witness
        h, total = metadata(values)
        count = len(values)
        exact_q = [sum(v >> k for v in values) for k in range(31)]
        costs = [q + count * (k + 1) for k, q in enumerate(exact_q)]
        for k, q in enumerate(exact_q):
            hist, mean, tight_mean, remainder = quotient_bounds(h, total, count, k)
            assert 0 <= hist <= q and 0 <= mean <= tight_mean <= q and 0 <= remainder <= q
            if tight_mean > mean and quotient_witness is None:
                quotient_witness = dict(values=list(values), k=k, mean=mean, tighter_mean=tight_mean, actual=q)
            quotient_checks += 1
        lb, stronger, old = partition_bounds(h, total, count)
        maximum = max(v.bit_length() for v in values)
        exact_methods = []
        for pb, max_k in [(4, 14), (5, 30)]:
            exact_rice = pb + min(costs[:max_k + 1])
            exact = min(exact_rice, pb + 5 + count * maximum) if maximum <= 31 else exact_rice
            assert old <= lb <= stronger <= exact
            exact_methods.append(exact)
        improved_width += lb > old
        improved_mean += stronger > lb
        tight += lb == min(exact_methods)
        if lb > old and partition_witness is None:
            partition_witness = dict(values=list(values), old=old, proposed=lb, exact=min(exact_methods))
        partitions += 1
        return lb

    for count in range(1, 5):
        for values in itertools.product(range(8), repeat=count):
            check(values)
    # Signed widths include negative extrema, folded zero, and width32 where
    # escape is forbidden; generation here is independent of MoonBit widths.
    signed_edges = sorted(set([0, -1, 1] + [v for bit in range(1, 32) for v in [-(1 << bit), -(1 << bit) + 1, (1 << bit) - 1]]))
    folded_edges = [(-v * 2 - 1 if v < 0 else v * 2) for v in signed_edges]
    for left in folded_edges:
        for right in [0, 1, 2, (1 << 30) - 1, (1 << 31) - 1, (1 << 32) - 1]:
            check([left, right])
    rng = random.Random(2026093002)
    for trial in range(1000):
        count = rng.randrange(1, 129)
        values = [rng.randrange(1 << 32) if trial % 3 == 0 else rng.choice(folded_edges) for _ in range(count)]
        check(values)
    for count in [255, 4096, 65535]:
        for value in [0, 1, 2, (1 << 31) - 1, (1 << 32) - 1]:
            check([value] * count)
            check([value] + [0] * (count - 1))
    merge_checks = 0
    order_checks = 0
    for size in [16, 32, 256, 1024]:
        values = [rng.choice(folded_edges) for _ in range(size)]
        for predictor in [0, 1, 4, 15]:
            for order in range(11):
                if size % (1 << order) or size >> order <= predictor:
                    continue
                span = size >> order
                chunks = [values[predictor:span]] + [values[i:i + span] for i in range(span, size, span)]
                assert sum(map(len, chunks)) == size - predictor
                total_lb = 6 + sum(check(chunk) for chunk in chunks)
                # Every method shares one parameter-field width for this order.
                exact_order = []
                for pb, max_k in [(4, 14), (5, 30)]:
                    cost = 6
                    for chunk in chunks:
                        w = max(v.bit_length() for v in chunk)
                        rice = pb + min(sum(v >> k for v in chunk) + len(chunk) * (k + 1) for k in range(max_k + 1))
                        cost += min(rice, pb + 5 + len(chunk) * w) if w <= 31 else rice
                    exact_order.append(cost)
                assert total_lb <= min(exact_order)
                for a, b in zip(chunks[::2], chunks[1::2]):
                    ha, sa = metadata(a)
                    hb, sb = metadata(b)
                    hc, sc = metadata(a + b)
                    assert [x + y for x, y in zip(ha, hb)] == hc and sa + sb == sc
                    assert partition_bounds(hc, sc, len(a) + len(b))[0] <= check(a + b)
                    merge_checks += 1
                order_checks += 1
    report = dict(
        status='pass', partitions=partitions, quotient_bound_checks=quotient_checks,
        histogram_merge_checks=merge_checks, warmup_order_checks=order_checks,
        stronger_than_width_count=improved_width, optional_tightening_count=improved_mean,
        exact_partition_bound_count=tight, mean_tightening_witness=quotient_witness,
        width_improvement_witness=partition_witness,
        formula='Qhist(k)=sum(w>k,h[w]*2^(w-k-1)); Qmean(k)=S if k0 else max(0,(S>>k)-(N-1)); dataLB=min(k in exact max30 window,max(Qhist,Qmean)+N*(k+1)); riceLB=4+max(sum h[w]*(w+1),dataLB); partitionLB=min(riceLB,9+N*maxw) if maxw<=31 else riceLB; orderLB=6+sum partitionLB.',
        proof=[
            'If bit_length(u)=w>k, u>=2^(w-1), giving u>>k>=2^(w-k-1). Summing bins proves Qhist.',
            'Write S=2^k*Q+R with 0<=R<=N*(2^k-1). This proves Qmean; a stronger equally cheap bound is max(0,((S+N-1)>>k)-(N-1)), exact at k0.',
            'Histogram bins additionally imply R<=sum h[w]*(2^min(w,k)-1). Hence max(0,ceil((S-Rmax)/2^k)) is a safe optional stronger bound. Combining independent lower bounds by max is safe.',
            'The exact max30 window contains the earliest unrestricted Rice2 data minimizer. Evaluate the lower-bound cost at that minimizer: the minimum lower-bound value across the window cannot exceed the exact unrestricted minimum. Adding4 is optimistic for Rice2 (actual5), and the unrestricted minimum cannot exceed the restricted max14 Rice minimum. Thus both methods are bounded even when14 is outside the window.',
            'sum(width+1) independently bounds data cost. Max with dataLB remains a lower bound. Escape is legal only if maxwidth<=31 and has cost9+N*maxwidth for Rice,10+N*maxwidth for Rice2. Taking min safely bounds all legal choices.',
            'Histogram/count/sum merge additively for disjoint intervals. First partition excludes predictor warmups. All partitions cover exactly samples[predictor:size]. Summing optimistic per-partition method minima and adding6 bounds any globally fixed method.',
            'A strict-cost winner must have cost<budget. Partial sums are nonnegative, so reject when cumulative lower bound>=budget. When equal cost can win by lower-order/Rice tie priority, use budget=best_cost+1 (integer costs) or reject only when bound>best_cost. Using>=best_cost in that case is unsound.',
            'Coarse-only histogram bounds and weaker width bounds at deeper levels remain sound: both are lower bounds. Every legal depth must still be considered; this does not justify a partition cap.',
        ],
        precision='Cast histogram counts to Int64 BEFORE shifting. With N<=65535 and u<=2^32-1, S<2^48, every histQ<=S<2^48, Rmax<2^46 for k<=30, S+N-1<2^48. Integer cost and histogram-width sums fit signed64. Summed method costs also remain below2^48+small per-sample/header overhead.',
        tie_example='Folded [0,0,6,6] (signed residuals [0,0,3,3]) has exact Rice cost24 including6bits at both order0 and order1. Order0 must replace order1 on equality. This illustrates why a tight lower-bound equality cannot universally be rejected; it does not claim the proposed histogram bound itself is tight for this example.',
        limitations='No performance claim or production implementation validation; finite checks support the algebra. Tightened remainder bounds are optional mathematical alternatives, not an instruction to add them.',
        script_sha256=hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
        window_proof_script_sha256=hashlib.sha256(Path(__file__).with_name('prove_rice_parameter_window.py').read_bytes()).hexdigest(),
    )
    path = Path(__file__).resolve().parents[1] / 'validation/evidence/faster-than-libflac-rice-histogram-proof.json'
    path.write_text(json.dumps(report, indent=2) + '\n', encoding='utf-8')
    print(json.dumps({k: report[k] for k in ['status', 'partitions', 'quotient_bound_checks', 'histogram_merge_checks', 'warmup_order_checks', 'stronger_than_width_count', 'optional_tightening_count']}))


if __name__ == '__main__':
    main()
