# Third-party sources and licenses

MoonFLAC source is licensed under Apache-2.0. The codec algorithms were implemented in MoonBit from the FLAC specification and standard predictive coding methods; no encoder or decoder source from libFLAC, FFmpeg or neighboring projects was copied into the core. LPC analysis uses a locally implemented normalized autocorrelation/Levinson-Durbin routine; external codec executables and libraries are validation tools only.

| Source | Use | License / provenance |
|---|---|---|
| [RFC 9639](https://www.rfc-editor.org/rfc/rfc9639.html) | Format requirements, numerical limits, Appendix D test bytes and expected samples | IETF Trust legal provisions stated in the RFC; extracted code components are subject to its Revised BSD terms |
| [RFC errata 8256](https://www.rfc-editor.org/errata/eid8256), [8810](https://www.rfc-editor.org/errata/eid8810) | Corrected MD5 illustration and wasted-bit shift direction | RFC Editor, verified technical errata |
| [MoonBit core](https://github.com/moonbitlang/core) | Standard collections, bytes, UTF-8 and runtime facilities | Apache-2.0; distributed with the toolchain |
| [moonbitlang/x](https://github.com/moonbitlang/x) | CLI platform utilities | Apache-2.0; declared version in `moon.mod` |
| [Xiph FLAC](https://github.com/xiph/flac) | Independent external reference encoder/decoder used by Python validation | See upstream [COPYING.Xiph](https://github.com/xiph/flac/blob/master/COPYING.Xiph), [COPYING.GPL](https://github.com/xiph/flac/blob/master/COPYING.GPL) and component notices; not linked into the MoonFLAC library |
| [FLAC test files](https://github.com/ietf-wg-cellar/flac-test-files) | Downloaded interoperability/invalid-input corpus | CC0 1.0 Universal, Martijn van Beurden; preserve upstream `README.txt` and `LICENSE.txt` |
| [Playwright](https://github.com/microsoft/playwright) | Optional external browser acceptance runner | Apache-2.0; not required by the playground runtime |

Downloaded reference tools and corpus files live under ignored `validation/cache`. Fetching records the source revision and verifies Git blob hashes; generated manifests record source parameters and hashes. Do not redistribute cache contents without preserving the relevant upstream licenses. The Apache license text in `LICENSE` is the standard license text, not a license grant over these third-party datasets.

The browser uses local code and system fonts; it has no remote image/audio asset dependency. Embedded picture URIs remain untrusted metadata and are not automatically retrieved.

## Performance speech fixture

The optional hardening benchmark uses the complete utterance
`Lab41-SRI-VOiCES-src-sp0307-ch127535-sg0042.wav`, provided by SRI International
and Lab41 through the [VOiCES corpus](https://iqtlabs.github.io/voices/), under
[CC BY 4.0](https://creativecommons.org/licenses/by/4.0/). The cached download
comes from the [PyTorch audio tutorial asset](https://download.pytorch.org/torchaudio/tutorial-assets/Lab41-SRI-VOiCES-src-sp0307-ch127535-sg0042.wav).
SHA256: `c65fcd726d6b08c82c1e5dc7558f863cd8d483e3ed2f4a7bcf271dc1865ada14`.
The WAV integer samples are unpacked without resampling or sample changes;
generated raw PCM and FLAC files are benchmark derivatives. The fixture is
cached locally, not bundled with the library source.

## Speed-first holdout recordings (2026-09-29)

Two complete human readings are reserved for the speed-first encoder's final
holdout validation, separately from the existing VOiCES and FLAC testbench inputs:

- **America The Beautiful**, Katharine Lee Bates, read by **Bvince**:
  [official LibriVox collection](https://librivox.org/short-poetry-collection-228-by-various/),
  [128 kbps MP3](https://archive.org/download/spc228_2206_librivox/spc228_americabeautiful_bv_128kb.mp3).
  Source SHA256: `4bb81a824534351993359bd839278b9a8600a11cd86c51c728f1121e55361d9a`.
- **Anarchy**, John McCrae, read by **mleigh**:
  [official LibriVox collection](https://librivox.org/short-poetry-collection-228-by-various/),
  [128 kbps MP3](https://archive.org/download/spc228_2206_librivox/spc228_anarchy_mlm_128kb.mp3).
  Source SHA256: `015205b61df3de47d0739ce04e753b2f1578825776f8f07c76570756ea4b4666`.

The publisher identifies LibriVox recordings as **Public Domain in the USA**;
this is not a claim about every jurisdiction. The official collection page and
media are retained in the local `validation/cache/speed-first-holdout/` cache.
These are distinct texts and readers within one collection, not evidence of
broad recording diversity. FFmpeg converts each entire MP3 continuously to
fixed integer PCM without resampling, channel conversion, or repetition. The
lossless encoder target is that frozen PCM; MP3 source loss is not recoverable,
and conversion to 24-bit PCM does not establish 24-bit source recording quality.
Exact commands, source and PCM hashes, format, sample counts, and preparation
script identity are in `validation/evidence/speed-first-holdout-manifest.json`.
The source media and generated PCM are local validation assets, not bundled
library source. Reproduce with `python scripts/prepare_speed_first_holdout.py`.
