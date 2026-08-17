"""
x-auto-poster
ブログ(はてなブログ)のRSSフィードから新着記事を検知し、
Groq APIでツイート文を生成してXに自動投稿するスクリプト。

処理の流れ:
1. RSSフィードを取得
2. posted.json (投稿済みURLリスト) と比較して未投稿の記事を抽出
3. 未投稿記事があれば、Groq APIで140字以内のツイート文を生成
4. tweepyでXに投稿
5. posted.json を更新(コミットはワークフロー側で実施)
"""

import json
import os
import sys
from pathlib import Path

import feedparser
import tweepy
from groq import Groq

# ---- 設定 ----
RSS_URL = "https://nisa-sp500.hatenablog.com/rss"
POSTED_FILE = Path(__file__).parent / "posted.json"
MAX_NEW_POSTS_PER_RUN = 3  # 1回の実行で投稿する最大件数(まとめて投下して垢BANされないよう制限)


def load_posted() -> set:
    if not POSTED_FILE.exists():
        return set()
    with open(POSTED_FILE, "r", encoding="utf-8") as f:
        return set(json.load(f))


def save_posted(posted: set) -> None:
    with open(POSTED_FILE, "w", encoding="utf-8") as f:
        json.dump(sorted(posted), f, ensure_ascii=False, indent=2)


def fetch_new_entries(posted: set):
    feed = feedparser.parse(RSS_URL)
    if feed.bozo and not feed.entries:
        print(f"RSS取得に失敗した可能性があります: {feed.bozo_exception}", file=sys.stderr)
        return []

    new_entries = []
    for entry in feed.entries:
        link = entry.get("link")
        title = entry.get("title")
        if not link or not title:
            continue
        if link in posted:
            continue
        new_entries.append({"title": title, "link": link})

    # 古い記事から順に投稿したいのでRSSの並び(新しい順)を逆にする
    new_entries.reverse()
    return new_entries


def generate_tweet_text(title: str, link: str) -> str:
    """Groq APIでツイート文を生成。失敗時はシンプルなフォールバック文を返す。"""
    api_key = os.environ.get("GROQ_API_KEY")
    if not api_key:
        return f"【新着記事】{title} {link}"

    try:
        client = Groq(api_key=api_key)
        prompt = (
            "以下のブログ記事タイトルをもとに、Twitter(X)投稿用の文章を日本語で1つ作成してください。\n"
            "条件:\n"
            "- URLを含めない(あとで別途付与するため)\n"
            "- 絵文字は0〜1個まで\n"
            "- 100文字以内\n"
            "- 煽り文句や誇張は避け、内容が伝わる自然な文にする\n"
            "- 出力はツイート本文のみ。前置きや説明文は書かない\n\n"
            f"記事タイトル: {title}"
        )
        resp = client.chat.completions.create(
            model="llama-3.3-70b-versatile",
            messages=[{"role": "user", "content": prompt}],
            max_tokens=200,
            temperature=0.7,
        )
        body = resp.choices[0].message.content.strip()
        # 万一長すぎた場合の保険
        if len(body) > 100:
            body = body[:97] + "..."
        return f"{body}\n{link}"
    except Exception as e:
        print(f"Groq生成に失敗、フォールバック文を使用します: {e}", file=sys.stderr)
        return f"【新着記事】{title} {link}"


def post_to_x(text: str) -> None:
    client = tweepy.Client(
        consumer_key=os.environ["X_API_KEY"],
        consumer_secret=os.environ["X_API_SECRET"],
        access_token=os.environ["X_ACCESS_TOKEN"],
        access_token_secret=os.environ["X_ACCESS_TOKEN_SECRET"],
    )
    client.create_tweet(text=text)


def main():
    posted = load_posted()
    new_entries = fetch_new_entries(posted)

    if not new_entries:
        print("新着記事はありませんでした。")
        return

    targets = new_entries[:MAX_NEW_POSTS_PER_RUN]
    print(f"{len(targets)}件の新着記事を投稿します。")

    for entry in targets:
        text = generate_tweet_text(entry["title"], entry["link"])
        try:
            post_to_x(text)
            print(f"投稿成功: {entry['title']}")
            posted.add(entry["link"])
        except Exception as e:
            print(f"投稿失敗: {entry['title']} / {e}", file=sys.stderr)
            # 失敗した記事は posted に追加しない(次回リトライ対象にする)

    save_posted(posted)


if __name__ == "__main__":
    main()
