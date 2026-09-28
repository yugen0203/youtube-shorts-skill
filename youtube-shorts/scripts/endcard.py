#!/usr/bin/env python3
"""Append a thumbnail CTA to a finished 1080x1920 Short. No upload or link-setting."""
import argparse
import json
from pathlib import Path
import shutil
import tempfile
from types import SimpleNamespace
import shorts as m


def append_endcard(src, thumbnail, target, source_url, seconds=3, font='Hiragino Sans'):
    src, thumbnail, target = [Path(x).expanduser().resolve() for x in (src, thumbnail, target)]
    if not 1 <= seconds <= 10:
        raise ValueError('End card must be 1 to 10 seconds')
    if target.suffix.lower() != '.mp4' or any(target.with_suffix(s).exists() for s in ['.mp4','.json','.description.txt','.publish.md','.edit-plan.json']):
        raise ValueError('Choose a new .mp4 output path')
    info = m.probe(src); length = m.duration(info)
    video = next(s for s in info['streams'] if s['codec_type']=='video')
    if (video['width'],video['height']) != (1080,1920) or length + seconds > 180:
        raise ValueError('Input must be 1080x1920 and combined length <=180 seconds')
    if not any(s['codec_type']=='audio' for s in info['streams']):
        raise ValueError('Input needs an audio stream')
    target.parent.mkdir(parents=True,exist_ok=True)
    overlays = [
        dict(start=0,end=seconds,text='物件選びの続きはこちら',y=150,size=50,color='FFFFFF'),
        dict(start=0,end=seconds,text='続きは本編を\nチェック！',y=280,size=132,color='FF2538',outline_color='FFFFFF',border=8,shadow=3),
        dict(start=0,end=seconds,text='下の関連動画をタップ',y=1350,size=98,color='FFE600',outline_color='161000',border=6,shadow=3),
        dict(start=0,end=seconds,text='↓↓↓',y=1500,size=170,color='FFE600',outline_color='161000',border=6,shadow=3),
    ]
    with tempfile.TemporaryDirectory(prefix='shorts-endcard-') as tmp:
        tmp=Path(tmp); still=tmp/'still.mp4'; card=tmp/'card.mp4'; out=tmp/'final.mp4'
        m.run([m.FFMPEG,'-v','error','-loop','1','-framerate','30','-i',thumbnail,'-f','lavfi','-i','anullsrc=r=48000:cl=stereo','-t',str(seconds),'-c:v','libx264','-preset','fast','-crf','16','-pix_fmt','yuv420p','-c:a','aac',still])
        m.render(SimpleNamespace(input=str(still),out=str(card),start='0',end=str(seconds),focus_x=.5,transcript=None,layout='fit',draft=False,font=font,headline='',label='',overlays=overlays))
        graph='[0:v]setsar=1,setpts=PTS-STARTPTS[v0];[1:v]setsar=1,setpts=PTS-STARTPTS[v1];[0:a]aresample=48000,asetpts=PTS-STARTPTS[a0];[1:a]aresample=48000,asetpts=PTS-STARTPTS[a1];[v0][a0][v1][a1]concat=n=2:v=1:a=1[v][a]'
        m.run([m.FFMPEG,'-v','error','-i',src,'-i',card,'-filter_complex',graph,'-map','[v]','-map','[a]','-r','30','-c:v','libx264','-crf','18','-preset','fast','-pix_fmt','yuv420p','-c:a','aac','-b:a','192k','-movflags','+faststart',out])
        final_info=m.probe(out); actual=m.duration(final_info)
        if abs(actual-length-seconds)>.15: raise ValueError('Unexpected duration after concatenation')
        m.run([m.FFMPEG,'-v','error','-xerror','-i',out,'-f','null','-'])
        shutil.copy2(out,target)
    plan={'input':str(src),'thumbnail':str(thumbnail),'source_url':source_url,'endcard_start':length,'endcard_seconds':seconds,'overlays':overlays,'clickable_link':'Set Related video in YouTube Studio; burned-in graphics are not interactive','audio':'3-second endcard uses silence'}
    m.dump(target.with_suffix('.edit-plan.json'),plan)
    m.dump(target.with_suffix('.json'),{'width':1080,'height':1920,'duration':actual,'technical_validation':'passed; full decode and duration checked','editorial_review':'pending','endcard':plan})
    previous=src.with_suffix('.description.txt')
    if previous.exists():shutil.copy2(previous,target.with_suffix('.description.txt'))
    target.with_suffix('.publish.md').write_text(f'''# 投稿時の本編リンク設定\n\nMP4の矢印やサムネイルは画像でありクリック機能はありません。Shorts概要欄のURLもクリックできません。\n\nYouTube Studio → コンテンツ → 投稿したショート → 関連動画 → 下記の本編を選択 → 保存。\n\n{source_url}\n\n関連動画には上級者向け機能へのアクセスと、公開または限定公開の本編が必要です。設定後、チャンネルハンドル下の関連動画リンクから本編に進めることを確認してください。表示位置は端末により変わるため、画像の矢印位置でリンクそのものを作ることはできません。\n\n投稿・関連動画の設定はこのスクリプトでは実行していません。\n\n公式手順：https://support.google.com/youtube/answer/14075157?hl=ja\nリンク仕様：https://support.google.com/youtube/answer/13748639?hl=ja\n''',encoding='utf-8')
    print(target)

if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--input',required=True);p.add_argument('--thumbnail',required=True);p.add_argument('--out',required=True);p.add_argument('--source-url',required=True)
    p.add_argument('--seconds',type=float,default=3);p.add_argument('--font',default='Hiragino Sans')
    a=p.parse_args()
    append_endcard(a.input,a.thumbnail,a.out,a.source_url,a.seconds,a.font)
