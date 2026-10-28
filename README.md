# 🦾 mraz0tix Interactive Portfolio Bot

An advanced, asynchronous Telegram bot built with **Aiogram 3** that serves as an interactive portfolio for a Python Developer & Linux Systems Administrator. It features a built-in anonymous feedback/bridge system, a local database tracker, and WebApp integration.

## 🚀 Features

* **Interactive Menus:** Seamless navigation through projects, system setups, and contact forms using Inline Keyboards.
* **Project Showcase:** Highlights open-source system utilities (`SysPulse`, `FastSysPulse`, `NetPulse`) with exact codebase details and features.
* **Linux Rice Spec:** Displays system customization profiles (Arch Linux, GNOME, Kitty terminal, custom themes).
* **Telegram WebApp Integration:** Users can open your portfolio website directly inside Telegram as a WebApp or open it in a browser.
* **Anonymous Bridge (Contact System):** Users can send messages to the bot, which are safely forwarded to the creator. The creator can reply to the user directly by replying to the bot's log message, keeping the creator's username entirely private.
* **User Database Tracking:** Uses SQLite3 to automatically log and welcome unique users who interact with the bot.

## 🛠️ Stack & Technologies

* **Language:** Python 3.10+
* **Framework:** Aiogram 3.x (Asynchronous Telegram Bot API)
* **Database:** SQLite3
* **Environment Management:** OS-level Environment Variables (for secure token storage)

## 📂 Project Structure

```text
├── main.py             # Main application script containing handlers and logic
└── users.db            # SQLite database for storing registered users (auto-generated)
```

## ⚙️ Installation & Setup

### 1. Clone the Repository
```bash
git clone https://github.com/mraz0tix-code/tg-portfolio-bot/tree/main
cd ~/tg-portfolio-bot
```

### 2. Install Dependencies
Make sure you have `aiogram` installed:
```bash
pip install aiogram
```

### 3. Configure Environment Variables
For security reasons, **never hardcode your Bot Token or Telegram ID** inside the source code. Set them in your environment:

**On Linux/macOS:**
```bash
export BOT_TOKEN="YOUR_ACTUAL_BOT_TOKEN"
export CREATOR_ID="YOUR_TELEGRAM_USER_ID"
```

**On Windows (Command Prompt):**
```cmd
set BOT_TOKEN=YOUR_ACTUAL_BOT_TOKEN
set CREATOR_ID=YOUR_TELEGRAM_USER_ID
```

**On Windows (PowerShell):**
```powershell
$env:BOT_TOKEN="YOUR_ACTUAL_BOT_TOKEN"
$env:CREATOR_ID="YOUR_TELEGRAM_USER_ID"
```

*Note: Update the `API_TOKEN` fallback line in `main.py` to use `os.getenv("BOT_TOKEN")` to fully secure your environment.*

## 🛫 Running the Bot

Once the environment variables are set, simply run the Python script:
```bash
python main.py
```

Upon successful initialization, you will see the following terminal output:
```text
[+] Portfolio bot successfully initialized. Ready for global production!
```

## 📩 Feedback System Workflow

1. **User Side:** A user navigates to the "Contact Me" section, types a message, and sends it.
2. **Admin Side:** The bot captures the message and forwards it to the administrator defined in `CREATOR_ID` along with a unique log header containing the user's ID.
3. **Replying:** The administrator simply uses Telegram's native **Reply** function on that log message. The bot extracts the target User ID and securely delivers the response.

## 📄 License

This project is open-source. Feel free to fork, modify, and use it for your own personal portfolios.
