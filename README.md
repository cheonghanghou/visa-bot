# Prenot@Mi Visa Slot Monitor (Boston + New York)

用于后台监测 Prenot@Mi 的签证预约状态：
- 默认每 **5 分钟**检查一次
- 每 **30 分钟**发送一次运行进度（Heartbeat）
- 一旦检测到 `VISAS` 出现 `BOOK`，立即发送告警

## 这版重点改进
- 使用项目内独立 `session_profile/`，不再占用你日常 Chrome 的真实 Profile。
- 启动前自动清理异常退出留下的 Chrome 锁文件（`Singleton*`），降低闪退/锁死概率。
- 监控程序支持 `Ctrl+C` / `SIGTERM` 优雅退出，退出时会关闭浏览器上下文，减少 profile 被锁住问题。

## Requirements
- Python 3.9+
- Google Chrome
- Prenot@Mi 账号

## 安装
```bash
pip install -r requirements.txt
python -m playwright install chrome
```

## 配置 `.env`
```dotenv
BOSTON_URL=https://prenotami.esteri.it/Services
NY_URL=https://prenotami.esteri.it/Services

# 每5分钟检查一次
CHECK_INTERVAL_SECONDS=300
# 每30分钟发送进度
STATUS_REPORT_SECONDS=1800

# BOOK告警最短间隔（避免连续轰炸）
COOLDOWN_SECONDS=600

SMTP_HOST=smtp.gmail.com
SMTP_PORT=587
SMTP_USER=your_email@gmail.com
SMTP_PASS=your_gmail_app_password
MAIL_TO=your_email@gmail.com

# 可选：Telegram
TELEGRAM_BOT_TOKEN=
TELEGRAM_CHAT_ID=

# 可选：会话目录（默认 session_profile）
SESSION_DIR=session_profile
```

## 首次登录（仅一次）
```bash
python save_session.py
```
完成登录后回终端按回车，登录状态会保存在 `session_profile/`。

## 启动监控
```bash
python monitor_slots.py
```

## 注意
- 不要并行启动多个监控实例。
- 若系统异常关机，下次启动会自动尝试清理 Chrome stale lock 文件。
