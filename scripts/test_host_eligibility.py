"""Focused current-host rejection tests; codecs and native probe are mocked."""
import json,tempfile,unittest
from pathlib import Path
from unittest.mock import patch
import host_eligibility as guard

class CurrentHostTests(unittest.TestCase):
    def exercise(self,missing=None,xcr0=0xe7,fail_probe=False):
        with tempfile.TemporaryDirectory() as directory:
            folder=Path(directory); roles={}
            for role in ['cli','core']:
                original=guard.ROOT/'validation/evidence/faster-than-libflac/candidate77-planner-views-avx512'/('clang-'+role+'-identity.json')
                obj=json.loads(original.read_text()); binary=folder/(role+'.exe'); binary.write_bytes(b'never executed')
                obj[role]['sha256']=guard.sha(binary)
                # The stale builder claims support even when the fresh probe rejects it.
                self.assertTrue(obj['native_host_probe']['result']['features']['AVX512F'])
                identity=folder/(role+'.json'); identity.write_text(json.dumps(obj)); roles[role]=(identity,binary,role)
            current={'features':{k:True for k in guard.BITS},'xcr0':xcr0}
            current['features'].update(OS_AVX=True,OS_AVX512=True)
            if missing: current['features'][missing]=False
            dispatched=[]
            with patch.object(guard,'probe_current',side_effect=RuntimeError('probe failed') if fail_probe else None,
                              return_value=(current,{'mock':True},{})), patch.object(guard.platform,'machine',return_value='AMD64'):
                action=lambda receipt:dispatched.append(receipt['status'])
                if missing or xcr0!=0xe7 or fail_probe:
                    with self.assertRaises(RuntimeError): guard.guarded_dispatch(roles,folder/'host',action)
                    self.assertEqual(dispatched,[])
                else:
                    guard.guarded_dispatch(roles,folder/'host',action)
                    self.assertEqual(dispatched,['pass'])
                    receipt=json.loads((folder/'host/receipt.json').read_text())
                    self.assertEqual(set(receipt['roles']),{'cli','core'})
    def test_old_true_current_missing_no_dispatch(self): self.exercise(missing='AVX512F')
    def test_current_xcr0_missing_no_dispatch(self): self.exercise(xcr0=7)
    def test_probe_failure_no_dispatch(self): self.exercise(fail_probe=True)
    def test_current_all_true_dispatch(self): self.exercise()

if __name__=='__main__': unittest.main()
