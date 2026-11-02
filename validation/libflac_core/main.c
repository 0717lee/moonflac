/* Test-only libFLAC buffer-to-owned-buffer reference; never linked into MoonFLAC. */
#include <FLAC/stream_encoder.h>
#include <errno.h>
#include <inttypes.h>
#include <limits.h>
#include <stdint.h>
#include <stdbool.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#ifdef _WIN32
#include <windows.h>
#include <intrin.h>
#else
#include <time.h>
#endif

typedef struct { unsigned char *data; size_t size, capacity, position; } Output;
typedef struct { unsigned channels, bits, rate, block, effort, frames; } Settings;

static FLAC__StreamEncoderWriteStatus write_bytes(const FLAC__StreamEncoder *encoder,
    const FLAC__byte data[], size_t bytes, unsigned samples, unsigned frame, void *client) {
    Output *out = (Output *)client;
    size_t needed, capacity;
    unsigned char *grown;
    (void)encoder; (void)samples; (void)frame;
    if (bytes > SIZE_MAX - out->position) return FLAC__STREAM_ENCODER_WRITE_STATUS_FATAL_ERROR;
    needed = out->position + bytes;
    if (needed > out->capacity) {
        capacity = out->capacity ? out->capacity : 4096;
        while (capacity < needed) {
            if (capacity > SIZE_MAX / 2) { capacity = needed; break; }
            capacity *= 2;
        }
        grown = (unsigned char *)realloc(out->data, capacity);
        if (!grown) return FLAC__STREAM_ENCODER_WRITE_STATUS_FATAL_ERROR;
        out->data = grown; out->capacity = capacity;
    }
    memcpy(out->data + out->position, data, bytes);
    out->position = needed;
    if (needed > out->size) out->size = needed;
    return FLAC__STREAM_ENCODER_WRITE_STATUS_OK;
}

static FLAC__StreamEncoderSeekStatus seek_bytes(const FLAC__StreamEncoder *encoder,
    FLAC__uint64 offset, void *client) {
    Output *out = (Output *)client; (void)encoder;
    if (offset > out->size) return FLAC__STREAM_ENCODER_SEEK_STATUS_ERROR;
    out->position = (size_t)offset;
    return FLAC__STREAM_ENCODER_SEEK_STATUS_OK;
}

static FLAC__StreamEncoderTellStatus tell_bytes(const FLAC__StreamEncoder *encoder,
    FLAC__uint64 *offset, void *client) {
    (void)encoder; *offset = ((Output *)client)->position;
    return FLAC__STREAM_ENCODER_TELL_STATUS_OK;
}

/* The complete encoder lifecycle and all output allocation happen in this call. */
static int encode(const FLAC__int32 *pcm, const Settings *s, Output *out) {
    FLAC__StreamEncoder *encoder = FLAC__stream_encoder_new();
    int ok = 0;
    memset(out, 0, sizeof(*out));
    if (!encoder) return 0;
    /* A build without threading can reject the setter, but its actual limit is 1. */
    FLAC__stream_encoder_set_num_threads(encoder, 1);
    if (FLAC__stream_encoder_get_num_threads(encoder) != 1) goto done;
    if (!FLAC__stream_encoder_set_verify(encoder, false) ||
        !FLAC__stream_encoder_set_streamable_subset(encoder, false) ||
        !FLAC__stream_encoder_set_compression_level(encoder, s->effort) ||
        !FLAC__stream_encoder_set_channels(encoder, s->channels) ||
        !FLAC__stream_encoder_set_bits_per_sample(encoder, s->bits) ||
        !FLAC__stream_encoder_set_sample_rate(encoder, s->rate) ||
        !FLAC__stream_encoder_set_blocksize(encoder, s->block) ||
        !FLAC__stream_encoder_set_total_samples_estimate(encoder, s->frames)) goto done;
    if (FLAC__stream_encoder_init_stream(encoder, write_bytes, seek_bytes,
            tell_bytes, NULL, out) != FLAC__STREAM_ENCODER_INIT_STATUS_OK) goto done;
    if (!FLAC__stream_encoder_process_interleaved(encoder, pcm, s->frames)) goto done;
    ok = FLAC__stream_encoder_finish(encoder);
done:
    FLAC__stream_encoder_delete(encoder);
    return ok;
}

#ifdef _WIN32
static double frequency;
static double now(void) { LARGE_INTEGER tick; QueryPerformanceCounter(&tick); return (double)tick.QuadPart / frequency; }
#else
static double now(void) { struct timespec ts; clock_gettime(CLOCK_MONOTONIC, &ts); return (double)ts.tv_sec + (double)ts.tv_nsec * 1e-9; }
#endif

static int parse(const char *text, unsigned *value) {
    char *end; unsigned long n;
    errno = 0; n = strtoul(text, &end, 10);
    if (errno || !*text || *text == '-' || *end || n > UINT_MAX) return 0;
    *value = (unsigned)n; return 1;
}

int main(int argc, char **argv) {
    Settings s; unsigned batch, width, repetition;
    FILE *input = NULL, *file = NULL;
    unsigned char *raw = NULL;
    FLAC__int32 *pcm = NULL;
    double *seconds = NULL, warm_start, warm_seconds, total = 0.0;
    size_t bytes, scalars, i; long length;
    Output expected = {0}, actual = {0}; int result = 1;
#ifdef _WIN32
    LARGE_INTEGER f; QueryPerformanceFrequency(&f); frequency = (double)f.QuadPart;
    if (argc == 2 && strcmp(argv[1], "--identity") == 0) {
        int registers[4], sse2, avx, avx2 = 0, os_avx = 0;
        __cpuid(registers, 1); sse2 = (registers[3] >> 26) & 1; avx = (registers[2] >> 28) & 1;
        if ((registers[2] >> 27) & 1) os_avx = (_xgetbv(0) & 6) == 6;
        __cpuidex(registers, 7, 0); avx2 = (registers[1] >> 5) & 1;
        printf("{\"sse2\":%d,\"avx\":%d,\"avx2\":%d,\"os_avx_state\":%d,\"qpc_frequency\":%.0f}\n", sse2, avx, avx2, os_avx, frequency);
        return 0;
    }
#endif
    if (argc != 9 || !parse(argv[3], &s.channels) || !parse(argv[4], &s.bits) ||
        !parse(argv[5], &s.rate) || !parse(argv[6], &s.block) ||
        !parse(argv[7], &batch) || !parse(argv[8], &s.effort) ||
        s.channels < 1 || s.channels > 8 || s.bits < 4 || s.bits > 32 ||
        s.rate > 1048575 || s.block < 16 || s.block > 65535 ||
        !batch || batch > 1000000 || s.effort > 8) {
        fprintf(stderr, "usage: libflac_core input.raw output.flac channels bits rate block batch effort\n"); return 2;
    }
    input = fopen(argv[1], "rb");
    if (!input || fseek(input, 0, SEEK_END) || (length = ftell(input)) < 0 || fseek(input, 0, SEEK_SET)) goto done;
    bytes = (size_t)length; width = (s.bits + 7) / 8;
    if (!bytes || bytes % (width * s.channels)) goto done;
    scalars = bytes / width;
    if (scalars / s.channels > UINT_MAX || scalars > SIZE_MAX / sizeof(*pcm)) goto done;
    s.frames = (unsigned)(scalars / s.channels);
    raw = (unsigned char *)malloc(bytes); pcm = (FLAC__int32 *)malloc(scalars * sizeof(*pcm));
    seconds = (double *)malloc((size_t)batch * sizeof(*seconds));
    if (!raw || !pcm || !seconds || fread(raw, 1, bytes, input) != bytes) goto done;
    fclose(input); input = NULL;
    for (i = 0; i < scalars; ++i) {
        unsigned j; uint32_t word = 0; int64_t signed_value;
        for (j = 0; j < width; ++j) word |= (uint32_t)raw[(size_t)i * width + j] << (j * 8);
        signed_value = (int64_t)word;
        if (word & (UINT32_C(1) << (width * 8 - 1))) signed_value -= INT64_C(1) << (width * 8);
        if (signed_value < -(INT64_C(1) << (s.bits - 1)) || signed_value >= (INT64_C(1) << (s.bits - 1))) goto done;
        pcm[i] = (FLAC__int32)signed_value;
    }
    free(raw); raw = NULL;
    warm_start = now();
    if (!encode(pcm, &s, &expected)) goto done;
    warm_seconds = now() - warm_start;
    for (repetition = 0; repetition < batch; ++repetition) {
        double start = now(); int ok = encode(pcm, &s, &actual);
        seconds[repetition] = now() - start;
        if (!ok || expected.size != actual.size || memcmp(expected.data, actual.data, expected.size)) goto done;
        total += seconds[repetition];
        free(actual.data); memset(&actual, 0, sizeof(actual));
    }
    file = fopen(argv[2], "wb");
    if (!file || fwrite(expected.data, 1, expected.size, file) != expected.size) goto done;
    if (fclose(file)) { file = NULL; goto done; } file = NULL;
    printf("LIBFLAC_CORE {\"batch\":%u,\"effort\":%u,\"seconds\":%.17g,\"warm_seconds\":%.17g,\"bytes\":%zu,\"frames\":%u,\"capacity\":%zu,\"per_call_seconds\":[", batch, s.effort, total, warm_seconds, expected.size, s.frames, expected.capacity);
    for (repetition = 0; repetition < batch; ++repetition) printf("%s%.17g", repetition ? "," : "", seconds[repetition]);
    printf("]}\n"); result = 0;
done:
    if (result) fprintf(stderr, "libflac_core: invalid input, encoder, or I/O failure\n");
    if (input) fclose(input); if (file) fclose(file);
    free(raw); free(pcm); free(seconds); free(expected.data); free(actual.data);
    return result;
}
