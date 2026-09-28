# 調査と設計根拠

調査日：2026-09-28。以下は公開説明の確認であり、各OSSのインストール・品質比較・再生数効果の実証ではない。SNS投稿は開発者の自己申告として扱う。

| 事例 | 確認できた構成 | 今回の採用判断 |
|---|---|---|
| [NouClip](https://github.com/nouverse/nouclip) | エージェント向けCLI、時刻指定、字幕、縦型化、素材保存。skills/nouclipも公開 | 時刻指定と素材・中間ファイル保存を採用。CLI全体への依存は追加せず小さなPython補助スクリプトにする |
| [OpenShorts](https://github.com/mutonby/openshorts) | 長尺から候補抽出、顔追跡、字幕、API/MCPなどを掲げる | 候補選定とレンダリングを分ける。追跡・配信・Docker基盤は初版の必須にしない |
| [clipper](https://github.com/Steezy-code/clipper) | Whisper→LLM選定→OpenCV追跡→FFmpegのローカル構成 | ローカル文字起こしを採用し、選定判断は実行中のCodexが行う |
| [Reddit開発事例](https://www.reddit.com/r/SideProject/comments/1prme0a/i_was_tired_of_overpriced_clip_tools_so_i_made_my/) | 2025-12-20公開。Geminiで候補を選び縦型動画を生成するという開発者投稿 | 実用例が公開されていることの確認。品質・「バズる」効果の根拠にはしない |
| [Reddit n8n事例](https://www.reddit.com/r/n8n/comments/1vur5d9/i_have_created_a_workflow_that_creates_viral/) | 2026-08-21公開。OpenShorts→Telegram確認→スケジュール投稿という投稿 | 今回の依頼はファイル制作まで。公開・スケジュール投稿を勝手に付加しない |

## 推奨設計

専用SaaSの全面導入よりも、Codexの内容判断＋yt-dlp＋Whisper＋FFmpegを組み合わせたスキルが今回の用途に合う。APIキーなしでローカル編集でき、指定区間を再現できる。AI選定は字幕と実フレームを照合し、字幕だけで映像内容を断定しない。

成否は①取得できること②時刻が正確なこと③発言の意味を損なわないこと④縦型で重要な部分が残ること⑤日本語字幕の読みやすさ⑥音声と字幕の同期、で評価する。汎用的な「バズりスコア」は実証できないため付けない。

単独話者ならcrop、資料や対談ならfit/blurという分岐を優先する。自動追跡は便利だが、初版で実装済みと見せかけず将来の拡張にする。

## 一次資料

- [yt-dlp公式](https://github.com/yt-dlp/yt-dlp)：字幕取得、動画形式、再試行などのCLI仕様。
- [Whisper公式](https://github.com/openai/whisper)：ローカル音声認識、多言語対応、モデルの速度と精度のトレードオフ。
- [FFmpegフィルタ公式](https://ffmpeg.org/ffmpeg-filters.html)：scale、crop、pad、overlay、subtitlesなど。
- [YouTube公式：3分間のショート](https://support.google.com/youtube/answer/15424877?hl=ja)：正方形または縦長、最長3分という区分。実際の投稿時には最新条件を再確認する。
