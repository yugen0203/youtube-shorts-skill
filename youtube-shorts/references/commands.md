# コマンドと形式

Python 3、起動するFFmpeg/ffprobe（libass字幕フィルタ付き）、URL取得時yt-dlpが必要。ASR利用時のみPython環境にopenai-whisperが必要。Python依存は既存環境または専用venvを使い、グローバル環境を不用意に入れ替えない。

`SHORTS_FFMPEG` / `SHORTS_FFPROBE` 環境変数で別の実行バイナリを選択できる。Whisperが音声を読み込むため、正常なffmpegをPATHにも置く。日本語フォントの既定はmacOSのHiragino Sans。他OSでは実際に導入済みのCJKフォントを `--font` で指定する。

以下ではSを `scripts/shorts.py` の絶対パス、各入出力を作業用の絶対パスとする。URLやファイル名はシェル文字列として安全に引用する。

```sh
python3 "$S" doctor
python3 "$S" fetch 'https://www.youtube.com/watch?v=VIDEO_ID_11' --out source --lang ja
python3 "$S" transcript --srt source/source.ja.srt --out transcript.json
# 字幕がない場合
python3 "$S" transcript --input source/source.mp4 --model small --lang ja --out transcript.json
python3 "$S" frames --input source/source.mp4 --out overview --count 8
python3 "$S" frames --input source/source.mp4 --start 2:10 --end 2:45 --out candidate-frames --count 8
python3 "$S" render --input source/source.mp4 --start 2:10 --end 2:45 --transcript edited-transcript.json --layout fit --out clip-01.mp4
```

fetchはYouTube単一動画だけを取得し、120分の上限を設ける。長い素材を意図して扱う場合のみ `--max-minutes` を変更する。再取得は空の別ディレクトリで行い、途中まで保存した素材を自動削除しない。実際の拡張子は取得結果を確認する。

字幕JSON（元動画基準、秒）:
```json
{"timebase":"source_seconds","method":"human reviewed","segments":[{"start":130.2,"end":132.6,"text":"まず結論を話します。"}]}
```

edit-plan.json（Codexが内容分析して記入する。スクリプトが自動生成するわけではない）:
```json
{"source_url":"...","mode":"exact","clips":[{"start":130,"end":165,"quote":"実際の発言を引用","reason":"指定区間","layout":"fit","subtitle_corrections":[],"unverified":[]}]}
```

`render` のlayoutは `fit`（全体を黒余白に収める）、`blur`（全体＋ぼかし背景）、`crop`（静的切り抜き）。`--draft` は720×1280。それ以外は1080×1920。音声はある場合のみ維持し、無音素材に架空の音声を追加しない。

現実的な制約：YouTube側の変更・ログイン要求で取得できない場合がある。字幕取得失敗でも動画を保持する。ASRの正確性、話題選定、音声の自然さはバイナリ検査だけで保証できない。動的顔追跡、話者の上下分割、単語ごとのカラオケ字幕、投稿APIはこの版のスクリプトには含めない。

## ブラウザによる取得への切替

fetchの動画取得が失敗した場合は、作業先にacquisition-state.jsonを保存する。statusがbrowser_fallback_neededなら [browser-download.md](browser-download.md) に従い、CodexのブラウザツールでTurboScribeを操作する。この状態はダウンロード成功を表さない。保存後はaccept_download.pyで全編デコード・音声・尺を検証して取り込む。署名付き配信URLは引き継ぎ資料へ保存しない。
