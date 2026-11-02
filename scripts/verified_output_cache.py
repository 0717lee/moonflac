"""Reuse independent verification only for identical bytes in one frozen case.

Create a fresh instance per case and benchmark process. The verifier closure must
bind that case's immutable PCM, format and tool configuration. Timings are never
cached. Callers retain their before/after input and executable identity checks.
"""
from copy import deepcopy
import hashlib


def digest_file(path):
    digest = hashlib.sha256()
    with path.open('rb') as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b''):
            digest.update(block)
    return digest.hexdigest()


class VerifiedOutputCache:
    def __init__(self, verifier):
        self._verifier = verifier
        self._expected = {}
        self._verified = {}
        self._calls = 0

    def check(self, codec, output):
        self._calls += 1
        digest = digest_file(output)
        if codec in self._expected and self._expected[codec] != digest:
            raise AssertionError(f'Unstable output: {codec}')
        reused = digest in self._verified
        if not reused:
            checked = self._verifier(output)
            if checked['encoded_sha256'] != digest or digest_file(output) != digest:
                raise AssertionError('Output changed during independent verification')
            if checked['encoded_bytes'] != output.stat().st_size:
                raise AssertionError('Verified output size differs')
            self._verified[digest] = (deepcopy(checked), self._calls, str(codec))
        self._expected[codec] = digest
        checked, first_call, first_codec = self._verified[digest]
        result = deepcopy(checked)
        result['verification_provenance'] = dict(
            method='sha256-identical-output' if reused else 'full-independent-verification',
            call=self._calls, first_verified_call=first_call,
            first_verified_codec=first_codec, encoded_sha256=digest,
            scope='this case in this process; no cached timings',
        )
        return result
