"""
x-auto-poster (通知版)
ブログ(はてなブログ)のRSSフィードから新着記事を検知し、
Groq APIでツイート文案を生成して、メールで通知するスクリプト。
(X APIのPay-Per-Use課金・クレカ登録を避けるため、直接投稿はせず
 「文案をメールで送る→手動でXに貼る」運用に変更したバージョン)

処理の流れ:
1. RSSフィードを取得
2. posted.json (通知済みURLリスト) と比較して未通知の記事を抽出
3. 未通知記事があれば、Groq APIで100字以内のツイート文案を生成
4. Gmail SMTPでメール通知(件名・本文にツイート文案+記事リンク)
5. posted.json を更新(コミットはワークフロー側で実施)
"""

import json
import os
import smtplib
import sys
from email.mime.text import MIMEText
from pathlib import Path

import feedparser
from groq import Groq

# ---- 設定 ----
RSS_URL = "https://nisa-sp500.hatenablog.com/rss"
POSTED_FILE = Path(__file__).parent / "posted.json"
MAX_NEW_NOTICES_PER_RUN = 3  # 1回の実行で通知する最大件数
SMTP_HOST = "smtp.gmail.com"
SMTP_PORT = 587


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


def generate_tweet_draft(title: str, link: str) -> str:
    """Groq APIでツイート文案を生成。失敗時はシンプルなフォールバック文を返す。"""
    api_key = os.environ.get("GROQ_API_KEY")
    if not api_key:
        return f"[Groq未設定のためタイトルをそのまま使用]\n{title} {link}"

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
            model="openai/gpt-oss-120b",
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
        return f"[Groq生成失敗: {e}]\n{title} {link}"


def send_notification_email(entries_with_drafts: list) -> None:
    """新着記事+ツイート文案をまとめて1通のメールで通知する。"""
    sender = os.environ["GMAIL_ADDRESS"]
    app_password = os.environ["GMAIL_APP_PASSWORD"]
    recipient = os.environ["NOTIFY_EMAIL_TO"]

    lines = []
    for item in entries_with_drafts:
        lines.append(f"■ {item['title']}")
        lines.append(f"文案:\n{item['draft']}")
        lines.append("---")
    body = "\n\n".join(lines)

    msg = MIMEText(body, "plain", "utf-8")
    msg["Subject"] = f"【ブログ新着】Xへ投稿する記事が{len(entries_with_drafts)}件あります"
    msg["From"] = sender
    msg["To"] = recipient

    with smtplib.SMTP(SMTP_HOST, SMTP_PORT) as server:
        server.starttls()
        server.login(sender, app_password)
        server.send_message(msg)


def main():
    posted = load_posted()
    new_entries = fetch_new_entries(posted)

    if not new_entries:
        print("新着記事はありませんでした。")
        return

    targets = new_entries[:MAX_NEW_NOTICES_PER_RUN]
    print(f"{len(targets)}件の新着記事を通知します。")

    entries_with_drafts = []
    for entry in targets:
        draft = generate_tweet_draft(entry["title"], entry["link"])
        entries_with_drafts.append({"title": entry["title"], "link": entry["link"], "draft": draft})

    try:
        send_notification_email(entries_with_drafts)
        print("メール通知に成功しました。")
        for entry in targets:
            posted.add(entry["link"])
    except Exception as e:
        print(f"メール通知に失敗しました: {e}", file=sys.stderr)
        # 失敗時は posted に追加しない(次回リトライ対象にする)
        return

    save_posted(posted)


if __name__ == "__main__":
    main()
