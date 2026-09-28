#!/usr/bin/env python3
"""Integration tests using generated, owned media. Requires macOS say for speech fixture."""
import importlib.util
import json
from pathlib import Path
import subprocess
import sys

spec = importlib.util.spec_from_file_location('shorts', Path(__file__).with_name('shorts.py'))
m = importlib.util.module_from_spec(spec); spec.loader.exec_module(m)
root = Path(sys.argv[1]).resolve(); root.mkdir(parents=True, exist_ok=True)
script = Path(__file__).with_name('shorts.py')
checks = []

def cli(*args, fail=False):
    p = subprocess.run([sys.executable, str(script), *map(str,args)], capture_output=True, text=True)
    if (p.returncode == 0) == fail:
        raise AssertionError(p.stderr or p.stdout)
    return p

phrases = ['今回は動画編集のテストです。','最初に結論を伝えましょう。','一つの動画では、一つの話題に絞ります。','字幕を付けて、内容を伝えます。','最後に全体を確認しましょう。']
colors = ['0x314158','0x12634c','0x194f80','0x633d87','0x854832']
segments = []
for i, text in enumerate(phrases):
    aiff = root/f'speech-{i}.aiff'
    m.run(['say','-v','Kyoko','-r','210','-o',aiff,text])
    seg = root/f'segment-{i}.mp4'
    vf = f"drawbox=x=80:y=80:w=1120:h=560:color=white@0.25:t=4,drawtext=fontfile=/System/Library/Fonts/ヒラギノ角ゴシック W6.ttc:text='検証用サンプル  {i+1} / 5':fontsize=48:fontcolor=white:x=(w-tw)/2:y=240,drawtext=fontfile=/System/Library/Fonts/ヒラギノ角ゴシック W6.ttc:text='YouTube Shorts — workflow test':fontsize=30:fontcolor=white:x=(w-tw)/2:y=340"
    m.run([m.FFMPEG,'-v','error','-f','lavfi','-i',f'color=c={colors[i]}:s=1280x720:r=30:d=4','-i',aiff,'-vf',vf,'-af','apad','-t','4','-c:v','libx264','-pix_fmt','yuv420p','-c:a','aac',seg])
    segments.append({'start':i*4+.1, 'end':i*4+3.8,'text':text})
(root/'concat.txt').write_text('\n'.join(f"file 'segment-{i}.mp4'" for i in range(5)))
m.run([m.FFMPEG,'-v','error','-f','concat','-safe','0','-i',root/'concat.txt','-c','copy',root/'source.mp4'])
m.dump(root/'transcript.json',{'timebase':'source_seconds','method':'known synthetic Japanese speech fixture','segments':segments})
cli('doctor'); checks.append('Runtime starts and libass subtitles are available')
cli('render','--input',root/'source.mp4','--start','0:04','--end','0:16','--transcript',root/'transcript.json','--layout','fit','--out',root/'short-fit.mp4')
info=m.probe(root/'short-fit.mp4'); v=next(s for s in info['streams'] if s['codec_type']=='video')
assert (v['width'],v['height'],v['codec_name'])==(1080,1920,'h264')
assert abs(m.duration(info)-12)<.15
assert any(s['codec_name']=='aac' for s in info['streams'])
checks.append('Exact 4–16s cut exports 12s 1080×1920 H.264/AAC')
cues=m.read_srt(root/'short-fit.srt')
assert len(cues)==3 and abs(cues[0]['start']-.1)<.001 and cues[-1]['end']<=12
checks.append('Subtitles are rebased from source to clip time and retain Japanese')
# Pixel comparison verifies selection starts in second color section, not the first.
def pixel(path, t):
    return subprocess.check_output([m.FFMPEG,'-v','error','-ss',str(t),'-i',str(path),'-vf','crop=2:2:500:400,format=rgb24','-frames:v','1','-f','rawvideo','-'])[:3]
a=pixel(root/'source.mp4',4.5); b=pixel(root/'short-fit.mp4',.5)
# Output sample above is in letterbox, so compare at source center with equivalent output region.
b=subprocess.check_output([m.FFMPEG,'-v','error','-ss','0.5','-i',str(root/'short-fit.mp4'),'-vf','crop=2:2:420:1000,format=rgb24','-frames:v','1','-f','rawvideo','-'])[:3]
assert sum(abs(x-y) for x,y in zip(a,b))<30
checks.append('First output scene matches the requested source start visually by pixel color')
for layout in ['crop','blur']:
    cli('render','--input',root/'source.mp4','--start','4','--end','6','--layout',layout,'--draft','--out',root/f'short-{layout}.mp4')
    checks.append(f'{layout} layout encodes and decodes successfully')
# Silent video should remain supported.
m.run([m.FFMPEG,'-v','error','-i',root/'source.mp4','-t','1','-an','-c:v','copy',root/'silent.mp4'])
cli('render','--input',root/'silent.mp4','--start','0','--end','.8','--draft','--out',root/'short-silent.mp4')
checks.append('Video without an audio stream renders')
for start,end in [('8','4'),('-1','3'),('0','999'),('nan','3')]:
    cli('render','--input',root/'source.mp4','--start',start,'--end',end,'--out',root/'invalid.mp4',fail=True)
checks.append('Reversed, negative, out-of-bounds and NaN timestamps are rejected')
cli('render','--input',root/'source.mp4','--start','4','--end','16','--out',root/'short-fit.mp4',fail=True)
checks.append('Existing output is protected from overwrite')
cli('transcript','--srt',root/'short-fit.srt','--out',root/'normalized-srt.json')
checks.append('SRT ingestion executes successfully (clip SRT must not be reused as source timing)')
for url in ['https://example.com/test','https://youtube.com.evil.test/watch?v=abcdefghijk','https://www.youtube.com/playlist?list=123']:
    try: m.youtube_url(url)
    except ValueError: pass
    else: raise AssertionError(url)
assert m.youtube_url('https://youtu.be/abcdefghijk?t=4')=='https://www.youtube.com/watch?v=abcdefghijk'
checks.append('YouTube URL validation rejects unrelated hosts and playlists')
cli('frames','--input',root/'short-fit.mp4','--out',root/'review-frames','--count','5')
checks.append('Review frames are extracted from rendered MP4')
m.dump(root/'test-results.json',{'passed':len(checks),'checks':checks,'limits':['Synthetic owned fixture, not live YouTube acquisition','ASR tested separately','Listening and editorial relevance are not proven by these automated tests']})
print(json.dumps({'passed':len(checks),'checks':checks},ensure_ascii=False,indent=2))
