# Pre-hardening encoder baseline

`encoder_frame.pre-hardening.mbt.txt` is MoonFLAC's own implementation before the
2026-09-29 search optimization, not third-party codec code. Its SHA256 is
`2cc4813f31410a661422057ab2d678a9a354166fda31c262e733a3225d8e6fb1`, matching
`../evidence/hardening-baseline-source.json`. The `.txt` suffix keeps Moon from
compiling it as another implementation.

Only this production MoonBit source file changed in the optimization. A clean
checkout/cache can reconstruct the algorithm baseline with:

```sh
python scripts/profile_encoder.py freeze --historical
```

This creates an isolated source copy and builds its native release binaries.
An existing `_build/hardening/baseline` is preserved; the command refuses to
overwrite it. Current documentation and validation harnesses may differ from the
original snapshot, so a reconstructed whole-tree hash need not equal that earlier
snapshot's hash. The preserved codec implementation itself is checked exactly.

## Accepted hardening baseline for the effort-8 follow-up

`encoder_frame.pre-effort8.mbt.txt` is the already accepted implementation used as the new baseline for `high-effort-optimization-20260929`. Its SHA256 is `509361274de453e812649cf9331a85898d177b76f7e81761be2d34f208ea273b`. It is separate from the older pre-hardening baseline above. This follow-up again changes only `encoder_frame.mbt` in production.

```sh
python scripts/profile_effort8.py freeze --historical --name reconstructed
cd _build/effort8/reconstructed
moon build --target native --release
```

The command preserves existing baseline snapshots and identity reports. Each reconstructed copy records its own `source-identity.json`, so existing historical evidence does not block a fresh cache rebuild. It creates source only; the explicit build compiles the archived algorithm with the current measurement harness. Use its `validation/benchmark8` binary for core measurements and `cmd/moonflac` for CLI. Current whitebox tests exercise the new scratch interface and are not a claim that the historical implementation can run the current whitebox suite unchanged. Original binary identities remain historical evidence; a rebuild records its own identity.
