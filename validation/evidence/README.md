# Validation evidence

The current Ogg FLAC output receipt is [2026-11-02-ogg-mux](2026-11-02-ogg-mux/README.md). It records the commands, test counts, libFLAC checks and PCM hashes for the November increment.

Historical decoder, encoder and long-stream evidence is summarized in [docs/ACCEPTANCE.md](../../docs/ACCEPTANCE.md). Large raw artifacts are kept local and are not part of the public checkout; the public repository only includes the current receipt and the acceptance summary.

The external oracle is Xiph libFLAC 1.5.0. MoonFLAC does not use its own decoder as reference PCM.
