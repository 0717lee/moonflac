# Demo walkthrough

This checkout is the public submission for the 2026 MoonBit Hackathon. See [HACKATHON.md](../HACKATHON.md) for the project note and submission state.

## 5-minute path

```sh
moon test --target native
moon run examples/stream --target native
moon run examples/encode --target native
moon run examples/ogg --target native
```

```sh
moon run cmd/moonflac --target native -- info input.flac
moon run cmd/moonflac --target native -- verify input.flac
moon run cmd/moonflac --target native -- encode input.wav output.flac
moon run cmd/moonflac --target native -- ogg output.flac output.oga
flac -t output.oga
flac -d --force-raw-format --endian=little --sign=signed -o output.raw output.oga
```

Compare `output.raw` with the source PCM. The Ogg path exercises the mapping packet, metadata, page CRC/sequence, frame continuation, granule and EOS.

## Browser

```sh
node playground/build.mjs
node playground/serve.mjs
```

Open `http://127.0.0.1:8080`, choose JavaScript or WebAssembly GC, inspect metadata/waveform, play/pause/seek and export WAV. Switching backends re-decodes the same file.

## Failure cases

`verify` must reject a damaged CRC or truncated stream. `decode` must not report a partial export as a successful intact file.
