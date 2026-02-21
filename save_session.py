import os
import pathlib

from dotenv import load_dotenv
from playwright.sync_api import sync_playwright

load_dotenv()

# 使用项目内独立 profile，避免锁定你日常 Chrome 的用户目录
SESSION_DIR = pathlib.Path(os.getenv("SESSION_DIR", "session_profile")).resolve()
START_URL = os.getenv("START_URL", "https://prenotami.esteri.it/Services").strip()


def cleanup_stale_locks(profile_dir: pathlib.Path) -> None:
    """删除异常退出后遗留的 Chrome 锁文件，防止下次启动闪退。"""
    for name in ("SingletonLock", "SingletonCookie", "SingletonSocket"):
        p = profile_dir / name
        if p.exists():
            try:
                p.unlink()
            except OSError:
                pass


def main():
    SESSION_DIR.mkdir(parents=True, exist_ok=True)
    cleanup_stale_locks(SESSION_DIR)

    with sync_playwright() as p:
        context = p.chromium.launch_persistent_context(
            user_data_dir=str(SESSION_DIR),
            channel="chrome",
            headless=False,
            args=[
                "--disable-blink-features=AutomationControlled",
                "--start-maximized",
            ],
        )

        try:
            page = context.new_page()
            page.goto(START_URL, timeout=90000)

            print("\n浏览器已使用独立 session_profile 打开。")
            print("请完成 Prenot@Mi 登录，确认进入 Services 页面后回终端按回车。")
            input("按回车保存会话并退出... ")
        finally:
            context.close()


if __name__ == "__main__":
    main()
