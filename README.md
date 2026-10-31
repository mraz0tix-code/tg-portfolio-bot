# 🤖 System Management & Portfolio Telegram Bots

This repository contains two independent Python-based Telegram bots designed for server security infrastructure monitoring (SSH/auth logs analytics) and interactive developer portfolio hosting.

---

## 📦 Component Overview

### 1. 🚨 Login Alert Bot (`bot.py`)
A real-time security daemon that continuously monitors system authentication logs (`journalctl` or `/var/log/auth.log`). It parses authorization events using regular expressions and sends enriched security alerts to your private Telegram chat.

*   **Auth Tracking:** Monitors successful/failed SSH logins, max auth attempts exceeded, preauth connections dropped, port scans, and `sudo`/`su` authentication failures.
*   **Threat Intelligence & GeoIP:** Enriches incoming IP metadata using `ip-api.com` to report Country, City, ISP, Autonomous System (AS), and Reverse DNS.
*   **Security Risk Profiling:** Automatically flags proxy/VPN/Tor exits, datacenter/hosting subnets, and mobile networks.
*   **Brute-Force Mitigation:** Implements a sliding-window counter to detect brute-force waves. Throttles notifications using alert milestones (1st, 5th, 10th, 25th... attempt) to avoid spamming the user.
*   **Geolocation Pins:** Dispatches native Telegram map pins (`sendLocation`) on successful handshakes or heavy brute-force alerts.

### 2. 💼 Interactive Portfolio Bot (`portfolio.py`)
An asynchronous high-concurrency Telegram bot built on top of **aiogram 3.x** that acts as an interactive resume and bridge for user feedback.

*   **Fluid Inline UX:** Complete navigation menu built entirely on structural inline keyboards.
*   **Persistent User Logging:** Integrates a local `SQLite` backend to register users and track distinct profile visits.
*   **Project Showcase:** Displays summaries of technical open-source scripts (SysPulse, FastSysPulse, NetPulse) and custom Unix desktop desktop configurations (Arch Linux rice).
*   **Telegram WebApp Support:** Supports launching immersive integrated applications via WebApp interfaces right within the chat screen.
*   **Anonymous Traffic Routing:** Features a secure reverse-proxy feedback tunnel. Visitors can send messages, and the creator can respond using the Telegram `Reply` function directly without exposing their personal account identity.

---

## ⚡ Technical Stack
*   **Core:** Python 3.9+
*   **Framework:** Aiogram 3.x, Asyncio, SQLite3
*   **Networking/Monitoring:** Requests, Subprocess (journalctl piping), Socket API, Threading

---

## 🚀 Installation & Setup Guide

### 📋 Prerequisites
Ensure you have Python 3.9 or higher installed on your target machine. For the **Login Alert Bot**, you must have `root` privileges or be a member of the `adm` / `systemd-journal` groups to read the log streams.

### 1. Clone the Repository
```bash
git clone https://github.com
cd YOUR_REPOSITORY
```

### 2. Install Dependencies
Install all required external modules via `pip`:
```bash
pip install requests aiogram
```

### 3. Environment Configuration
Create a `.env` configuration file in the root root directory of the application:
```bash
touch .env
```

Open the `.env` file and populate it with your environment-specific credentials:
```ini
# --- Global Telegram Setup ---
YOUR_CHAT_ID=your_personal_telegram_chat_id
LOG_SOURCE=journal

# --- Optional Security Rules (Login Alert Bot) ---
IGNORE_IPS=127.0.0.1,192.168.1.10
BRUTE_THRESHOLD=5
BRUTE_WINDOW=600
SEND_LOCATION_PIN=1
NOTIFY_PRIVATE=1
LOG_FILE=/var/log/auth.log
```
> ⚠️ **Important Security Note:** Open `bot.py` and `portfolio.py` to ensure your Bot API tokens (`TOKEN` / `API_TOKEN`) and Creator IDs (`ID_Creator`) match your Telegram parameters.

---

## 🛠️ Execution & Deployment

### Running the Login Alert Bot (`bot.py`)
To test the log parsing engines locally without blasting notifications to active API endpoints, run the script with the testing flag:
```bash
python3 bot.py --test
```

To deploy the production listener daemon (requires privileges to read security streams):
```bash
sudo python3 bot.py
```

### Running the Portfolio Bot (`portfolio.py`)
To execute the asynchronous interactive bot portfolio pipeline:
```bash
python3 portfolio.py
```

### Production Daemonization (Optional)
To ensure both scripts execute reliably long-term in the background, you can wrap them as standard `systemd` unit services.
