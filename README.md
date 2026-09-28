# YouTube Shorts Skill — APIフィリピン不動産

YouTube URLまたはローカル動画から、結論先出し・大きな赤白見出し・黄色の要点・本編サムネイル付きの縦型ショートを作るCodexスキルです。

**対象チャンネルは [APIフィリピン不動産（@apigatewayph）](https://www.youtube.com/@apigatewayph) のみ。** 他の担当者への引き継ぎ用として公開しています。チャンネル外の動画を取得する汎用ダウンローダーではありません。

## 標準の完成形

- 冒頭3〜5秒：本人の結論をダイジェストで先出し
- 本体：理由・説明を、必要に応じて複数区間から連結
- 1080×1920・黒背景・中央に横動画・元字幕を保持
- 上部：123〜132pxの赤太字＋白い縁取り
- 下部：105pxの黄色文字で場面ごとの要点
- 最後3秒：本編の実サムネイル、「続きは本編をチェック！」、「下の関連動画をタップ ↓↓↓」
- MP4、投稿タイトル・概要欄、編集プラン、検証結果、投稿時のリンク設定手順を保存

文言と切り抜き時刻は動画ごとに分析します。内容判断はCodexが担当し、Pythonだけで意味解析や全自動選定をするものではありません。

## ダウンロード・設置

[Releases](https://github.com/yugen0203/youtube-shorts-skill/releases/latest) の `youtube-shorts-portable.zip` をダウンロードして展開し、中の `youtube-shorts` フォルダをCodexのスキル置き場へコピーします。既定の配置先は `~/.codex/skills/youtube-shorts` です。CODEX_HOMEを設定している環境では、そのskillsフォルダに置いてください。既存の同名スキルに独自変更がある場合は退避してから更新します。

リポジトリの **Code → Download ZIP** でも取得できます。その場合はリポジトリ全体ではなく、中の `youtube-shorts` フォルダを設置します。

## 必要な環境

- Python 3
- FFmpeg / ffprobe（libass・H.264・AAC対応）
- yt-dlp（YouTubeから取得する場合）
- 日本語フォント。macOS既定はHiragino Sans。他OSはCJKフォントを導入して指定
- openai-whisper（音声認識を使う場合のみ。モデル初回取得にはネット接続が必要）

スクリプト本体の基本処理はPython標準ライブラリと上記コマンドを使います。APIキーは必須ではありません。

```sh
python3 ~/.codex/skills/youtube-shorts/scripts/shorts.py doctor
```

macOSで実動画制作を検証しました。他OSではフォント・依存コマンドの確認と試作を行ってください。付属 `test_shorts.py` はmacOSのsay音声を使うためmacOS用です。

## Codexへの依頼例

```text
$youtube-shorts このYouTube URLから、見どころを選んでショートを1本作ってください。
結論先出し、大きな赤文字と白縁、黄色の要点、最後3秒の本編サムネイルを含む標準仕様で。
保存先は /希望するフォルダ です。
```

担当者や保存先が変わっても、スキル本体のパスを書き換える必要はありません。保存先は毎回の実行引数またはSHORTS_OUTPUT_DIRで指定します。素材やサムネイルは利用者側で用意・取得し、編集プラン内の相対パスで管理します。

具体的な構成は [SKILL.md](youtube-shorts/SKILL.md)、サイズと編集プランは [編集仕様](youtube-shorts/references/channel-editing.md)、プランの雛形は [examples/plan.json](youtube-shorts/examples/plan.json) を参照してください。雛形の時刻・文言は実素材に必ず置き換えてください。

## 取得と投稿の制約

yt-dlpで取得できない場合、対応ブラウザツールがあればTurboScribe経路を試します。YouTubeや利用ツールの制限で取得できない場合もあるため、完全自動ダウンロードを保証しません。制限を別経路で回避せず、提供されたローカルMP4から再開できます。

MP4内の矢印・サムネイルはクリックできません。投稿後にYouTube Studioの「関連動画」で本編を設定することで導線が機能します。上級者向け機能へのアクセスが必要です。Shorts概要欄の通常URLはクリックできません。[公式手順](https://support.google.com/youtube/answer/14075157?hl=ja)。投稿・関連動画の設定は自動では実行しません。

## 検証と配布内容

実動画の複数区間連結、縦型化、場面別テキスト、末尾3秒サムネイル、全編デコードを検証済み。過去の自作素材テスト12項目と取得検証5項目も通過しています。映像・音声の技術検証と人による聴感確認は別です。公開物には元動画・完成動画・サムネイル・ログイン情報・利用者の絶対パスを含めません。
