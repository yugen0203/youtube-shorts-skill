#!/usr/bin/env python3
"""Offline behavioral checks; pass a small local video+audio fixture."""
import argparse
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch
import tempfile
import hashlib
import json
import accept_download as a
import shorts as m

p=argparse.ArgumentParser();p.add_argument('--fixture',required=True);args=p.parse_args()
fixture=Path(args.fixture).resolve();results=[]
meta={'id':'abcdefghijk','webpage_url':'https://www.youtube.com/watch?v=abcdefghijk','channel_id':'UC0kKqd2HWVv4HEZ7lh-gWLA','duration':m.duration(m.probe(fixture)),'title':'Synthetic local test fixture, not YouTube footage'}
with tempfile.TemporaryDirectory(prefix='shorts-acquisition-test-') as temp:
    root=Path(temp);m.dump(root/'metadata.json',meta)
    a.accept(fixture,root/'metadata.json',root/'accepted.mp4','user-local')
    assert hashlib.sha256(fixture.read_bytes()).digest()==hashlib.sha256((root/'accepted.mp4').read_bytes()).digest()
    results.append('Completed video+audio file validates and copies without changing bytes')
    for label,file,metadata,out in [('partial',root/'x.mp4.part',root/'metadata.json',root/'part.mp4'),('overwrite',fixture,root/'metadata.json',root/'accepted.mp4')]:
        try:a.accept(file,metadata,out,'user-local')
        except ValueError:results.append(label+' rejected')
        else:raise AssertionError(label)
    m.dump(root/'wrong.json',{**meta,'duration':meta['duration']+20})
    try:a.accept(fixture,root/'wrong.json',root/'wrong.mp4','user-local')
    except ValueError:results.append('Duration mismatch rejected before copy')
    else:raise AssertionError('duration')
    def fake_run(cmd,**kw):
        if '--dump-single-json' in cmd:return json.dumps(meta)
        raise RuntimeError('HTTP 403 synthetic test error')
    with patch.object(m,'run',side_effect=fake_run):
        try:m.fetch(SimpleNamespace(url=meta['webpage_url'],out=str(root/'fetch'),max_minutes=120,lang='ja'))
        except RuntimeError:pass
    state=json.loads((root/'fetch/acquisition-state.json').read_text())
    assert state['status']=='browser_fallback_needed' and state['source_url']==meta['webpage_url']
    results.append('HTTP failure produces a browser fallback request rather than success')
print(json.dumps({'passed':len(results),'checks':results,'limits':'Offline fixture tests; not evidence of successful browser MP4 saving'},ensure_ascii=False,indent=2))
