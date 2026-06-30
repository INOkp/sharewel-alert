# ShareWel Alert 導入マニュアル

[ShareWel](https://sharewel.riise.u-tokyo.ac.jp) に新しい商品が出品されると、Slackに自動で通知するBotです。

GitHub Actions（GitHubの自動実行機能）を使うので、**サーバー不要・無料**で動きます。
30分ごとに自動チェックし、新着があればSlackに通知します。

### こんな通知が届きます

```
📢新着商品が公開されました‼️

> 椅子（キャスター付き）
商品ページを開く
[商品画像]
```

---

## 導入手順（15〜20分）

### ステップ1：Slackアプリを作る

通知を受け取るためのSlackアプリを作成します。

1. https://api.slack.com/apps を開く
2. **Create New App** → **From scratch** を選ぶ
3. アプリ名を入力（例：`ShareWel Alert`）、ワークスペースを選んで作成
4. 左メニューの **Incoming Webhooks** を開く
5. **Activate Incoming Webhooks** を **On** にする
6. 下の方にある **Add New Webhook to Workspace** を押す
7. 通知を送りたいチャンネルを選んで許可する
8. 表示される **Webhook URL** をコピーしておく（あとで使います）

### ステップ2：GitHubリポジトリをコピーする

1. https://github.com/INOkp/sharewel-alert を開く
2. 右上の **Fork** を押して、自分のアカウントにコピーする
3. コピーしたリポジトリで **Settings** → **Actions** → **General** を開く
4. **Workflow permissions** を **Read and write permissions** に変えて保存

### ステップ3：Webhook URLを登録する

コピーしたリポジトリにSlackのWebhook URLを登録します。

1. **Settings** → **Secrets and variables** → **Actions** を開く
2. **New repository secret** を押す
3. **Name** に `SLACK_WEBHOOK_URL` と入力
4. **Secret** にステップ1でコピーしたWebhook URLを貼り付ける
5. **Add secret** で保存

### ステップ4：動作確認

1. リポジトリの **Actions** タブを開く
2. 左側の **ShareWel Alert** を選ぶ
3. **Run workflow** → **Run mode** を `slack-test` にして実行
4. Slackにテストメッセージが届けば成功！

### ステップ5：本番開始

1. 同じ画面で **Run workflow** → **Run mode** は `check` のまま実行
2. 初回は既存の商品を記録するだけで、通知は送りません（正常です）
3. あとは30分ごとに自動でチェックが走り、新着があればSlackに届きます

**これで導入完了です。**

---

## （オプション）スレッドに詳細情報を表示する

追加の設定をすると、通知のスレッド（返信欄）に商品の詳細が自動投稿されます。
また、画像がSlackに直接アップロードされるため、時間が経っても画像が消えなくなります。

```
詳細情報
> 椅子（キャスター付き）
商品ページを開く

出品者: ○○研究室
掲載期限: 2026-07-31
場所: 本郷キャンパス / ○○棟
品目: 椅子 / 在庫: 1 / 状態: 良好

[追加画像]
```

### 追加の設定手順

1. ステップ1で作ったSlackアプリの設定画面に戻る
2. 左メニューの **OAuth & Permissions** を開く
3. **Bot Token Scopes** に `chat:write`、`files:write`、`channels:history` を追加する
4. ページ上部の **Install to Workspace** を押して再インストール
5. 表示される **Bot User OAuth Token**（`xoxb-...`で始まる文字列）をコピー
6. Slackで通知先チャンネルを開き、チャンネル名をクリック → **インテグレーション** → **アプリを追加する** で、作ったアプリを追加
7. チャンネル詳細の下部に表示される **チャンネルID**（`C`で始まる英数字）をコピー
8. GitHubリポジトリで、ステップ3と同じ手順で以下の2つを追加登録する

| Name | 値 |
|------|-----|
| `SLACK_BOT_TOKEN` | コピーしたBot Token |
| `SLACK_CHANNEL_ID` | コピーしたチャンネルID |

登録後、**Actions** → **Run workflow** → `simulate-new` で実行すると、スレッド付きの通知を確認できます。

---

## うまくいかないとき

| 症状 | 確認すること |
|------|-------------|
| Actionsが動かない | Actionsタブでワークフローが有効か確認（Forkした直後は無効のことがあります） |
| Slackに通知が来ない | `SLACK_WEBHOOK_URL` の名前と値が正しいか確認 → `slack-test` で再テスト |
| スレッド詳細が出ない | `SLACK_BOT_TOKEN` と `SLACK_CHANNEL_ID` の両方を登録したか確認。Botがチャンネルに招待されているか確認 |
| 初回で通知が来ない | 正常です。初回は既存商品の記録だけ行います |

---

## 更新履歴

- **2026-06-30** 画像をSlackに直接アップロードする方式に変更（リンク切れ対策）。URLプレビューを非表示に。Bot Tokenに `files:write` scopeが必要に
- **2026-06-30** 初回リリース
