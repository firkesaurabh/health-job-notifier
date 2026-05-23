#!/usr/bin/env python3
"""
Run this ONCE after creating your Telegram bot to find your CHAT_ID.

Steps:
  1. Message your bot in Telegram (just send "hi")
  2. Run:  python get_telegram_chat_id.py <YOUR_BOT_TOKEN>
"""
import sys
import requests

if len(sys.argv) < 2:
    print("Usage: python get_telegram_chat_id.py <BOT_TOKEN>")
    sys.exit(1)

token = sys.argv[1]
url   = f"https://api.telegram.org/bot{token}/getUpdates"

resp = requests.get(url, timeout=10)
data = resp.json()

if not data.get("ok"):
    print("Error:", data)
    sys.exit(1)

updates = data.get("result", [])
if not updates:
    print("No messages found. Send a message to your bot first, then re-run.")
    sys.exit(1)

for upd in updates:
    msg  = upd.get("message", {})
    chat = msg.get("chat", {})
    print(f"Chat ID : {chat.get('id')}")
    print(f"Name    : {chat.get('first_name', '')} {chat.get('last_name', '')}")
    print(f"Username: @{chat.get('username', 'N/A')}")
    print()
