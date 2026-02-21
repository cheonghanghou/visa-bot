import os
import time
import pathlib
import signal
import smtplib
import urllib.request
import urllib.parse
from datetime import datetime
from email.mime.text import MIMEText

from dotenv import load_dotenv
from playwright.sync_api import sync_playwright

load_dotenv()

BOSTON_URL = os.getenv("BOSTON_URL", "").strip()
NY_URL = os.getenv("NY_URL", "").strip()
CHECK_INTERVAL_SECONDS = int(os.getenv("CHECK_INTERVAL_SECONDS", "300"))
STATUS_REPORT_SECONDS = int(os.getenv("STATUS_REPORT_SECONDS", "1800"))
COOLDOWN_SECONDS = int(os.getenv("COOLDOWN_SECONDS", "600"))

SMTP_HOST = os.getenv("SMTP_HOST", "").strip()
SMTP_PORT = int(os.getenv("SMTP_PORT", "587"))
SMTP_USER = os.getenv("SMTP_USER", "").strip()
SMTP_PASS = os.getenv("SMTP_PASS", "").strip()
MAIL_TO = os.getenv("MAIL_TO", "").strip()

TG_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN", "").strip()
TG_CHAT_ID = os.getenv("TELEGRAM_CHAT_ID", "").strip()

SESSION_DIR = pathlib.Path(os.getenv("SESSION_DIR", "session_profile")).resolve()
ARTIFACT_DIR = pathlib.Path("artifacts")
ARTIFACT_DIR.mkdir(exist_ok=True)

NO_CALENDAR_PHRASES = [
    "Booking calendar not yet available",
    "calendar not yet available",
    "not yet available",
]


def now_ts():
    return datetime.now().strftime("%Y-%m-%d_%H-%M-%S")


def send_email(subject: str, body: str):
    if not (SMTP_HOST and SMTP_USER and SMTP_PASS and MAIL_TO):
        return
    msg = MIMEText(body, "plain", "utf-8")
    msg["Subject"] = subject
    msg["From"] = SMTP_USER
    msg["To"] = MAIL_TO
    with smtplib.SMTP(SMTP_HOST, SMTP_PORT) as s:
        s.starttls()
        s.login(SMTP_USER, SMTP_PASS)
        s.sendmail(SMTP_USER, [MAIL_TO], msg.as_string())


def send_telegram(text: str):
    if not (TG_TOKEN and TG_CHAT_ID):
        return
    url = f"https://api.telegram.org/bot{TG_TOKEN}/sendMessage"
    data = urllib.parse.urlencode({"chat_id": TG_CHAT_ID, "text": text}).encode()
    req = urllib.request.Request(url, data=data, method="POST")
    with urllib.request.urlopen(req, timeout=20):
        pass


def notify(subject: str, body: str):
    send_email(subject, body)
    send_telegram(f"{subject}\n{body}")


def save_artifacts(page, tag: str):
    ts = now_ts()
    png = ARTIFACT_DIR / f"{ts}_{tag}.png"
    html = ARTIFACT_DIR / f"{ts}_{tag}.html"
    page.screenshot(path=str(png), full_page=True)
    html.write_text(page.content(), encoding="utf-8")
    return str(png), str(html)


def visas_row_status_text(page) -> str:
    row = page.locator("table tbody tr").filter(has_text="VISAS").filter(has_text="Visas").first
    booking_cell = row.locator("td").nth(3)
    return booking_cell.inner_text().strip()


def is_visas_book_available(booking_text: str) -> bool:
    t = booking_text.lower()
    if any(p.lower() in t for p in NO_CALENDAR_PHRASES):
        return False
    return "book" in t


def check_one(page, name: str, url: str):
    page.goto(url, timeout=90000, wait_until="domcontentloaded")

    booking_text = ""
    try:
        booking_text = visas_row_status_text(page)
    except Exception:
        booking_text = page.inner_text("body")[:5000]

    available = is_visas_book_available(booking_text)
    return available, booking_text


def cleanup_stale_locks(profile_dir: pathlib.Path) -> None:
    for name in ("SingletonLock", "SingletonCookie", "SingletonSocket"):
        p = profile_dir / name
        if p.exists():
            try:
                p.unlink()
            except OSError:
                pass


def main():
    if not (BOSTON_URL and NY_URL):
        raise SystemExit("请先在 .env 里填写 BOSTON_URL 和 NY_URL（等号=）")

    if not SESSION_DIR.exists():
        raise SystemExit("未找到 SESSION_DIR，请先运行 python save_session.py 完成首次登录。")

    cleanup_stale_locks(SESSION_DIR)

    stop = {"value": False}

    def _handle_stop(_sig, _frame):
        stop["value"] = True

    signal.signal(signal.SIGINT, _handle_stop)
    signal.signal(signal.SIGTERM, _handle_stop)

    last_alert_time = 0.0
    last_status_time = 0.0

    with sync_playwright() as p:
        context = p.chromium.launch_persistent_context(
            user_data_dir=str(SESSION_DIR),
            channel="chrome",
            headless=True,
            args=[
                "--disable-blink-features=AutomationControlled",
                "--window-size=1400,1100",
            ],
        )
        context.set_extra_http_headers({
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
            "(KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36"
        })

        page = context.new_page()

        try:
            while not stop["value"]:
                started = time.time()
                stamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                print(f"\n[{stamp}] 检查中...")

                triggered = []
                statuses = []

                for name, url in [("BOSTON", BOSTON_URL), ("NEWYORK", NY_URL)]:
                    try:
                        ok, booking_text = check_one(page, name, url)
                        short_text = booking_text[:160].replace("\n", " ")
                        statuses.append(f"- {name}: {'疑似可BOOK' if ok else '未开放'} | {short_text}")
                        print(statuses[-1])
                        if ok:
                            png, html = save_artifacts(page, name)
                            triggered.append((name, url, png, html))
                    except Exception as e:
                        err = f"- {name}: 检查失败: {e}"
                        statuses.append(err)
                        print(err)

                now = time.time()

                if triggered and (now - last_alert_time >= COOLDOWN_SECONDS):
                    lines = ["检测到 VISAS 可能开放 BOOK（请立刻手动确认并预约）："]
                    for name, url, png, html in triggered:
                        lines.append(f"- {name}: {url}")
                        lines.append(f"  截图: {png}")
                        lines.append(f"  HTML: {html}")
                    msg = "\n".join(lines)
                    try:
                        notify("Prenot@Mi VISA BOOK Alert", msg)
                        print("[已通知] BOOK 告警已发送。")
                    except Exception as e:
                        print(f"[错误] 告警发送失败: {e}")
                    last_alert_time = now

                if now - last_status_time >= STATUS_REPORT_SECONDS:
                    report = "\n".join([
                        f"时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}",
                        "监控仍在运行，最新状态如下:",
                        *statuses,
                    ])
                    try:
                        notify("Prenot@Mi Slot Monitor Heartbeat", report)
                        print("[已通知] 心跳进度已发送。")
                    except Exception as e:
                        print(f"[错误] 心跳发送失败: {e}")
                    last_status_time = now

                elapsed = time.time() - started
                sleep_for = max(5, CHECK_INTERVAL_SECONDS - int(elapsed))
                print(f"下次检查将在 {sleep_for} 秒后。")
                for _ in range(sleep_for):
                    if stop["value"]:
                        break
                    time.sleep(1)
        finally:
            context.close()


if __name__ == "__main__":
    main()
