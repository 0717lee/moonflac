# Nested valid-frame regression

`python scripts/review_raw.py` independently constructs four native FLAC fixtures
from RFC9639, then uses the installed libFLAC decoder to confirm every signed
integer sample and STREAMINFO MD5. Expected PCM literals are the libFLAC callback
output. The script checks the embedded constant frames independently too.

Each42-byte outer mono16-bit verbatim frame has a12-byte valid constant frame
inside its32-byte PCM payload. Payload offsets are0,2,8,20 and the inner values
are123,-2345,16384,-32768. The inner bytes remain ordinary outer-frame PCM.

Every two-part split, every three-part split, and bytewise delivery must return
exactly one complete outer frame with the independent PCM. No prefix may produce
audio or a `Skipped` event. This is3960 chunkings per backend. The all-three-part
case includes the original20-byte-prefix trigger as well as empty segments.

The script runs this package on native, JS and wasm-gc using isolated build
directories in ignored `validation/cache/review-raw`. The durable result is
`validation/evidence/review-raw.json`, which records libFLAC's actual version,
fixture hashes, expected PCM, commands and outcomes. No Ogg behavior is changed.

`python scripts/review_raw.py --corpus` separately rebuilds the existing native
validation runner in `_build/review-raw-runner` and compares just the public raw
multicast files10/11 with libFLAC. It requires the expected recovery diagnostic
for the895-byte prefix and records `validation/evidence/review-raw-corpus.json`.
Existing baseline corpus reports remain untouched.
