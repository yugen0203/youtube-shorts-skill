#!/usr/bin/env python3
"""Validate a completed local browser download and copy it into the job directory.
This script does not access websites, signed media URLs, cookies or browser state.
"""
import argparse
import hashlib
import json
from pathlib import Path
import shutil
import shorts as m


def accept(file, metadata, out, provider):
    src, dst = Path(file).resolve(), Path(out).resolve()
    meta = json.loads(Path(metadata).read_text(encoding='utf-8'))
    if meta.get('channel_id') != 'UC0kKqd2HWVv4HEZ7lh-gWLA':
        raise ValueError('Metadata is not for @apigatewayph')
    url = m.youtube_url(meta['webpage_url'])
    if url.split('v=')[-1] != meta.get('id'):
        raise ValueError('Metadata video ID and URL disagree')
    if src.suffix.lower() not in {'.mp4','.mov','.mkv','.webm'} or not src.is_file():
        raise ValueError('Provide a completed local video, not ZIP, .part or .crdownload')
    if dst.suffix.lower() != src.suffix.lower():
        raise ValueError('Keep the source extension; renaming a container does not convert it')
    report_path=dst.with_suffix('.acquisition.json')
    if dst.exists() or report_path.exists():
        raise ValueError('Destination exists; reuse it after verification or choose a new name')
    info=m.probe(src)
    streams=info['streams']; video=next((s for s in streams if s['codec_type']=='video'),None)
    if not video or not any(s['codec_type']=='audio' for s in streams):
        raise ValueError('Expected this channel source to contain both video and audio')
    expected=float(meta['duration'])
    if abs(m.duration(info)-expected)>2:
        raise ValueError('Duration differs from video metadata; check the source identity/completeness')
    # Decode the entire input before making it available as a completed source.
    m.run([m.FFMPEG,'-v','error','-xerror','-i',src,'-map','0:v:0','-map','0:a:0','-f','null','-'])
    digest=hashlib.sha256()
    with src.open('rb') as f:
        for chunk in iter(lambda:f.read(1024*1024),b''):digest.update(chunk)
    dst.parent.mkdir(parents=True,exist_ok=True)
    with src.open('rb') as source, dst.open('xb') as target:
        shutil.copyfileobj(source,target)
    m.dump(report_path,{'source_url':url,'video_id':meta['id'],'provider':provider,'file':dst.name,'sha256':digest.hexdigest(),'duration':m.duration(info),'width':video['width'],'height':video['height'],'technical_validation':'passed','identity_review':'pending: compare actual frames/title against requested video; matching duration alone is not proof'})
    print(dst)

if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--file',required=True);p.add_argument('--metadata',required=True);p.add_argument('--out',required=True)
    p.add_argument('--provider',choices=['turboscribe-browser','user-local'],default='turboscribe-browser')
    a=p.parse_args()
    try:accept(a.file,a.metadata,a.out,a.provider)
    except (ValueError,RuntimeError,OSError,KeyError) as e:p.exit(1,f'ERROR: {e}\n')
