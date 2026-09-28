#!/usr/bin/env python3
"""Deterministic media helpers; editorial decisions belong to the calling agent."""
import argparse
import html
import json
import math
import os
from pathlib import Path
import re
import shutil
import subprocess
import sys
import tempfile
from urllib.parse import urlparse, parse_qs

FFMPEG = os.environ.get('SHORTS_FFMPEG', 'ffmpeg')
FFPROBE = os.environ.get('SHORTS_FFPROBE', 'ffprobe')


def run(args, **kwargs):
    p = subprocess.run([str(x) for x in args], capture_output=True, text=True, **kwargs)
    if p.returncode:
        raise RuntimeError(p.stderr[-5000:] or p.stdout[-5000:])
    return p.stdout


def dump(path, value):
    Path(path).write_text(json.dumps(value, ensure_ascii=False, indent=2), encoding='utf-8')


def seconds(value):
    fields = str(value).replace(',', '.').split(':')
    if len(fields) > 3:
        raise ValueError('Time must be seconds, MM:SS or HH:MM:SS')
    nums = [float(x) for x in fields]
    if any(not math.isfinite(x) or x < 0 for x in nums) or any(x >= 60 for x in nums[1:]):
        raise ValueError('Invalid timestamp')
    return sum(x * 60 ** i for i, x in enumerate(reversed(nums)))


def probe(path):
    return json.loads(run([FFPROBE, '-v', 'error', '-show_format', '-show_streams', '-of', 'json', Path(path).resolve()]))


def duration(info):
    return float(info['format']['duration'])


def youtube_url(value):
    u = urlparse(value)
    if u.scheme != 'https' or u.username or u.password or u.port not in (None, 443):
        raise ValueError('Use an HTTPS YouTube video URL')
    host = (u.hostname or '').lower()
    if host == 'youtu.be':
        vid = u.path.strip('/')
    elif host in {'youtube.com', 'www.youtube.com', 'm.youtube.com'}:
        parts = u.path.strip('/').split('/')
        vid = parse_qs(u.query).get('v', [''])[0] if u.path == '/watch' else (parts[1] if len(parts) == 2 and parts[0] in {'shorts', 'live', 'embed'} else '')
    else:
        raise ValueError('Only YouTube video URLs are supported')
    if not re.fullmatch(r'[A-Za-z0-9_-]{11}', vid):
        raise ValueError('Invalid YouTube video ID')
    return 'https://www.youtube.com/watch?v=' + vid


def doctor(_):
    result = {}
    for label, cmd in [('ffmpeg', [FFMPEG, '-version']), ('ffprobe', [FFPROBE, '-version']), ('yt-dlp', ['yt-dlp', '--version'])]:
        try:
            result[label] = run(cmd).splitlines()[0]
        except (RuntimeError, OSError) as e:
            result[label] = {'error': str(e)}
    try:
        result['subtitle_filter'] = bool(re.search(r'\bsubtitles\s', run([FFMPEG, '-hide_banner', '-filters'])))
    except (RuntimeError, OSError):
        result['subtitle_filter'] = False
    print(json.dumps(result, ensure_ascii=False, indent=2))
    if not result['subtitle_filter'] or any(isinstance(v, dict) for v in result.values()):
        raise RuntimeError('Media runtime is incomplete; repair or select working binaries before continuing')


def fetch(a):
    url = youtube_url(a.url)
    out = Path(a.out).resolve()
    out.mkdir(parents=True, exist_ok=True)
    if list(out.iterdir()):
        raise ValueError('Use an empty fetch directory to avoid mixing sources')
    base = ['yt-dlp', '--ignore-config', '--no-playlist', '--no-progress', '--retries', '2', '--socket-timeout', '30']
    meta = json.loads(run(base + ['--skip-download', '--dump-single-json', url]))
    if meta.get('channel_id') != 'UC0kKqd2HWVv4HEZ7lh-gWLA':
        raise ValueError('Source video must belong to @apigatewayph (verified channel ID)')
    if meta.get('is_live') or meta.get('live_status') == 'is_upcoming':
        raise ValueError('Use a completed video, not a live or upcoming stream')
    if not meta.get('duration') or meta['duration'] > a.max_minutes * 60:
        raise ValueError('Duration is unknown or exceeds --max-minutes; inspect before increasing the limit')
    dump(out / 'metadata.json', {k:meta.get(k) for k in ['id', 'title', 'channel', 'channel_id', 'uploader_id', 'duration', 'webpage_url', 'license', 'chapters']})
    try:
        run(base + ['-f', 'bv*[height<=1080]+ba/b[height<=1080]', '--merge-output-format', 'mp4', '--ffmpeg-location', shutil.which(FFMPEG) or FFMPEG, '-o', str(out / 'source.%(ext)s'), url])
    except RuntimeError as e:
        dump(out / 'acquisition-state.json', {
            'status':'browser_fallback_needed', 'source_url':url,
            'fallback_page':'https://turboscribe.ai/ja/downloader/youtube/mp4',
            'instructions':'Read references/browser-download.md and use the available browser tool. The CLI itself does not operate the browser.',
            'error':str(e)[-2000:]})
        raise RuntimeError('Direct download failed. Browser fallback request saved in acquisition-state.json; follow references/browser-download.md') from e
    # Subtitle failure must not discard a successful media download.
    try:
        run(base + ['--skip-download', '--write-subs', '--write-auto-subs', '--sub-langs', a.lang + '.*', '--sub-format', 'srt/vtt/best', '--convert-subs', 'srt', '--ffmpeg-location', shutil.which(FFMPEG) or FFMPEG, '-o', str(out / 'source.%(ext)s'), url])
    except RuntimeError as e:
        (out / 'subtitle-warning.txt').write_text(str(e), encoding='utf-8')
    print(json.dumps({'directory':str(out), 'files':[p.name for p in out.iterdir()]}, ensure_ascii=False))


def read_srt(path):
    value = Path(path).read_text(encoding='utf-8-sig').replace('\r\n', '\n')
    segments = []
    for block in re.split(r'\n\s*\n', value.strip()):
        lines = block.splitlines()
        idx = next((i for i, line in enumerate(lines) if '-->' in line), None)
        if idx is None:
            continue
        left, right = lines[idx].split('-->', 1)
        start, end = seconds(left.strip()), seconds(right.strip().split()[0])
        text = html.unescape(re.sub(r'<[^>]*>', '', ' '.join(lines[idx + 1:]))).strip()
        if end > start and text:
            segments.append({'start':start, 'end':end, 'text':text})
    if not segments:
        raise ValueError('No valid subtitle segments')
    return segments


def transcript(a):
    out = Path(a.out).resolve()
    if out.exists():
        raise ValueError('Transcript output already exists')
    if a.srt:
        segments = read_srt(a.srt)
        method = 'source subtitles; unverified'
    else:
        import whisper
        import torch
        torch.set_num_threads(min(4, os.cpu_count() or 1))
        with tempfile.TemporaryDirectory(prefix='shorts-asr-') as tmp:
            wav = Path(tmp) / 'audio.wav'
            run([FFMPEG, '-v', 'error', '-i', Path(a.input).resolve(), '-vn', '-ar', '16000', '-ac', '1', wav])
            model = whisper.load_model(a.model, device='cpu')
            result = model.transcribe(str(wav), language=a.lang, fp16=False, word_timestamps=True, verbose=False)
            segments = [{k:s[k] for k in ('start', 'end', 'text', 'words') if k in s} for s in result['segments']]
        method = f'local Whisper {a.model}; unverified'
    out.parent.mkdir(parents=True, exist_ok=True)
    dump(out, {'timebase':'source_seconds', 'method':method, 'segments':segments})
    print(out)


def frames(a):
    info = probe(a.input)
    start = seconds(a.start)
    end = seconds(a.end) if a.end else duration(info)
    if not 0 <= start < end <= duration(info) + .05 or not 1 <= a.count <= 60:
        raise ValueError('Invalid frame sampling range/count')
    out = Path(a.out).resolve()
    out.mkdir(parents=True, exist_ok=True)
    if list(out.iterdir()):
        raise ValueError('Use an empty frame directory')
    index = []
    for i in range(a.count):
        t = start + (end-start) * (i+.5)/a.count
        f = out / f'frame-{i+1:02d}.jpg'
        run([FFMPEG, '-v', 'error', '-i', Path(a.input).resolve(), '-ss', str(t), '-frames:v', '1', '-vf', 'scale=640:-2', f])
        index.append({'file':str(f), 'source_seconds':round(t, 3)})
    dump(out / 'index.json', index)
    print(json.dumps(index, ensure_ascii=False))


def stamp(t, ass=False):
    rate = 100 if ass else 1000
    n = round(t * rate)
    sec, frac = divmod(n, rate)
    mins, sec = divmod(sec, 60)
    hours, mins = divmod(mins, 60)
    return f'{hours}:{mins:02}:{sec:02}.{frac:02}' if ass else f'{hours:02}:{mins:02}:{sec:02},{frac:03}'


def render(a):
    src, target = Path(a.input).resolve(), Path(a.out).resolve()
    info = probe(src)
    start, end = seconds(a.start), seconds(a.end)
    if not 0 <= start < end <= duration(info) + .05:
        raise ValueError('Clip range is outside the source or reversed')
    if end-start > 180:
        raise ValueError('This Shorts renderer supports clips up to 180 seconds')
    if not 0 <= a.focus_x <= 1:
        raise ValueError('--focus-x must be between 0 and 1')
    outputs = [target, target.with_suffix('.srt'), target.with_suffix('.ass'), target.with_suffix('.json')]
    if any(p.exists() for p in outputs):
        raise ValueError('Output or sidecars already exist; choose a new output name')
    target.parent.mkdir(parents=True, exist_ok=True)
    cues = []
    if a.transcript:
        data = json.loads(Path(a.transcript).read_text(encoding='utf-8'))
        if data.get('timebase') != 'source_seconds':
            raise ValueError('Transcript must use source_seconds, not clip-relative time')
        for s in data['segments']:
            x, y = max(start, float(s['start'])), min(end, float(s['end']))
            if x < y:
                cues.append((x-start, y-start, str(s['text']).strip()))
        cues.sort()
        if not cues:
            raise ValueError('No captions intersect the selected clip')
    w, h = (720, 1280) if a.draft else (1080, 1920)
    if a.layout == 'fit':
        vf = f'scale={w}:{h}:force_original_aspect_ratio=decrease:force_divisible_by=2,pad={w}:{h}:(ow-iw)/2:(oh-ih)/2:color=black,setsar=1'
        graph = f'[0:v]{vf}[base]'
    elif a.layout == 'crop':
        vf = f'scale={w}:{h}:force_original_aspect_ratio=increase:force_divisible_by=2,crop={w}:{h}:(iw-ow)*{a.focus_x}:(ih-oh)/2,setsar=1'
        graph = f'[0:v]{vf}[base]'
    else:
        graph = f'[0:v]split[b][f];[b]scale={w}:{h}:force_original_aspect_ratio=increase,crop={w}:{h},boxblur=20:2[bg];[f]scale={w}:{h}:force_original_aspect_ratio=decrease:force_divisible_by=2[fg];[bg][fg]overlay=(W-w)/2:(H-h)/2,setsar=1[base]'
    with tempfile.TemporaryDirectory(prefix='shorts-render-') as tmp:
        temp = Path(tmp)
        if cues or getattr(a, 'headline', '') or getattr(a, 'overlays', []):
            srt = '\n\n'.join(f'{i}\n{stamp(x)} --> {stamp(y)}\n{text}' for i, (x,y,text) in enumerate(cues,1))+'\n'
            target.with_suffix('.srt').write_text(srt, encoding='utf-8')
            header = '[Script Info]\nScriptType: v4.00+\nPlayResX: 1080\nPlayResY: 1920\nWrapStyle: 0\n\n[V4+ Styles]\nFormat: Name, Fontname, Fontsize, PrimaryColour, SecondaryColour, OutlineColour, BackColour, Bold, Italic, Underline, StrikeOut, ScaleX, ScaleY, Spacing, Angle, BorderStyle, Outline, Shadow, Alignment, MarginL, MarginR, MarginV, Encoding\n'
            header += f'Style: Default,{a.font},58,&H00FFFFFF,&H00FFFFFF,&H00101010,&H80000000,-1,0,0,0,100,100,0,0,1,3,1,2,90,160,330,1\n\n[Events]\nFormat: Layer, Start, End, Style, Name, MarginL, MarginR, MarginV, Effect, Text\n'
            lines = []
            for x,y,text in cues:
                # Strip ASS control syntax from content and wrap Japanese captions.
                clean = text.replace('\\', '＼').replace('{', '｛').replace('}', '｝').replace('\n', ' ')
                if len(clean) > 28:
                    raise ValueError('A subtitle exceeds 28 characters. Split it using verified speech/word timing before rendering.')
                chunks = [clean]
                if len(clean) > 14:
                    choices = [i+1 for i,c in enumerate(clean) if c in '、。！？，' and len(clean)-14 <= i+1 <= 14]
                    cut = min(choices, key=lambda i: abs(i-len(clean)/2)) if choices else (len(clean)+1)//2
                    if clean[cut] in '、。！？，．）』」':
                        cut = cut+1 if cut < 14 else cut-1
                    chunks = [clean[:cut], clean[cut:]]
                lines.append(f'Dialogue: 0,{stamp(x,True)},{stamp(y,True)},Default,,0,0,0,,'+r'\N'.join(chunks))
            def overlay_text(value):
                return value.replace('\\', '＼').replace('{', '｛').replace('}', '｝')
            headline = getattr(a, 'headline', '')
            label = getattr(a, 'label', '')
            if headline:
                title_lines = headline.splitlines()
                if len(title_lines) > 3 or any(len(t)>15 for t in title_lines):
                    raise ValueError('Headline must have at most 3 lines of 15 characters')
                title = r'\N'.join(overlay_text(t) for t in title_lines)
                lines.append(f'Dialogue: 1,0:00:00.00,{stamp(end-start,True)},Default,,0,0,0,,'+r'{\an8\pos(540,280)\fs76\c&H4040FF&}'+title)
            if label:
                if len(label)>16 or '\n' in label:
                    raise ValueError('Label must be one line, at most 16 characters')
                lines.append(f'Dialogue: 1,0:00:00.00,{stamp(end-start,True)},Default,,0,0,0,,'+r'{\an8\pos(540,140)\fs68\c&H66FFFF&}'+overlay_text(label))
            for item in getattr(a, 'overlays', []):
                t0, t1 = seconds(item['start']), seconds(item['end'])
                x, y, size = int(item.get('x',540)), int(item['y']), int(item['size'])
                color = item.get('color','FFFFFF')
                if not 0 <= t0 < t1 <= end-start+.01 or not 0 <= x <= 1080 or not 0 <= y <= 1920 or not 20 <= size <= 180 or not re.fullmatch('[0-9A-Fa-f]{6}',color):
                    raise ValueError('Invalid timed overlay')
                outline = item.get('outline_color','000000')
                border, shadow = float(item.get('border',0)), float(item.get('shadow',0))
                if not re.fullmatch('[0-9A-Fa-f]{6}',outline) or not 0 <= border <= 16 or not 0 <= shadow <= 12:
                    raise ValueError('Invalid overlay outline or shadow')
                outline_bgr = outline[4:6]+outline[2:4]+outline[:2]
                bgr = color[4:6]+color[2:4]+color[:2]
                content = r'\N'.join(overlay_text(t) for t in item['text'].splitlines())
                tag = '{'+rf'\an8\pos({x},{y})\fs{size}\c&H{bgr}&\3c&H{outline_bgr}&\4c&H000000&\4a&H00&\bord{border}\shad{shadow}\q2'+'}'
                lines.append(f'Dialogue: 2,{stamp(t0,True)},{stamp(t1,True)},Default,,0,0,0,,'+tag+content)
            lines.sort(key=lambda line: seconds(line.split(',')[1]))
            ass = header+'\n'.join(lines)+'\n'
            (temp/'captions.ass').write_text(ass, encoding='utf-8')
            target.with_suffix('.ass').write_text(ass, encoding='utf-8')
            graph += ';[base]subtitles=captions.ass[v]'
        else:
            graph += ';[base]null[v]'
        partial = temp/'render.mp4'
        cmd = [FFMPEG, '-hide_banner', '-v', 'error', '-ss', str(start), '-i', src, '-t', str(end-start), '-filter_complex', graph, '-map', '[v]', '-map', '0:a:0?', '-c:v', 'libx264', '-preset', 'fast', '-crf', '20', '-pix_fmt', 'yuv420p', '-r', '30', '-c:a', 'aac', '-b:a', '192k', '-ar', '48000', '-movflags', '+faststart', partial]
        run(cmd, cwd=temp)
        check = probe(partial)
        v = next(s for s in check['streams'] if s['codec_type']=='video')
        if (v['width'],v['height']) != (w,h) or abs(duration(check)-(end-start)) > .15:
            raise RuntimeError('Output dimensions or duration failed validation')
        if any(s['codec_type']=='audio' for s in info['streams']) and not any(s['codec_type']=='audio' for s in check['streams']):
            raise RuntimeError('Audio stream was lost')
        run([FFMPEG, '-v', 'error', '-i', partial, '-f', 'null', '-'])
        shutil.copyfile(partial, target)
    dump(target.with_suffix('.json'), {'source':str(src), 'start':start, 'end':end, 'layout':a.layout, 'focus_x':a.focus_x, 'subtitle_count':len(cues), 'width':w, 'height':h, 'duration':duration(check), 'technical_validation':'passed', 'editorial_review':'pending; inspect frames, caption timing and listen to audio'})
    print(target)


def main():
    p = argparse.ArgumentParser(description=__doc__)
    subs = p.add_subparsers(dest='command', required=True)
    subs.add_parser('doctor').set_defaults(func=doctor)
    f = subs.add_parser('fetch'); f.add_argument('url'); f.add_argument('--out', required=True); f.add_argument('--lang', default='ja'); f.add_argument('--max-minutes', type=float, default=120); f.set_defaults(func=fetch)
    t = subs.add_parser('transcript'); g=t.add_mutually_exclusive_group(required=True); g.add_argument('--input'); g.add_argument('--srt'); t.add_argument('--out', required=True); t.add_argument('--lang', default='ja'); t.add_argument('--model', default='small'); t.set_defaults(func=transcript)
    f = subs.add_parser('frames'); f.add_argument('--input', required=True); f.add_argument('--out', required=True); f.add_argument('--start', default='0'); f.add_argument('--end'); f.add_argument('--count', type=int, default=8); f.set_defaults(func=frames)
    r = subs.add_parser('render'); r.add_argument('--input', required=True); r.add_argument('--start', required=True); r.add_argument('--end', required=True); r.add_argument('--out', required=True); r.add_argument('--transcript'); r.add_argument('--layout', choices=['fit','blur','crop'], default='fit'); r.add_argument('--focus-x', type=float, default=.5); r.add_argument('--font', default='Hiragino Sans'); r.add_argument('--draft', action='store_true'); r.add_argument('--headline', default=''); r.add_argument('--label', default=''); r.set_defaults(func=render)
    a=p.parse_args()
    try:
        a.func(a)
    except (RuntimeError, ValueError, OSError, KeyError, ImportError) as e:
        p.exit(1, f'ERROR: {e}\n')

if __name__ == '__main__':
    main()
