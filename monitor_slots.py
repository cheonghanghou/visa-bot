import os
import time
import pathlib
import smtplib
import urllib.request
import urllib.parse
from datetime import datetime
from email.mime.text import MIMEText

from dotenv import load_dotenv
from playwright.sync_api import sync_playwright

from save_session import PROFILE

# ========= 你的真实 Chrome Profile（已确认） =========
USER_DATA_DIR = r"C:\Users\Admin\AppData\Local\Google\Chrome\User Data"
PROFILE_DIR = "Profile 1"  # 注意这里必须是 Profile 1或者Profile 2，不是路径，跑别的会直接锁死该用户（一点就闪退）

load_dotenv()

BOSTON_URL = os.getenv("BOSTON_URL", "").strip()
NY_URL = os.getenv("NY_URL", "").strip()
CHECK_INTERVAL_SECONDS = int(os.getenv("CHECK_INTERVAL_SECONDS", "900"))
COOLDOWN_SECONDS = int(os.getenv("COOLDOWN_SECONDS", "3600"))

SMTP_HOST = os.getenv("SMTP_HOST", "").strip()
SMTP_PORT = int(os.getenv("SMTP_PORT", "587"))
SMTP_USER = os.getenv("SMTP_USER", "").strip()
SMTP_PASS = os.getenv("SMTP_PASS", "").strip()
MAIL_TO = os.getenv("MAIL_TO", "").strip()

TG_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN", "").strip()
TG_CHAT_ID = os.getenv("TELEGRAM_CHAT_ID", "").strip()

ARTIFACT_DIR = pathlib.Path("artifacts")
ARTIFACT_DIR.mkdir(exist_ok=True)

# 目标：监测 “VISAS / Visas” 那一行状态是否从
# “Booking calendar not yet available” 变成可点击 BOOK
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

def save_artifacts(page, tag: str):
    ts = now_ts()
    png = ARTIFACT_DIR / f"{ts}_{tag}.png"
    html = ARTIFACT_DIR / f"{ts}_{tag}.html"
    page.screenshot(path=str(png), full_page=True)
    html.write_text(page.content(), encoding="utf-8")
    return str(png), str(html)

def visas_row_status_text(page) -> str:
    """
    抓取 Services 表格里 'VISAS' + 'Visas' 那行的 Booking 列文本
    如果页面结构变化，可能需要调整选择器。
    """
    # 先定位到表格行：包含 'VISAS' 且 service 为 'Visas'
    row = page.locator("table tbody tr").filter(has_text="VISAS").filter(has_text="Visas").first
    booking_cell = row.locator("td").nth(3)  # Booking 列（第4列，0-index）
    return booking_cell.inner_text().strip()

def is_visas_book_available(booking_text: str) -> bool:
    t = booking_text.lower()
    # 如果还包含“not yet available”类文本 -> 没开放
    if any(p.lower() in t for p in NO_CALENDAR_PHRASES):
        return False
    # 如果出现 BOOK 或类似（可能是按钮文本）
    return "book" in t

def check_one(page, name: str, url: str):
    page.goto(url, timeout=90000, wait_until="domcontentloaded")

    booking_text = ""
    try:
        booking_text = visas_row_status_text(page)
    except Exception:
        # fallback：结构变化时至少保存整页文本用于排查
        booking_text = page.inner_text("body")[:5000]

    available = is_visas_book_available(booking_text)
    return available, booking_text

def main():
    if not (BOSTON_URL and NY_URL):
        raise SystemExit("请先在 .env 里填写 BOSTON_URL 和 NY_URL（等号=）")

    print("重要：运行监测前请关闭所有 Chrome（同一 Profile 不能同时占用）。")

    last_alert_time = 0

    with sync_playwright() as p:
        # 用真实 Chrome profile，避免被 Radware 识别
        context = p.chromium.launch_persistent_context(
            user_data_dir=USER_DATA_DIR,
            headless=False,  # 想看浏览器就改 False
            args=[
                f"--profile-directory={PROFILE}",
                "--disable-blink-features=AutomationControlled",
                "--start-maximized",
            ]
        )

        context.set_extra_http_headers({
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36"
        })

        page = context.new_page()

        while True:
            started = time.time()
            stamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            print(f"\n[{stamp}] 检查中...")

            triggered = []
            for name, url in [("BOSTON", BOSTON_URL), ("NEWYORK", NY_URL)]:
                try:
                    ok, booking_text = check_one(page, name, url)
                    print(f" - {name}: {'疑似开放BOOK' if ok else '未开放'} | Booking字段: {booking_text[:120]}")
                    if ok:
                        png, html = save_artifacts(page, name)
                        triggered.append((name, url, png, html))
                except Exception as e:
                    print(f" - {name}: 检查失败: {e}")

            now = time.time()
            if triggered and (now - last_alert_time >= COOLDOWN_SECONDS):
                lines = ["检测到 VISAS 可能开放 BOOK（请立刻手动确认并预约）："]
                for name, url, png, html in triggered:
                    lines.append(f"- {name}: {url}")
                    lines.append(f"  截图: {png}")
                    lines.append(f"  HTML: {html}")
                msg = "\n".join(lines)

                try:
                    send_email("Prenot@Mi VISA BOOK Alert", msg)
                except Exception as e:
                    print(f"[错误] 邮件发送失败: {e}")

                try:
                    send_telegram(msg)
                except Exception as e:
                    print(f"[错误] Telegram 发送失败: {e}")

                last_alert_time = now
                print("[已通知] 已发送 Email/Telegram，并保存证据。")

            elapsed = time.time() - started
            sleep_for = max(5, CHECK_INTERVAL_SECONDS - int(elapsed))
            print(f"下次检查将在 {sleep_for} 秒后。")
            time.sleep(sleep_for)

        # context.close()  # 永久循环一般不走到这

if __name__ == "__main__":
    main()
