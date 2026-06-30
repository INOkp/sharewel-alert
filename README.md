# ShareWel Alert

ShareWel の出品一覧を定期的に確認し、新しく追加された商品名だけを Slack チャンネルへ通知します。

初回起動時は既存の商品を通知せず、状態ファイルに保存します。2回目以降に追加された商品だけを通知します。

## 設定

Slack Incoming Webhook URL を用意します。

GitHub Actionsで実行する場合、Webhook URL は `.env` ではなく GitHub の Repository secret に保存します。
このリポジトリでは `.env` や `.env.example` はコミット対象外です。

主な設定:

```sh
SHAREWEL_CHECK_INTERVAL_SECONDS=60
SHAREWEL_STATE_FILE=.sharewell_state.json
SHAREWEL_NOTIFY_ON_FIRST_RUN=false
SHAREWEL_IN_STOCK_ONLY=true
SHAREWEL_EXPIRED_ALSO=false
```

Slackへ送る本文には、追加された商品の商品名と商品詳細ページへのリンクを含めます。
商品名は引用形式で表示し、商品画像が取得できる場合はSlackのメッセージ内に画像も表示します。

## ローカル実行

現在の商品名だけ確認する場合:

```sh
python3 -m sharewell_alert --print-current
```

初回状態を作る場合:

```sh
set -a
source .env
set +a
python3 -m sharewell_alert --once
```

常駐させる場合:

```sh
set -a
source .env
set +a
python3 -m sharewell_alert
```

## Docker Compose

```sh
# .env を手元で作成し、SLACK_WEBHOOK_URL を設定
docker compose up -d --build
```

状態ファイルは `./data/sharewell_state.json` に保存されます。

## GitHub Actions

常時起動マシンがない場合は、GitHub Actions の定期実行で動かせます。

注意点:

- GitHub Actions では `.env` を使いません。
- `SLACK_WEBHOOK_URL` は GitHub の Repository secret に保存します。
- 定期実行は `.github/workflows/sharewell-alert.yml` で `5分ごと` に設定しています。
- `SHAREWEL_CHECK_INTERVAL_SECONDS` は GitHub Actions では使いません。
- 前回状態は Actions cache に `.sharewell_state.json` として保存します。
- 初回実行では既存商品を通知せず、状態だけ保存します。

### Secret の登録

GitHub の対象リポジトリで以下を設定します。

1. `Settings` を開く
2. `Secrets and variables` を開く
3. `Actions` を開く
4. `New repository secret` を押す
5. `Name` に `SLACK_WEBHOOK_URL` を入力
6. `Secret` に Slack Incoming Webhook URL を貼り付ける
7. `Add secret` で保存

`.env` はコミットしないでください。このリポジトリでは `.gitignore` で除外しています。

### 実行

このリポジトリを GitHub に push すると、以降は5分ごとに実行されます。

手動で試す場合:

1. GitHub リポジトリの `Actions` タブを開く
2. `ShareWel Alert` を選ぶ
3. `Run workflow` を押す

`Run workflow` の `mode` は以下から選べます。

```text
check        通常チェック。初回は状態保存のみ、2回目以降は新規商品があれば通知。
slack-test   固定文言をSlackへ送信。Slack SecretとWebhook疎通だけ確認。
simulate-new 現在のShareWel商品名を1件だけ新着扱いでSlackへ送信。通常の状態ファイルは変更しない。
```

### スレッド詳細

Incoming Webhookだけでも親通知は送れます。通知スレッドに詳細情報を返信したい場合は、追加でSlack Bot TokenとChannel IDをRepository secretに登録します。

必要なRepository secret:

```text
SLACK_BOT_TOKEN
SLACK_CHANNEL_ID
```

Bot Tokenには `chat:write` scope が必要です。Botを通知先チャンネルへ招待しておいてください。

この設定がある場合、親通知のスレッドに以下を投稿します。

```text
説明
出品者
掲載期限
場所
品目
メイン画像以外の追加画像
```

## 動作確認

Slackへ送らず、状態ファイルも更新しない確認:

```sh
set -a
source .env
set +a
python3 -m sharewell_alert --once --dry-run
```

テスト:

```sh
python3 -m unittest
```
