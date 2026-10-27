# iframe勤怠チェック検証キット

TimePro-VGに接続せず、入れ子iframeから表データを読み取り、JSON設定でルールを切り替え、HTML結果を出す流れを確認するための小さな検証用プロジェクトです。サンプルの社員名・勤怠は架空です。

## 実行方法（Windows）

1. Pythonをインストール済みのPCで、このフォルダーを展開します。
2. フォルダー内でコマンドプロンプトを開き、初回だけ実行します。

   ```bat
   py -m pip install -r requirements.txt
   py -m playwright install chromium
   ```

3. `run_check.py` をダブルクリックするか、次を実行します。

   ```bat
   py run_check.py
   ```

`output` にHTMLレポートが作られ、ブラウザーで開きます。通常の運用ではローカル検証サイトをプロセス内の一時HTTPサーバーで配信し、Playwrightでアクセスします。TimePro向けの最終設計でローカルサーバーを置かない方針とは別に、これは検証用の画面を表示する仕組みです。

## 試せること

- `site/index.html` → `site/frames/outer.html` → `site/frames/inner.html` の2段iframe
- `config/check.json` でURL、フレームのセレクター、表、列、チェックルールを指定
- 退勤打刻漏れと、定時より前の残業開始を検出
- 結果を静的HTMLに出力

たとえば `frames` のセレクターを変更して実行すると、取得失敗として止まります。`rules` の `true` / `false` を変えると、判定内容を変えられます。画面要素や列構造が変わった場合は `check.json` だけでは対応できず、取得コードの修正が必要になる場合があります。

Python の処理の詳細は [docs/python-logic.md](docs/python-logic.md) を参照してください。

## exe化

本キットはまずPython上で動作を確かめる試作です。実行環境にPlaywrightとChromiumを用意してからPyInstallerでexe化します。Edge channelへの切替やブラウザープロファイルによるログイン保持は、この検証では扱いません。
