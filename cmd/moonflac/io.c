#ifndef _WIN32
#define _POSIX_C_SOURCE 200809L
#endif
#include <stdio.h>
#include <stdint.h>
#include <stdlib.h>
#include <string.h>
#ifdef _WIN32
#include <windows.h>
#include <io.h>
#else
#include <sys/stat.h>
#include <unistd.h>
#endif
static FILE *input_file;
static FILE *output_file;
static FILE *open_utf8(const uint8_t *data, int32_t length, int writing) {
  if (memchr(data, 0, (size_t)length)) return NULL;
#ifdef _WIN32
  int size = MultiByteToWideChar(CP_UTF8, MB_ERR_INVALID_CHARS, (const char *)data, length, NULL, 0);
  if (!size) return NULL;
  wchar_t *path = malloc(((size_t)size + 1) * sizeof(wchar_t));
  if (!path) return NULL;
  MultiByteToWideChar(CP_UTF8, MB_ERR_INVALID_CHARS, (const char *)data, length, path, size);
  path[size] = 0;
  FILE *file = _wfopen(path, writing ? L"wb" : L"rb");
#else
  char *path = malloc((size_t)length + 1);
  if (!path) return NULL;
  memcpy(path, data, (size_t)length);
  path[length] = 0;
  FILE *file = fopen(path, writing ? "wb" : "rb");
#endif
  free(path);
  return file;
}
int32_t moonflac_open_input(const uint8_t *data, int32_t length) {
  input_file = open_utf8(data, length, 0);
  return input_file ? 0 : -1;
}
int32_t moonflac_open_output(const uint8_t *data, int32_t length) {
  /* Check file identity before truncation, including hard links and aliases. */
  FILE *existing = open_utf8(data, length, 0);
  if (existing) {
    int same = 0;
#ifdef _WIN32
    BY_HANDLE_FILE_INFORMATION a, b;
    if (GetFileInformationByHandle((HANDLE)_get_osfhandle(_fileno(input_file)), &a) &&
        GetFileInformationByHandle((HANDLE)_get_osfhandle(_fileno(existing)), &b))
      same = a.dwVolumeSerialNumber == b.dwVolumeSerialNumber &&
        a.nFileIndexHigh == b.nFileIndexHigh && a.nFileIndexLow == b.nFileIndexLow;
#else
    struct stat a, b;
    if (!fstat(fileno(input_file), &a) && !fstat(fileno(existing), &b))
      same = a.st_dev == b.st_dev && a.st_ino == b.st_ino;
#endif
    fclose(existing);
    if (same) return -2;
  }
  output_file = open_utf8(data, length, 1);
  return output_file ? 0 : -1;
}
int32_t moonflac_read(uint8_t *data, int32_t length) {
  size_t n = fread(data, 1, (size_t)length, input_file);
  return ferror(input_file) ? -1 : (int32_t)n;
}
int32_t moonflac_write(const uint8_t *data, int32_t length) {
  return fwrite(data, 1, (size_t)length, output_file) == (size_t)length ? 0 : -1;
}
int32_t moonflac_rewind_output(void) { return fseek(output_file, 0, SEEK_SET); }
int32_t moonflac_close(void) {
  int result = 0;
  if (input_file) { if (fclose(input_file)) result = -1; input_file = NULL; }
  if (output_file) { if (fclose(output_file)) result = -1; output_file = NULL; }
  return result;
}
int32_t moonflac_stderr(const uint8_t *data, int32_t length) {
  return fwrite(data, 1, (size_t)length, stderr) == (size_t)length ? 0 : -1;
}
