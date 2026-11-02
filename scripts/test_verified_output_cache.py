"""Protocol tests; these do not establish codec correctness or performance."""
import hashlib
import argparse
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from verified_output_cache import VerifiedOutputCache


class VerificationCacheTests(unittest.TestCase):
    def setUp(self):
        self.work = tempfile.TemporaryDirectory()
        self.addCleanup(self.work.cleanup)
        self.output = Path(self.work.name) / 'output.flac'
        self.output.write_bytes(b'first')
        self.calls = []

    def verify(self, output):
        data = output.read_bytes()
        self.calls.append(data)
        return dict(encoded_sha256=hashlib.sha256(data).hexdigest(),
                    encoded_bytes=len(data), detail={'pcm': True}, quality=False)

    def test_identical_bytes_inherit_explicitly_without_changing_quality(self):
        cache = VerifiedOutputCache(self.verify)
        first = cache.check('0', self.output)
        first['detail']['pcm'] = False
        second = cache.check('8', self.output)
        third = cache.check('0', self.output)
        self.assertEqual(self.calls, [b'first'])
        self.assertTrue(second['detail']['pcm'])
        self.assertFalse(second['quality'])
        self.assertEqual(first['verification_provenance']['method'], 'full-independent-verification')
        self.assertEqual(third['verification_provenance']['method'], 'sha256-identical-output')
        self.assertEqual(third['verification_provenance']['first_verified_call'], 1)

    def test_same_codec_changed_output_rejected(self):
        cache = VerifiedOutputCache(self.verify)
        cache.check('0', self.output)
        self.output.write_bytes(b'other')
        with self.assertRaisesRegex(AssertionError, 'Unstable'):
            cache.check('0', self.output)
        self.assertEqual(len(self.calls), 1)

    def test_new_bytes_and_new_context_require_independent_verification(self):
        cache = VerifiedOutputCache(self.verify)
        cache.check('0', self.output)
        self.output.write_bytes(b'other')
        cache.check('8', self.output)
        VerifiedOutputCache(self.verify).check('8', self.output)
        self.assertEqual(self.calls, [b'first', b'other', b'other'])

    def test_failed_verification_is_not_cached(self):
        def reject(output):
            self.calls.append(output.read_bytes())
            raise AssertionError('PCM mismatch')
        cache = VerifiedOutputCache(reject)
        for _ in range(2):
            with self.assertRaisesRegex(AssertionError, 'PCM mismatch'):
                cache.check('0', self.output)
        self.assertEqual(len(self.calls), 2)

    def test_output_mutation_during_verification_rejected(self):
        def mutate(output):
            result = self.verify(output)
            output.write_bytes(b'other')
            return result
        with self.assertRaisesRegex(AssertionError, 'changed during'):
            VerifiedOutputCache(mutate).check('0', self.output)

    def test_inconsistent_verifier_digest_or_size_rejected(self):
        for field, value in [('encoded_sha256', 'bad'), ('encoded_bytes', 999)]:
            def inconsistent(output):
                result = self.verify(output)
                result[field] = value
                return result
            with self.assertRaises(AssertionError):
                VerifiedOutputCache(inconsistent).check('0', self.output)

    def test_curve_wrapper_separates_context_and_records_protocol(self):
        import benchmark_reference_curve_cached as wrapper
        verified = []
        saved = []
        ref = object()

        def verify(output, case, reference, args):
            verified.append((dict(case), args.large_frame_transport))
            return self.verify(output)

        def run():
            args = argparse.Namespace(large_frame_transport=False)
            case = {'name': 'same-name', 'pcm_sha256': 'first'}
            first = wrapper.benchmark.validate_sized(self.output, case, ref, args)
            again = wrapper.benchmark.validate_sized(self.output, case, ref, args)
            self.assertEqual(again['verification_provenance']['first_verified_call'], 1)
            self.assertEqual(again['verification_provenance']['method'], 'sha256-identical-output')
            wrapper.benchmark.validate_sized(self.output, dict(case, pcm_sha256='second'), ref, args)
            wrapper.benchmark.validate_sized(self.output, case, ref,
                                             argparse.Namespace(large_frame_transport=True))
            wrapper.benchmark.save(self.output, {'action': 'curve', 'verification': first})

        with patch.object(wrapper.benchmark, 'validate_sized', verify), \
             patch.object(wrapper.benchmark, 'save', lambda path, report: saved.append(report)), \
             patch.object(wrapper.benchmark, 'main', run), \
             patch.object(wrapper.sys, 'argv', ['wrapper', 'curve']):
            wrapper.main()
            self.assertIs(wrapper.benchmark.validate_sized, verify)
        self.assertEqual(len(verified), 3)
        self.assertEqual(len(saved), 1)
        self.assertEqual(len(saved[0]['verification_protocol']['sources']), 3)

    def test_curve_wrapper_restores_hooks_after_failure(self):
        import benchmark_reference_curve_cached as wrapper
        validate, save = wrapper.benchmark.validate_sized, wrapper.benchmark.save
        with patch.object(wrapper.benchmark, 'main', side_effect=RuntimeError('failure')), \
             patch.object(wrapper.sys, 'argv', ['wrapper', 'curve']):
            with self.assertRaisesRegex(RuntimeError, 'failure'):
                wrapper.main()
        self.assertIs(wrapper.benchmark.validate_sized, validate)
        self.assertIs(wrapper.benchmark.save, save)


if __name__ == '__main__':
    unittest.main()
