from playwright.sync_api import sync_playwright

# 你的真实 Chrome 用户数据目录
USER_DATA_DIR = r"C:\Users\Admin\AppData\Local\Google\Chrome\User Data"

# 你的 profile 名称
PROFILE = "Profile 1"

START_URL = "https://prenotami.esteri.it/Services"

def main():
    with sync_playwright() as p:
        context = p.chromium.launch_persistent_context(
            user_data_dir=USER_DATA_DIR,
            headless=False,
            args=[
                f"--profile-directory={PROFILE}"
            ]
        )

        page = context.new_page()
        page.goto(START_URL, timeout=90000)

        print("\n浏览器已使用你的真实 Chrome Profile 打开。")
        print("如果已经登录 Prenot@Mi，就可以直接关闭窗口。")
        input("确认页面正常后，按回车退出...")

        context.close()

if __name__ == "__main__":
    main()
