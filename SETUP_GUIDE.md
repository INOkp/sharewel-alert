# ShareWel Alert 導入マニュアル

ShareWelに新しい商品が出品されると、Slackに自動で通知するBotです。
GitHub Actionsで30分ごとに動くため、サーバーは不要です。

---

## 全体の流れ

1. Slackの準備（Webhook URLの取得）
2. GitHubリポジトリの準備
3. Secretの登録
4. 動作確認

所要時間：15〜20分程度

---

## 1. Slackの準備

### Incoming Webhook URLを取得する

1. https://api.slack.com/apps にアクセス
2. **Create New App** → **From scratch** を選択
3. App名（例：`ShareWel Alert`）を入力し、通知を送りたいワークスペースを選択
4. 左メニューの **Incoming Webhooks** を開く
5. **Activate Incoming Webhooks** を **On** にする
6. ページ下部の **Add New Webhook to Workspace** を押す
7. 通知先のチャンネルを選んで **許可する**
8. 表示された **Webhook URL**（`https://hooks.slack.com/services/...`）をコピーして控えておく

> これだけで基本の通知は動きます。次のBot Token設定は任意です。

### （任意）Bot Tokenを取得する

Bot Tokenを設定すると、通知メッセージのスレッドに商品の詳細情報（説明、出品者、場所、画像など）を自動で返信します。

1. 同じアプリの設定画面で、左メニューの **OAuth & Permissions** を開く
2. **Scopes** → **Bot Token Scopes** に `chat:write` を追加する
3. ページ上部の **Install to Workspace** を押して再インストール
4. 表示された **Bot User OAuth Token**（`xoxb-...`）をコピーして控えておく
5. Slackで通知先チャンネルを開き、チャンネル名をクリック → **インテグレーション** → **アプリを追加する** から、作成したアプリを追加する
6. チャンネルの詳細画面の下部に表示される **チャンネルID**（`C`で始まる英数字）を控えておく

---

## 2. GitHubリポジトリの準備

1. 以下のリポジトリにアクセスする

   https://github.com/INOkp/sharewel-alert

2. 右上の **Fork** を押して、自分のアカウントにコピーする
3. Forkしたリポジトリの **Settings** → **Actions** → **General** を開く
4. **Workflow permissions** を **Read and write permissions** に変更して保存する

---

## 3. Secretの登録

ForkしたリポジトリにSlackの認証情報を登録します。

1. **Settings** → **Secrets and variables** → **Actions** を開く
2. **New repository secret** を押す
3. 以下のSecretをそれぞれ登録する

| Name | 値 | 必須 |
|------|-----|------|
| `SLACK_WEBHOOK_URL` | 手順1で控えたWebhook URL | はい |
| `SLACK_BOT_TOKEN` | 手順1で控えたBot Token | スレッド詳細を使う場合 |
| `SLACK_CHANNEL_ID` | 手順1で控えたチャンネルID | スレッド詳細を使う場合 |

> `SLACK_BOT_TOKEN` と `SLACK_CHANNEL_ID` はセットで登録してください。片方だけでは動きません。

---

## 4. 動作確認

### テスト通知を送る

1. リポジトリの **Actions** タブを開く
2. 左側の **ShareWel Alert** を選ぶ
3. **Run workflow** を押す
4. **Run mode** を `slack-test` に変更して実行
5. Slackにテストメッセージが届けば成功

### 本番と同じ形式で試す

1. 同じ手順で **Run workflow** を押す
2. **Run mode** を `simulate-new` に変更して実行
3. Slackに商品名・画像付きの通知が届くことを確認

### 本番運用を開始する

1. 同じ手順で **Run mode** を `check`（初期値）のまま実行
2. 初回は既存商品を記録するだけで、通知は送られません
3. 以降は30分ごとに自動実行され、新しい商品があればSlackに通知されます

---

## 通知のイメージ

**親メッセージ（Webhook）：**
```
📢新着商品が公開されました‼️

> 商品名
商品ページを開く
[商品画像]
```

**スレッド返信（Bot Token設定時）：**
```
詳細情報
> 商品名
商品ページを開く

出品者: ○○
掲載期限: 2026-07-31
場所: ○○キャンパス / ○○棟
品目: ○○ / 在庫: 1 / 状態: 良好

[追加画像]
```

---

## トラブルシューティング

| 症状 | 対処 |
|------|------|
| Actionsが動かない | ForkリポジトリのActionsタブで、ワークフローが有効になっているか確認 |
| Slackに通知が来ない | Secretの名前と値が正しいか確認。`slack-test` モードで疎通テスト |
| スレッド詳細が出ない | `SLACK_BOT_TOKEN` と `SLACK_CHANNEL_ID` の両方が登録されているか確認。Botがチャンネルに招待されているか確認 |
| 初回実行で通知が来ない | 正常動作です。初回は既存商品を記録するだけです |
