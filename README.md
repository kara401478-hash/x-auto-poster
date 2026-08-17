# x-auto-poster

はてなブログ(`nisa-sp500.hatenablog.com`)の新着記事を検知し、
Groq API でツイート文を生成して X(旧Twitter)に自動投稿する GitHub Actions Bot。

## 仕組み

1. 毎日 JST 21:00 に GitHub Actions が起動(手動実行も可)
2. ブログの RSS フィードを取得
3. `posted.json` と照合し、未投稿の記事だけを抽出(最大3件/回)
4. Groq API (`llama-3.3-70b-versatile`) でツイート文を生成
5. tweepy で X に投稿
6. 投稿済みURLを `posted.json` に追記してコミット

## セットアップ

### 1. GitHub Secrets の登録

Settings → Secrets and variables → Actions → New repository secret で以下を登録:

| Secret名 | 内容 |
|---|---|
| `X_API_KEY` | X Developer PortalのAPI Key |
| `X_API_SECRET` | X Developer PortalのAPI Secret |
| `X_ACCESS_TOKEN` | Access Token |
| `X_ACCESS_TOKEN_SECRET` | Access Token Secret |
| `GROQ_API_KEY` | Groq APIキー(未設定でも動くが、その場合はタイトルそのまま投稿するフォールバックになる) |

X側アプリの権限は **Read and Write** になっている必要があります。
(Read onlyのまま発行したトークンだと投稿時に403エラーになります)

### 2. ローカルでのテスト実行(任意)

```bash
pip install -r requirements.txt
export X_API_KEY=...
export X_API_SECRET=...
export X_ACCESS_TOKEN=...
export X_ACCESS_TOKEN_SECRET=...
export GROQ_API_KEY=...
python post_tweet.py
```

### 3. 動作確認

リポジトリの Actions タブ →「Auto Post to X」→「Run workflow」で手動実行できます。
初回は `posted.json` が空なので、既存のブログ記事が最大3件まとめて投稿される点に注意してください。
過去記事を投稿したくない場合は、事前に `posted.json` へ既存記事のURLを手動で入れておいてください。

## カスタマイズ

- 投稿頻度: `.github/workflows/post.yml` の `cron` を変更
- 1回あたりの最大投稿数: `post_tweet.py` の `MAX_NEW_POSTS_PER_RUN`
- 投稿ネタの追加(nijihoro更新情報など): `fetch_new_entries` と同じパターンで別関数を追加し、`main()` でマージする形で拡張可能
