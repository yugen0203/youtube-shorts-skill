#!/usr/bin/env python3
"""Join ordered source ranges, remap captions, and produce channel Shorts assets."""
import argparse
import json
import os
from pathlib import Path
import tempfile
from types import SimpleNamespace
import shorts as m


def compose(plan_path, out):
    plan_path = Path(plan_path).resolve()
    p = json.loads(plan_path.read_text(encoding='utf-8'))
    def local_path(value):
        path = Path(value).expanduser()
        return path.resolve() if path.is_absolute() else (plan_path.parent / path).resolve()
    if p.get('channel_url') != 'https://www.youtube.com/@apigatewayph':
        raise ValueError('This workflow is scoped to @apigatewayph')
    src = local_path(p['source'])
    target = Path(out).resolve()
    if any(target.with_suffix(s).exists() for s in ['.mp4','.json','.ass','.srt','.description.txt','.edit-plan.json']):
        raise ValueError('Output exists; choose a new filename')
    if target.suffix.lower() != '.mp4':
        raise ValueError('Output must end in .mp4')
    info = m.probe(src)
    has_audio = any(s['codec_type']=='audio' for s in info['streams'])
    ranges = [(m.seconds(r['start']),m.seconds(r['end'])) for r in p['ranges']]
    if not ranges or any(not 0 <= a < b <= m.duration(info)+.05 for a,b in ranges):
        raise ValueError('Invalid source ranges')
    total = sum(b-a for a,b in ranges)
    if total > 180:
        raise ValueError('Combined duration exceeds 180 seconds')
    if not p.get('headline') or not p.get('description'):
        raise ValueError('headline and description are required')
    segments = []
    if p.get('transcript'):
        t = json.loads(local_path(p['transcript']).read_text(encoding='utf-8'))
        if t.get('timebase') != 'source_seconds':
            raise ValueError('Transcript must use original source_seconds')
        segments = t['segments']
    mapped=[]; edits=[]; offset=0; filters=[]; inputs=[]
    for i,(a,b) in enumerate(ranges):
        filters.append(f'[0:v]trim=start={a}:end={b},setpts=PTS-STARTPTS[v{i}]')
        inputs.append(f'[v{i}]')
        if has_audio:
            filters.append(f'[0:a:0]atrim=start={a}:end={b},asetpts=PTS-STARTPTS[a{i}]')
            inputs.append(f'[a{i}]')
        for s in segments:
            x,y=max(a,float(s['start'])),min(b,float(s['end']))
            if x<y:
                mapped.append({'start':offset+x-a,'end':offset+y-a,'text':s['text']})
        edits.append({'source_start':a,'source_end':b,'output_start':offset,'output_end':offset+b-a})
        offset+=b-a
    filters.append(''.join(inputs)+f'concat=n={len(ranges)}:v=1:a={int(has_audio)}[v]'+('[a]' if has_audio else ''))
    target.parent.mkdir(parents=True,exist_ok=True)
    with tempfile.TemporaryDirectory(prefix='shorts-compose-') as tmp:
        tmp=Path(tmp); joined=tmp/'joined.mp4'; captions=tmp/'captions.json'
        args=[m.FFMPEG,'-v','error','-to',str(max(b for a,b in ranges)),'-i',src,'-filter_complex',';'.join(filters),'-map','[v]']
        if has_audio: args+=['-map','[a]','-c:a','aac','-ar','48000']
        m.run(args+['-c:v','libx264','-crf','16','-preset','fast','-r','30','-pix_fmt','yuv420p',joined])
        m.dump(captions,{'timebase':'source_seconds','segments':mapped})
        m.render(SimpleNamespace(input=str(joined),out=str(target),start='0',end=str(total),focus_x=.5,transcript=str(captions) if mapped else None,layout='fit',draft=False,font=p.get('font','Hiragino Sans'),headline=p.get('headline','') if not p.get('overlays') else '',label=p.get('label','') if not p.get('overlays') else '',overlays=p.get('overlays',[])))
    m.dump(target.with_suffix('.edit-plan.json'),{**p,'timeline':edits,'total_duration':total})
    report=json.loads(target.with_suffix('.json').read_text())
    report.update(source=str(src),ranges=edits,headline=p['headline'],channel_url=p['channel_url'])
    m.dump(target.with_suffix('.json'),report)
    description=p['description'].strip()
    if p.get('source_url'): description+='\n\n元動画：'+p['source_url']
    target.with_suffix('.description.txt').write_text(p.get('post_title',p['headline'])+'\n\n'+description+'\n',encoding='utf-8')

if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--plan',required=True); parser.add_argument('--out')
    parser.add_argument('--output-dir', default=os.environ.get('SHORTS_OUTPUT_DIR'))
    parser.add_argument('--name', default='clip-01.mp4')
    args=parser.parse_args()
    if not args.out:
        if not args.output_dir:
            parser.error('Specify --out, --output-dir or SHORTS_OUTPUT_DIR')
        if Path(args.name).name != args.name or args.name in {'.', '..'}:
            parser.error('--name must be a filename, not a path')
        args.out = str(Path(args.output_dir).expanduser() / args.name)
    try: compose(args.plan,args.out)
    except (ValueError,RuntimeError,OSError,KeyError) as e: parser.exit(1,f'ERROR: {e}\n')
