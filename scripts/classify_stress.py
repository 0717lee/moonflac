"""Audit every retained decoder acceptance disagreement after stress completes.

Known inaccurate STREAMINFO mutations are verified from bytes and, where needed,
official FLAC frame analysis. Any unclassified difference fails this gate.
"""
import argparse
import hashlib
import json
import re
import subprocess
from pathlib import Path


def info(data):
    assert data[:4] == b'fLaC' and data[4] & 127 == 0
    return dict(min_block=int.from_bytes(data[8:10],'big'),max_block=int.from_bytes(data[10:12],'big'),
                min_frame=int.from_bytes(data[12:15],'big'),max_frame=int.from_bytes(data[15:18],'big'),
                samples=int.from_bytes(data[18:26],'big') & ((1<<36)-1))


def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--journal',type=Path,required=True)
    p.add_argument('--flac',type=Path,required=True)
    p.add_argument('--report',type=Path,required=True)
    p.add_argument('--compare-run',type=Path,help='check that the same-seed earlier run is fully covered by this journal')
    args=p.parse_args()
    report=json.loads(args.journal.read_text())
    assert report['status']=='passed'
    rows=[]
    for entry in report.get('disagreements',[]):
        folder=Path(entry['directory'])
        original=(folder/'original.flac').read_bytes()
        mutated=(folder/'mutated.flac').read_bytes()
        assert hashlib.sha256(mutated).hexdigest()==entry['mutation']['sha256']
        before,after=info(original),info(mutated)
        row=dict(iteration=entry['case']['iteration'],mutation=entry['mutation'],before=before,after=after,
                 moon_diagnostic=entry['moon']['stderr'],reference_diagnostic=entry['reference']['stderr'],
                 directory=str(folder),classification='unclassified')
        if entry['moon']['returncode']!=3 or entry['reference']['returncode']!=0:
            rows.append(row)
            continue
        # Only the known STREAMINFO edit may differ. No classification by an
        # error string alone, and no assumption that libFLAC acceptance is valid.
        offset=entry['mutation']['offset']
        header_only=(entry['mutation']['kind']=='bit' and 8<=offset<26 and
                     len(original)==len(mutated) and original[:offset]==mutated[:offset]
                     and original[offset+1:]==mutated[offset+1:])
        if header_only:
            if after['min_block']<16 or after['max_block']<16 or after['min_block']>after['max_block']:
                row['classification']='forbidden STREAMINFO block range'
            elif after['min_frame'] and after['max_frame'] and after['min_frame']>after['max_frame']:
                row['classification']='inconsistent STREAMINFO frame range'
            elif after['samples'] and after['samples']!=entry['case']['frames']:
                channels,bits=entry['case']['channels'],entry['case']['bits']
                actual=entry['reference']['stdout_pcm_bytes']//(channels*((bits+7)//8))
                assert actual==entry['case']['frames']
                row['classification']='incorrect nonzero STREAMINFO sample count'
                row['independent_actual_samples']=actual
            else:
                analysis=folder/'original.ana'
                subprocess.run([str(args.flac.resolve()),'-a','-f','-s','-o',str(analysis),str(folder/'original.flac')],
                               capture_output=True,check=True,timeout=60)
                frames=[]
                for line in analysis.read_text().splitlines():
                    if line.startswith('frame='):
                        frames.append({k:int(v) for k,v in re.findall(r'(frame|offset|bits|blocksize)=(\d+)',line)})
                assert frames
                row['independent_frame_analysis']=frames
                sizes=[f['bits']//8 for f in frames]
                if (after['min_frame'] and min(sizes)<after['min_frame']) or (after['max_frame'] and max(sizes)>after['max_frame']):
                    row['classification']='actual frame size outside mutated STREAMINFO range'
                elif (len(frames)>1 and before['min_block']==before['max_block']
                      and after['max_block']!=before['max_block']
                      and all(original[f['offset']+1]&1==0 for f in frames)
                      and all(f['blocksize']==before['max_block'] for f in frames[:-1])):
                    row['classification']='incorrect maximum block size for unchanged fixed-block frames'
        rows.append(row)
    count=report['counts']['moon_only_accepted']+report['counts']['reference_only_accepted']
    assert count==len(rows), 'Every disagreement must have a saved reproducer'
    result=dict(status='pass' if all(r['classification']!='unclassified' for r in rows) else 'needs-investigation',
                seed=report['seed'],stress_seconds=report['elapsed_seconds'],cli_sha256=report['cli_sha256'],cases=rows,
                specification='RFC 9639 section 8.2 permits rejecting incorrect STREAMINFO; any unclassified difference still needs investigation')
    if args.compare_run:
        earlier=json.loads(args.compare_run.read_text())
        assert earlier['status']=='passed'
        assert earlier['seed']==report['seed'] and earlier['cli_sha256']==report['cli_sha256']
        assert report['last_iteration']>=earlier['last_iteration'], 'Journal has not covered the earlier run yet'
        prefix=[r for r in rows if r['iteration']<earlier['last_iteration']]
        assert len(prefix)==earlier['counts']['moon_only_accepted']+earlier['counts']['reference_only_accepted']
        result['earlier_run_covered']=dict(iterations=earlier['last_iteration'],disagreements=len(prefix))
    args.report.write_text(json.dumps(result,indent=2)+'\n',encoding='utf-8')
    print(result['status'],len(rows),'retained disagreements')
    assert result['status']=='pass', 'Inspect unclassified cases before acceptance'


if __name__=='__main__':main()
