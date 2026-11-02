# Nonzero-background pulse regression

The two `tail-4096-*.raw` files are exact independent-review reproductions:
25-bit signed little-endian PCM in four-byte samples, eight channels, 48 kHz,
4096 full samples followed by the named short tail.

`scripts/validate_speed_first_pulses.py` reproduces their complete Python RNG
sequence from seed `202609291339`, including earlier calls, and asserts both
original SHA256 values. It requires no temporary review directory. The `review`
subdirectory preserves the original generator, diagnosis, and baseline/failing
revision4 FLAC outputs unchanged; `review/provenance.json` records their hashes.

The same script generates 30 predeclared variants into `validation/cache`:
small strictly nonzero background amplitudes 2/7/31; pulse intervals
7/17/53/113/257; rotating 16/25/32-bit and 1/2/8-channel formats; both fixed and
variable blocking. Expected PCM comes directly from independent Python inputs.

```sh
python scripts/validate_speed_first_pulses.py prepare
python scripts/validate_speed_first_pulses.py run --candidate PATH --report validation/evidence/speed-first-pulses-revision5.json
```

Prepare seals the input manifest before any candidate results, verifies the
accepted `e6817e77...` baseline identity, and independently checks every baseline
stream with libFLAC. Run checks all 32 candidates, original-byte MD5, frame CRC,
and per-file/aggregate size budgets of +3%/+1%. Size failures retain all cases.
Prior evidence is never overwritten. These are quality gates, not benchmarks.
