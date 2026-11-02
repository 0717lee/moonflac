# RFC 9639 implementation and acceptance matrix

Normative source: [RFC 9639](https://www.rfc-editor.org/rfc/rfc9639.html).
Checked 2026-09-29 against the [official errata registry](https://www.rfc-editor.org/errata/rfc9639).
Verified erratum [8256](https://www.rfc-editor.org/errata/eid8256) corrects the
MD5 diagram's second-sample channel label. Verified erratum
[8810](https://www.rfc-editor.org/errata/eid8810) restores wasted bits by **left**
shift. [9096](https://www.rfc-editor.org/errata/eid9096) is rejected and does not
change Vorbis-comment field lengths.

“Implementation” identifies the owner of a requirement, not a claim of verified
coverage. “Evidence” names executable tests or independent corpus cases. Actual
run results are maintained in `validation/evidence/` and the final acceptance report.
Independent native results: 245 generated cases,64 subset files,11 uncommon
streams and11 faulty rejections. Fourteen committed independent PCM fixtures
also pass on native, JavaScript and wasm-gc. See `validation/README.md` for commands.

| Requirement / normative section | Exact boundary and behavior | Implementation | Evidence |
|---|---|---|---|
| PCM domain (§1, §5) | Signed integer 4–32-bit, 1–8 channels, rates 1–1048575 Hz; no float decoding math | `frame.mbt`, `types.mbt` | Generated depth-04..32-channels-1..8 and rate-1..1048575; 245 native oracle cases passed |
| File signature/layout (§6, §8) | `fLaC`, first and exactly one STREAMINFO; bounded metadata chain ending at last flag | `metadata.mbt`, `stream.mbt` | metadata tests; faulty06/07/11 |
| STREAMINFO (§8.2) | Exactly34 bytes; min/max blocks16..65535, min<=max; zero frame sizes unknown; 36-bit total0 unknown; zero rate only no audio | `metadata.mbt` | subset45/46/47, faulty01/02/05 |
| Metadata header (§8.1) | 24-bit payload length; types0..6 recognized,7..126 reserved retained/skipped,127 forbidden | `metadata.mbt` | metadata boundary tests |
| PADDING (§8.3) | Byte-aligned zeros; retain size | `metadata.mbt` | subset49/55 |
| APPLICATION (§8.4) | 4-byte application ID plus opaque payload | `metadata.mbt` | subset52/55 |
| SEEKTABLE (§8.5) | At most one;18-byte entries; ordered unique sample numbers; all-ones placeholders only at end; offsets from first audio frame | `metadata.mbt`, `seek.mbt` | subset48/55; range/seek tests |
| VORBIS_COMMENT (§8.6) | At most one; little-endian length/count; UTF-8 value/vendor; case-insensitive ASCII names in permitted range, exclude `=` | `metadata.mbt` | subset51/54; faulty10; metadata tests |
| Channel layout (§8.6.2) | Case-insensitive/padded hex; absent vs explicit zero; partial assignments; preserve supplied mask in WAV/RF64; compare effective Ogg-link layouts; playback omits unnamed channels and diagnoses unrepresentable positions | `channel_layout.mbt`, `wav.mbt`, `cmd/moonflac/main.mbt`, `browser/bridge.mbt`, `playground/playback.js` | `channel_layout_wbtest.mbt`; independent `cmd/test_cli.py` fixtures; both backends in `playground/test-layout.mjs`, exact WAV masks/PCM and offline speaker impulses |
| CUESHEET (§8.7) | 396-byte prefix; reserved zeros; leadout255/non-CD or170/CD; tracks/index bounds and CD588 alignment; retain complete tracks | `metadata.mbt` | subset53; metadata tests |
| PICTURE (§8.8) | Big-endian lengths, UTF-8 description, image bytes or URL; informational dimensions; no automatic URL fetch | `metadata.mbt` | subset50/56..59; metadata tests |
| Header flags (§9.1) | 14-bit sync, zero reserved bits; reject reserved block/rate/channel/depth codes | `frame.mbt` | frame tests and malformed fixtures |
| Blocks (§4.1, §8.2, §9.1.1, §9.1.6) | 16..65535 except final may1..15; block code extensions +1; encoded65536 forbidden | `frame.mbt`, `stream.mbt` | generated blocks16/192/4096/65535, subset01..10/24..30, faulty08/09 |
| Sample rates (§9.1.2, §9.1.7) | Standard table, streaminfo fallback,8-bit kHz,16-bit Hz or tens-Hz; reserved1111 rejected | `frame.mbt` | generated extremes, subset19..21/33/35/36, uncommon06 |
| Channel assignment (§9.1.3, §4.2) | Independent1..8, left-side/right-side/mid-side; 33-bit side at32-bit depth; signed arithmetic and parity | `frame.mbt` | all channel/depth cases; subset38..44; fullscale tests |
| Bit-depth header (§9.1.4) | STREAMINFO fallback and8/12/16/20/24/32-bit codes; code011 reserved | `frame.mbt` | generated all depths, subset22/23/37, uncommon05/07 |
| Coded number (§9.1.5) | Canonical extended UTF-8; frame number<=2^31-1, sample<=2^36-1; no overlong/invalid continuation | `frame.mbt`, `stream.mbt` | number boundary tests; raw uncommon10/11 |
| Fixed/variable strategy (§9.1, App.B.1) | Frame vs sample index semantics; sequence consistency; historic implicit variable streams handled explicitly | `stream.mbt` | subset24..27 |
| Frame header CRC (§9.1.8) | CRC8 polynomial0x07 over header before CRC byte | `frame.mbt` | independent fixtures, corruption tests |
| Subframe header (§9.2.1) | Zero mandatory bit; constant/verbatim/fixed0..4/LPC1..32; reserved patterns fail | `frame.mbt` | subset15/17/31/34/44; unit tests |
| Wasted bits (§9.2.2 + erratum8810) | Unary count+1; reduced signed width; restore with left shift; apply side width correctly | `frame.mbt` | subset14; wasted-bit/fullscale tests |
| Constant/verbatim (§9.2.3–4) | Signed samples using channel width, including33-bit side | `frame.mbt` | subset15; independent generated extrema |
| Fixed predictor (§9.2.5) | Orders0..4; signed warmups; reconstructed values checked; wide intermediate math | `frame.mbt` | subset17/61..63; unit tests |
| LPC (§9.2.6, App.A) | Orders1..32, precision1..15 (16 forbidden), shift0..15 (negative forbidden), reversed past-sample coefficient order | `frame.mbt` | subset12/13/18/31/34/44/61..63 |
| Rice/Rice2 (§9.2.7) | Methods00/01, 4-/5-bit params; partition0..15; block divisible by2^order; first partition accounts predictor order | `frame.mbt` | subset11/16/32/34; uncommon09 |
| Escaped residual (§9.2.7.1) | All-ones parameter, 5-bit raw width0..31; width0 means all zero | `frame.mbt` | subset16/32/64 |
| Residual domain (§9.2.7.3) | Absolute residual<2^31; exclude INT32_MIN; reject unary/shift overflow | `frame.mbt` | malformed residual tests,32-bit extremes |
| Frame padding/footer (§9.3) | Zero alignment bits; CRC16 polynomial0x8005 including header CRC and subframes | `frame.mbt` | corruption and independent oracle tests |
| MD5 (§8.2 + erratum8256) | Interleaved signed LE bytes, sign extend to whole bytes; zero digest unavailable; distinguish mismatch and verified | `md5.mbt`, `stream.mbt` | all generated odd bit depths; known MD5 vectors; mutation tests |
| Changing properties (§9, App.C.8) | Frame API preserves per-frame rate/depth/channels; fixed-format WAV cannot represent a midstream change in one data chunk | `frame.mbt`, `stream.mbt`, CLI | uncommon01..04, per-frame oracle required |
| Ogg mapping (§10.1) | Mapping1.0,51-byte first packet alone on79-byte BOS page; metadata packets; one frame/audio packet; lacing, CRC, continuation and header count; muxer emits the same mapping and validates via the demuxer | `ogg.mbt`, `ogg_encoder.mbt` | generated Ogg4/16/24/32 cases; Ogg page tests; mux round-trip and libFLAC PCM comparisons |
| Ogg chaining (§10.1) | Chained logical streams represent property changes; separate stream integrity/metadata state | `ogg.mbt`, `stream.mbt` | chain/serial/continuation tests |
| Raw multicast (§6, App.C, corpus) | Metadata-less frames possible; explicit resynchronization events, supplied metadata needed for referenced properties | `raw_stream.mbt` | uncommon10/11 |
| Incremental input (project contract) | Arbitrary chunks, NeedMoreData vs terminal errors, finish catches truncation, owned frame PCM, bounded compressed buffering | `stream.mbt` | byte splits, random chunks, truncation and long-stream metrics |
| Seeking/ranges (project contract) | Validated frame index/seek hints; exact sample interval; no trust in unchecked offsets | `seek.mbt`, CLI | range PCM compared to reference slice |
| WAV/RF64 (project contract) | Valid/container bits, unsigned8-bit PCM, extensible channel mask,64-bit sizes, RIFF word padding | `wav.mbt`, CLI | WAV tests, ffmpeg interoperability, forced RF64 |
| Host safety (§11) | Resource limits reported explicitly; checked lengths/counts; no infinite unary or truncated retry loops | all parsers | faulty corpus, truncation/fuzz and memory tests |

## Native encoder implementation mapping

| Requirement | Implementation | Independent evidence |
|---|---|---|
| Full PCM domain, frame headers/numbers and CRC (§8.2, §9.1, §9.3) | `encoder_types.mbt`, `encoder_frame.mbt`, `encoder.mbt` | all 29 depths × 8 channels on three backends; rate/block extremes; official libFLAC integrity checks |
| Constant/verbatim/fixed/LPC/wasted bits (§9.2) | `encoder_frame.mbt`, `encoder_lpc.mbt` | natural selection/cost tests plus 137 emitted representation fixtures decoded and analyzed independently |
| Residual constraints, Rice/Rice2/escape and partition search (§9.2.7, Appendix A) | `encoder_residual_plan` and writer helpers in `encoder_frame.mbt`; effort policy in `encoder_search.mbt` | signed extremes, every escape width, parameters through 30, partition order 15; legal alternate candidates for unrepresentable residuals; shortlist backfilling and alternating-zero regression in `encoder_shortlist_wbtest.mbt`; search limits documented in API.md |
| Stereo decisions and 33-bit side values (§9.1.3, Appendix A) | `encode_frame` | natural left-side/right-side/mid-side selection; all four assignments independently decoded; 32-bit extreme pairs |
| Metadata, channel mask and source MD5 (§8) | `encoder_metadata.mbt`, `encoder.mbt`, shared `md5.mbt` | finalized/unpatched stream paths, preserved blocks/masks, source PCM digest, actual supplied seek-point boundary checks |
| Bounded push/pull/finish and output ownership | `encoder.mbt` | scalar splits/backpressure/errors; increasing-duration and maximum-block process-memory observations |
| PCM WAV/RF64/raw input and CLI finalization | `pcm_input.mbt`, `cmd/moonflac/main.mbt` | all 29 valid depths in RIFF/RF64, custom/zero masks, malformed input and 64-bit chunk tests; independent CLI re-decode |

The [encoder ledger](ENCODER-PROPOSAL.md) records all six completed acceptance gates, including all 75 valid public files in full. Its [oracle documentation](../validation/encoder/README.md) records actual source coverage and commands; forced writer representations and natural compression decisions are separate checks.

## Deliberate project boundaries

The core decodes native/Ogg FLAC, implements the separately authorized native
FLAC encoder, and muxes completed native frames into Ogg FLAC. A bounded Ogg
streaming writer and Matroska/MP4 mappings (§10.2–3) need separate
container demuxers and are outside this project's requested input formats;
their extracted FLAC frames can use the frame API. Web Audio is an output sink,
not the decoder. Unknown application payloads and embedded image formats are
preserved rather than interpreted. Decoder resource limits are configurable and
reported as limits, never as invalid FLAC or successful partial decoding.

## Independent oracle procedure

`python scripts/validate.py generate` makes source PCM and calls libFLAC1.5.0's
encoder and decoder. `compare --cli PATH --corpus generated|subset|uncommon`
compares MoonFLAC output to libFLAC callback integer samples. A reference failure
is a reported failure, not a skipped pass. `scripts/fetch-corpus.py` downloads a
pinned Git tree and verifies every blob hash, preserving upstream licenses and
READMEs. The changing-property and raw multicast cases require the frame API
runner; they must not be called verified by the fixed-format CLI comparator.
