"""
ブログ記事自動生成・投稿スクリプト
- Claude API (Haiku 4.5) で記事生成
- WordPress REST API で投稿（下書き保存）
"""

import os
import json
import random
import requests
from datetime import datetime
from base64 import b64encode

# ─────────────────────────────────────────
# 設定（GitHub Secrets から自動取得）
# ─────────────────────────────────────────
WP_URL        = os.environ["WP_URL"]
WP_USER       = os.environ["WP_USER"]
WP_APP_PASS   = os.environ["WP_APP_PASS"]
ANTHROPIC_KEY = os.environ["ANTHROPIC_API_KEY"]

# ─────────────────────────────────────────
# 記事テーマ候補
# ─────────────────────────────────────────
THEMES = [
    {"title_hint": "30代子育て世帯のふるさと納税活用術",                     "keyword": "ふるさと納税 子育て 30代"},
    {"title_hint": "年収700万円台でも保険は見直せる｜実体験から考える最適解", "keyword": "保険 見直し 年収700万"},
    {"title_hint": "NISAとiDeCo、どちらを優先すべきか？30代の正解",         "keyword": "NISA iDeCo 優先 30代"},
    {"title_hint": "子育て世帯が知っておくべき児童手当の使い方",             "keyword": "児童手当 使い方 資産形成"},
    {"title_hint": "不動産投資セミナーに行って分かったこと｜30代会社員の視点","keyword": "不動産投資 セミナー 30代 体験"},
    {"title_hint": "家計の生活防衛資金、いくら持てば安心？我が家の基準",     "keyword": "防衛資金 生活費 何ヶ月分"},
    {"title_hint": "クレジットカードのポイントを資産形成に活かす方法",       "keyword": "クレジットカード ポイント 資産形成"},
]


def pick_theme():
    seed = int(datetime.now().strftime("%Y%m%d"))
    random.seed(seed)
    return random.choice(THEMES)


def generate_article(theme: dict) -> dict:
    system_prompt = """
あなたは「コンサルパパの家族資産設計ブログ」の著者です。
プロフィール：33歳・会社員・コンサルタント・妻と1歳娘の3人家族・年収700万円台。
トーン：専門的だが親しみやすい。実体験・実数字を交えて書く。
ターゲット読者：30代共働き子育て世帯、資産形成に興味があるが何から始めればいいか分からない層。

記事のルール：
- 文字数は2,000〜2,500字
- 見出し（h2タグ）を3〜4個使う
- 冒頭に読者の悩みを共感的に書く
- 末尾に「まとめ」セクションを入れる
- アフィリエイトリンクの[PR]プレースホルダーを適切な箇所に1〜2個入れる（例：[PR:保険相談無料]）
- HTMLで出力する（WordPressにそのまま貼れる形式）

出力形式：
必ずJSON形式のみで返すこと。マークダウンのコードブロック（```）は絶対に使わない。
{"title": "記事タイトル", "content": "HTML本文", "excerpt": "120字以内の抜粋"}
""".strip()

    user_prompt = f"テーマ：{theme['title_hint']}\n狙うキーワード：{theme['keyword']}"

    response = requests.post(
        "https://api.anthropic.com/v1/messages",
        headers={
            "x-api-key": ANTHROPIC_KEY,
            "anthropic-version": "2023-06-01",
            "content-type": "application/json",
        },
        json={
            "model": "claude-haiku-4-5-20251001",
            "max_tokens": 4096,
            "system": system_prompt,
            "messages": [{"role": "user", "content": user_prompt}],
        },
        timeout=120,
    )
    response.raise_for_status()

    raw = response.json()["content"][0]["text"].strip()

    # コードブロックが混入した場合の保険
    if "```" in raw:
        raw = raw.split("```")[1]
        if raw.startswith("json"):
            raw = raw[4:].strip()

    return json.loads(raw)


def post_to_wordpress(article: dict) -> str:
    token = b64encode(f"{WP_USER}:{WP_APP_PASS}".encode()).decode()
    headers = {
        "Authorization": f"Basic {token}",
        "Content-Type": "application/json",
    }
    base = WP_URL.rstrip("/")

    # 認証テスト
    me = requests.get(f"{base}/wp-json/wp/v2/users/me", headers=headers, timeout=30)
    if me.status_code != 200:
        raise Exception(f"WordPress認証失敗: {me.status_code} {me.text[:200]}")
    print(f"[WordPress認証OK] ユーザー: {me.json().get('name')}")

    # カテゴリなしでシンプルに下書き投稿
    post_data = {
        "title":   article["title"],
        "content": article["content"],
        "excerpt": article.get("excerpt", ""),
        "status":  "draft",
    }

    res = requests.post(
        f"{base}/wp-json/wp/v2/posts",
        headers=headers,
        json=post_data,
        timeout=30,
    )

    if res.status_code not in (200, 201):
        raise Exception(f"投稿失敗: {res.status_code} {res.text[:300]}")

    return res.json().get("link", "（URL取得失敗）")


def main():
    theme = pick_theme()
    print(f"[テーマ] {theme['title_hint']}")

    print("[記事生成中...]")
    article = generate_article(theme)
    print(f"[タイトル] {article['title']}")

    print("[WordPress投稿中（下書き）...]")
    url = post_to_wordpress(article)
    print(f"[完了] 下書き保存: {url}")
    print("※ WordPress管理画面→投稿→下書きを確認し、[PR]箇所にASPリンクを挿入後、公開してください。")


if __name__ == "__main__":
    main()
