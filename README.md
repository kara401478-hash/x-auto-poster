# x-auto-poster (通知版)

はてなブログ(`nisa-sp500.hatenablog.com`)の新着記事を検知し、
Groq API でツイート文案を生成して、**メールで通知する** GitHub Actions Bot。

X API の Pay-Per-Use 課金(クレジットカード登録必須)を避けるため、
直接 X には投稿せず、「ツイート文案をメールで受け取り、手動でXアカウントに貼り付けて投稿する」運用にしています。

## 仕組み

1. 毎日 JST 21:00 に GitHub Actions が起動(手動実行も可)
2. ブログの RSS フィードを取得
3. `posted.json` と照合し、未通知の記事だけを抽出(最大3件/回)
4. Groq API (`llama-3.3-70b-versatile`) でツイート文案を生成
5. Gmail SMTP で通知メールを送信(件名+本文にタイトル・文案・リンクをまとめる)
6. 通知済みURLを `posted.json` に追記してコミット

## セットアップ

### 1. Gmailアプリパスワードの準備

投資通知botで使っているGmailアカウントを送信元として使い回す想定です。
2段階認証を有効化したGoogleアカウントの「アプリパスワード」を発行してください
(通常のログインパスワードではSMTP認証は通りません)。

### 2. GitHub Secrets の登録

Settings → Secrets and variables → Actions → New repository secret で以下を登録:

| Secret名 | 内容 |
|---|---|
| `GMAIL_ADDRESS` | 送信元Gmailアドレス(投資通知botと同じものでOK) |
| `GMAIL_APP_PASSWORD` | 上記アカウントのアプリパスワード |
| `NOTIFY_EMAIL_TO` | 通知を受け取りたい宛先メールアドレス(別アドレス指定可) |
| `GROQ_API_KEY` | Groq APIキー(未設定でも動くが、その場合はタイトルそのまま通知するフォールバックになる) |

### 3. ローカルでのテスト実行(任意)

```bash
pip install -r requirements.txt
export GMAIL_ADDRESS=...
export GMAIL_APP_PASSWORD=...
export NOTIFY_EMAIL_TO=...
export GROQ_API_KEY=...
python post_tweet.py
```

### 4. 動作確認

リポジトリの Actions タブ →「Blog Update Notifier」→「Run workflow」で手動実行できます。
初回は `posted.json` が空なので、既存のブログ記事が最大3件まとめて通知される点に注意してください。
過去記事分の通知が不要なら、事前に `posted.json` へ既存記事のURLを手動で入れておいてください。

## 運用の流れ

1. 通知メールが届く
2. 文案とリンクをコピー
3. TM_automation4アカウントに切り替えてXに貼り付け・投稿

## カスタマイズ

- 通知頻度: `.github/workflows/post.yml` の `cron` を変更
- 1回あたりの最大通知数: `post_tweet.py` の `MAX_NEW_NOTICES_PER_RUN`
- 通知ネタの追加(nijihoro更新情報など): `fetch_new_entries` と同じパターンで別関数を追加し、`main()` でマージする形で拡張可能
