# 📦 Inventory QR System

QR-based asset tracking system with FastAPI and Telegram bot.

---

## 🚀 Features

- 🔍 Find asset by QR / inventory code
- 🤖 Telegram bot interface
- 🌐 Web view for asset details
- 📱 Telegram Mini App with QR scanner
- 🗄 Supabase database integration

---

## 🧩 Tech Stack

- FastAPI
- Supabase
- Telegram Bot API
- HTML (Jinja2 templates)

---

## 📦 Project Structure
asset_system/

│

├── app.py # FastAPI backend

├── bot.py # Telegram bot

├── templates/

│ └── asset.html # Web asset view

├── requirements.txt

---

## ⚙️ Setup (local)

1. Clone repo:
git clone https://github.com/YOUR_USERNAME/inventory-qr-system.git

cd inventory-qr-system

3. Install dependencies:
pip install -r requirements.txt

4. Run API:
uvicorn app:app --reload

5. Run bot:
python bot.py

---

## 🌐 API Endpoints

- `/asset/{asset_tag}` → JSON data
- `/view/{asset_tag}` → HTML page
- `/miniapp` → Telegram Web App

---

## 🔐 Environment Variables
SUPABASE_URL=your_url

SUPABASE_KEY=your_key

BOT_TOKEN=your_telegram_token

---

## 📱 Usage

1. Scan QR code (e.g. `HELP-UKR-0015`)
2. Bot retrieves asset
3. View details in Telegram or Web App

---

## 🛠 Future Improvements

- Asset status updates
- Scan history
- User roles
- Admin panel

---

## 👨‍💻 Author

Developed as an internal asset tracking system.
