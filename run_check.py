from __future__ import annotations

import html
import json
import threading
import webbrowser
from datetime import datetime
from functools import partial
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

from playwright.sync_api import sync_playwright

# 実行時のカレントディレクトリではなく、このファイルを基準に各パスを決める。
ROOT = Path(__file__).resolve().parent
SITE = ROOT / "site"
CONFIG = ROOT / "config" / "check.json"
OUTPUT = ROOT / "output"


def load_config() -> dict:
    # 設定値の型やセレクターの内容ではなく、必須キーの有無を確認する。
    config = json.loads(CONFIG.read_text(encoding="utf-8"))
    required = ("site_url", "frames", "table", "rows", "columns", "rules")
    missing = [key for key in required if key not in config]
    if missing:
        raise ValueError(f"設定に必須項目がありません: {', '.join(missing)}")
    return config


def collect(config: dict) -> list[dict[str, str]]:
    # 検証用サイトをローカルに配信する。実際の TimePro には接続しない。
    handler = partial(SimpleHTTPRequestHandler, directory=str(SITE))
    server = ThreadingHTTPServer(("127.0.0.1", 8765), handler)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    try:
        with sync_playwright() as p:
            # 表示画面を出さずに Chromium を起動し、設定されたページを開く。
            browser = p.chromium.launch(headless=True)
            page = browser.new_page()
            page.goto(config["site_url"], wait_until="domcontentloaded")
            frame = page
            # 外側から内側への順に iframe をたどる。
            # 現在の設定では #outer-frame → #attendance-frame の2段。
            for selector in config["frames"]:
                frame = frame.frame_locator(selector)
            # 最後にたどり着いた iframe 内の表が表示されるまで待つ。
            table = frame.locator(config["table"])
            table.wait_for(state="visible", timeout=10000)
            rows = table.locator(config["rows"]).all()
            records = []
            for row in rows:
                # 各 td の前後の空白を除去し、設定の列名と位置で対応付ける。
                # zip は列名とセルの数が異なると、余った側を切り捨てる。
                cells = row.locator("td").all_text_contents()
                values = [cell.strip() for cell in cells]
                record = dict(zip(config["columns"], values))
                records.append(record)
            browser.close()
            return records
    finally:
        # 取得に失敗した場合もローカルサーバーを停止する。
        server.shutdown()
        server.server_close()


def check(records: list[dict[str, str]], rules: dict) -> list[dict[str, str]]:
    findings = []
    for record in records:
        # 有効なルールに該当した分だけ結果を追加する。
        # 1行が両方のルールに該当する場合は2件になる。
        if rules.get("missing_clock_out") and not record.get("clock_out"):
            findings.append({**record, "status": "要確認", "reason": "退勤打刻がありません"})

        overtime_start = record.get("overtime_start", "")
        scheduled_end = record.get("scheduled_end", "")
        # 文字列の大小比較なので、ゼロ埋めした HH:MM 形式を前提とする。
        if (
            rules.get("overtime_must_not_start_before_scheduled_end")
            and overtime_start
            and scheduled_end
            and overtime_start < scheduled_end
        ):
            reason = f"残業開始 {overtime_start} が定時 {scheduled_end} より前です"
            findings.append({**record, "status": "要確認", "reason": reason})
    return findings


def write_report(records: list[dict[str, str]], findings: list[dict[str, str]]) -> Path:
    OUTPUT.mkdir(exist_ok=True)
    # 秒単位のファイル名。同じ秒に再実行すると既存ファイルを上書きする。
    stamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    path = OUTPUT / f"{stamp}.html"
    # 表の値は HTML として解釈されないようエスケープする。
    columns = ("employee", "date", "status", "reason")
    report_rows = []
    for finding in findings:
        cells = [f"<td>{html.escape(finding.get(column, ''))}</td>" for column in columns]
        report_rows.append("<tr>" + "".join(cells) + "</tr>")
    body = "\n".join(report_rows) or '<tr><td colspan="4">要確認事項はありません</td></tr>'
    doc = f"""<!doctype html><meta charset="utf-8"><title>検証結果</title>
<style>body{{font:16px sans-serif;margin:2rem;color:#18212b}}table{{border-collapse:collapse}}td,th{{border:1px solid #ccd4dd;padding:.6rem}}th{{background:#edf2f7}}</style>
<h1>勤怠チェック検証結果</h1><p>取得件数: {len(records)}　要確認: {len(findings)}</p>
<table><thead><tr><th>社員</th><th>日付</th><th>判定</th><th>内容</th></tr></thead><tbody>{body}</tbody></table>"""
    path.write_text(doc, encoding="utf-8")
    return path


def main() -> None:
    try:
        # 設定 → 取得 → 判定 → 出力の順に処理する。
        config = load_config()
        records = collect(config)
        findings = check(records, config["rules"])
        report = write_report(records, findings)
        print(f"取得: {len(records)}件 / 要確認: {len(findings)}件")
        print(f"結果: {report}")
        webbrowser.open(report.resolve().as_uri())
    except Exception as exc:
        # エラーを表示した後、呼び出し元にも失敗を伝える。
        print(f"処理を中断しました: {exc}")
        raise


if __name__ == "__main__":
    main()
