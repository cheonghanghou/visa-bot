# Prenot@Mi Visa Slot Monitor (Boston + New York)

Local monitoring tool for checking Italian visa appointment availability on Prenot@Mi and notifying you when the **VISAS** service becomes bookable.

## What it does
- Opens Prenot@Mi Services page (Boston + New York)
- Reads the **VISAS** row "Booking" status
- If it changes to a clickable **BOOK** state → triggers notification and saves evidence (HTML/PNG)

## Requirements
- Windows / macOS
- Python 3.9+
- Google Chrome installed
- A Prenot@Mi account (you will login once via a real browser profile)

---

## Quick Start (one-time setup)

### 1) Clone
```bash
git clone https://github.com/cheonghanghou/visa-bot.git
cd visa-bot
```

### 2) Create & activate venv (recommended)
#### Windows:
```bash
python -m venv venv
venv\Scripts\activate
```

#### macOS/Linux:
```bash
python3 -m venv venv
source venv/bin/activate
```

### 3) Install dependencies
```bash
pip install -r requirements.txt
python -m playwright install
```

### 4) Create .env
```bash
Create a file named .env in the project root (simply use .env.example):
BOSTON_URL=https://prenotami.esteri.it/Services
NY_URL=https://prenotami.esteri.it/Services
CHECK_INTERVAL_SECONDS=900

SMTP_HOST=smtp.gmail.com
SMTP_PORT=587
SMTP_USER=your_email@gmail.com
SMTP_PASS=your_gmail_app_password
MAIL_TO=your_email@gmail.com
```

### First-time login (save session)
```bash
python save_session.py
```
A Chrome window will open. 
Notice that this might not work, unnecessary to do this, you can skip this and go straight to the monitor_slots.py
1. Login to Prenot@Mi
2. Ensure you can see the Services page
3. Close the browser window
4. Return to terminal and press Enter

### Run the monitor
Before running: close any Chrome instances using the same profile.
```bash
python monitor_slots.py
```
The script checks every CHECK_INTERVAL_SECONDS and alerts when VISAS becomes bookable.

### Notes
This project uses Playwright (real browser automation).
Website anti-bot protections may temporarily restrict access if you check too aggressively.
Recommended interval: 10–20 minutes.

### Disclaimer
Personal use only.