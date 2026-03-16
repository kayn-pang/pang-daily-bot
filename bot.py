#!/usr/bin/env python3
"""
Pang's Daily Assistant - Keyword-triggered Telegram Bot
Commands: /eventday /eventtmr /eventweek /eventnextweek /help
"""

import os
import json
import time
import requests
from datetime import datetime, timedelta
from zoneinfo import ZoneInfo

from google.oauth2 import service_account
from googleapiclient.discovery import build

SCOPES = ["https://www.googleapis.com/auth/calendar.readonly"]

# ── Configuration ───────────────────────────────────────────────────────────────
TELEGRAM_TOKEN  = "8619088376:AAH2uEBm-TuAglS1XBrUvGMvo8q0g9YLP_Y"
ALLOWED_CHAT_ID = 1527866122
TELEGRAM_API    = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}"
POLL_INTERVAL   = 2
TZ              = ZoneInfo("Asia/Kuala_Lumpur")

BOT_DIR    = os.path.dirname(os.path.abspath(__file__))
STATE_FILE = os.path.join(BOT_DIR, "bot_state.json")
SERVICE_ACCOUNT_FILE = os.path.join(BOT_DIR, "service_account.json")

# On cloud (Railway), load service account from env var if file doesn't exist
if not os.path.exists(SERVICE_ACCOUNT_FILE):
    _sa_json = os.environ.get("GOOGLE_SERVICE_ACCOUNT_JSON")
    if _sa_json:
        with open(SERVICE_ACCOUNT_FILE, "w") as _f:
            _f.write(_sa_json)

# All calendar IDs to fetch from
CALENDAR_IDS = [
    "elishapang28@gmail.com",
    "3c6ctp4hem04235omo0fc05gs8@group.calendar.google.com",
    "d6dc543925a7bfd25d2b811f6b6f5f5b53859e252341dbc057e587cfdb409ad8@group.calendar.google.com",
    "0ephoh8cggr9pglevhtdk5t2jk@group.calendar.google.com",
]

CALENDAR_NAMES = {
    "elishapang28@gmail.com":                                                                        "Primary",
    "3c6ctp4hem04235omo0fc05gs8@group.calendar.google.com":                                         "Focus Flow",
    "d6dc543925a7bfd25d2b811f6b6f5f5b53859e252341dbc057e587cfdb409ad8@group.calendar.google.com":  "Outreach",
    "0ephoh8cggr9pglevhtdk5t2jk@group.calendar.google.com":                                         "Workshop",
}

# ── Google Calendar ─────────────────────────────────────────────────────────────
def get_calendar_service():
    creds = service_account.Credentials.from_service_account_file(
        SERVICE_ACCOUNT_FILE, scopes=SCOPES
    )
    return build("calendar", "v3", credentials=creds, cache_discovery=False)

def fetch_events(time_min: datetime, time_max: datetime):
    service = get_calendar_service()
    if not service:
        return None  # Not authorised yet

    all_events = []
    tmin = time_min.isoformat()
    tmax = time_max.isoformat()

    for cal_id in CALENDAR_IDS:
        try:
            result = service.events().list(
                calendarId=cal_id,
                timeMin=tmin,
                timeMax=tmax,
                singleEvents=True,
                orderBy="startTime"
            ).execute()
            for ev in result.get("items", []):
                ev["_calendar"] = CALENDAR_NAMES.get(cal_id, cal_id)
                all_events.append(ev)
        except Exception:
            pass

    # Sort by start time
    def sort_key(e):
        start = e.get("start", {})
        return start.get("dateTime", start.get("date", ""))

    all_events.sort(key=sort_key)
    return all_events

def format_event(ev):
    start = ev.get("start", {})
    dt = start.get("dateTime")
    if dt:
        t = datetime.fromisoformat(dt).astimezone(TZ).strftime("%I:%M %p")
    else:
        t = "All day"
    title = ev.get("summary", "(No title)")
    return f"• {t} — {title}"

def format_events_for_day(events, date: datetime):
    day_events = []
    for ev in events:
        start = ev.get("start", {})
        dt_str = start.get("dateTime") or start.get("date", "")
        if dt_str:
            ev_date = datetime.fromisoformat(dt_str).date() if "T" in dt_str else datetime.fromisoformat(dt_str).date()
            if ev_date == date.date():
                day_events.append(ev)
    return day_events

# ── Command handlers ────────────────────────────────────────────────────────────
def cmd_today():
    now = datetime.now(TZ)
    tmin = now.replace(hour=0, minute=0, second=0, microsecond=0)
    tmax = now.replace(hour=23, minute=59, second=59, microsecond=0)
    events = fetch_events(tmin, tmax)

    if events is None:
        return "⚠️ Google Calendar not connected yet. Run the setup first."

    label = now.strftime("%A, %d %b %Y")
    if not events:
        return f"📅 *{label}*\n\nNo events today 🎉"

    lines = [f"📅 *{label}*\n"]
    for ev in events:
        lines.append(format_event(ev))
    lines.append(f"\n📊 {len(events)} event(s) today")
    return "\n".join(lines)

def cmd_tomorrow():
    now   = datetime.now(TZ)
    tmr   = now + timedelta(days=1)
    tmin  = tmr.replace(hour=0, minute=0, second=0, microsecond=0)
    tmax  = tmr.replace(hour=23, minute=59, second=59, microsecond=0)
    events = fetch_events(tmin, tmax)

    if events is None:
        return "⚠️ Google Calendar not connected yet. Run the setup first."

    label = tmr.strftime("%A, %d %b %Y")
    if not events:
        return f"📅 *{label}*\n\nNothing tomorrow 🎉"

    lines = [f"📅 *Tomorrow — {label}*\n"]
    for ev in events:
        lines.append(format_event(ev))
    lines.append(f"\n📊 {len(events)} event(s)")
    return "\n".join(lines)

def cmd_this_week():
    now  = datetime.now(TZ)
    # Monday of this week
    mon  = now - timedelta(days=now.weekday())
    tmin = mon.replace(hour=0, minute=0, second=0, microsecond=0)
    tmax = (mon + timedelta(days=6)).replace(hour=23, minute=59, second=59)
    events = fetch_events(tmin, tmax)

    if events is None:
        return "⚠️ Google Calendar not connected yet. Run the setup first."

    week_label = f"{mon.strftime('%d %b')} – {(mon + timedelta(days=6)).strftime('%d %b %Y')}"
    lines = [f"🗓 *This Week — {week_label}*\n"]

    total = 0
    for i in range(7):
        day = mon + timedelta(days=i)
        day_events = [ev for ev in events
                      if (lambda s: s.get("dateTime", s.get("date",""))[:10] == day.strftime("%Y-%m-%d"))(ev.get("start",{}))]
        day_label = day.strftime("%a %d %b")
        if day_events:
            lines.append(f"\n*{day_label}:*")
            for ev in day_events:
                lines.append(format_event(ev))
            total += len(day_events)
        else:
            lines.append(f"\n*{day_label}:* Nothing")

    lines.append(f"\n📊 {total} event(s) this week")
    return "\n".join(lines)

def cmd_next_week():
    now  = datetime.now(TZ)
    mon  = now - timedelta(days=now.weekday()) + timedelta(weeks=1)
    tmin = mon.replace(hour=0, minute=0, second=0, microsecond=0)
    tmax = (mon + timedelta(days=6)).replace(hour=23, minute=59, second=59)
    events = fetch_events(tmin, tmax)

    if events is None:
        return "⚠️ Google Calendar not connected yet. Run the setup first."

    week_label = f"{mon.strftime('%d %b')} – {(mon + timedelta(days=6)).strftime('%d %b %Y')}"
    lines = [f"🗓 *Next Week — {week_label}*\n"]

    total = 0
    for i in range(7):
        day = mon + timedelta(days=i)
        day_events = [ev for ev in events
                      if (lambda s: s.get("dateTime", s.get("date",""))[:10] == day.strftime("%Y-%m-%d"))(ev.get("start",{}))]
        day_label = day.strftime("%a %d %b")
        if day_events:
            lines.append(f"\n*{day_label}:*")
            for ev in day_events:
                lines.append(format_event(ev))
            total += len(day_events)
        else:
            lines.append(f"\n*{day_label}:* Nothing")

    lines.append(f"\n📊 {total} event(s) next week")
    return "\n".join(lines)

def cmd_help():
    return (
        "👋 *Pang's Daily Assistant*\n\n"
        "Commands:\n"
        "• /eventday — today's events\n"
        "• /eventtmr — tomorrow's events\n"
        "• /eventweek — this week\n"
        "• /eventnextweek — next week\n"
        "• /help — show this menu"
    )

COMMANDS = {
    "/eventday":      cmd_today,
    "/today":         cmd_today,
    "/eventtmr":      cmd_tomorrow,
    "/tmr":           cmd_tomorrow,
    "/eventweek":     cmd_this_week,
    "/week":          cmd_this_week,
    "/eventnextweek": cmd_next_week,
    "/nextweek":      cmd_next_week,
    "/help":          cmd_help,
    "/start":         cmd_help,
}

# ── Telegram helpers ────────────────────────────────────────────────────────────
def get_updates(offset=0):
    try:
        resp = requests.get(
            f"{TELEGRAM_API}/getUpdates",
            params={"offset": offset, "timeout": 10, "allowed_updates": ["message"]},
            timeout=15
        )
        data = resp.json()
        if data.get("ok"):
            return data.get("result", [])
    except Exception as e:
        print(f"[{now_str()}] Error getting updates: {e}")
    return []

def send_message(chat_id, text):
    try:
        requests.post(
            f"{TELEGRAM_API}/sendMessage",
            json={"chat_id": chat_id, "text": text, "parse_mode": "Markdown"},
            timeout=10
        )
    except Exception as e:
        print(f"[{now_str()}] Error sending: {e}")

def send_typing(chat_id):
    try:
        requests.post(f"{TELEGRAM_API}/sendChatAction",
                      json={"chat_id": chat_id, "action": "typing"}, timeout=5)
    except:
        pass

# ── State ───────────────────────────────────────────────────────────────────────
def load_state():
    if os.path.exists(STATE_FILE):
        with open(STATE_FILE) as f:
            return json.load(f)
    return {"last_update_id": 0}

def save_state(state):
    with open(STATE_FILE, "w") as f:
        json.dump(state, f)

def now_str():
    return datetime.now().strftime("%Y-%m-%d %H:%M:%S")

# ── Main ────────────────────────────────────────────────────────────────────────
def main():
    print(f"[{now_str()}] 🤖 Pang's Daily Assistant (keyword mode) starting...")

    if not os.path.exists(SERVICE_ACCOUNT_FILE):
        print(f"[{now_str()}] ⚠️  Service account file missing: {SERVICE_ACCOUNT_FILE}")
    else:
        print(f"[{now_str()}] ✅ Google Calendar service account found.")

    state  = load_state()
    offset = state["last_update_id"] + 1 if state["last_update_id"] else 0
    print(f"[{now_str()}] ✅ Polling for messages...")

    while True:
        updates = get_updates(offset)

        for update in updates:
            update_id = update.get("update_id", 0)
            offset = update_id + 1
            state["last_update_id"] = update_id

            message   = update.get("message", {})
            chat_id   = message.get("chat", {}).get("id")
            text      = (message.get("text") or "").strip().lower()
            user_name = message.get("from", {}).get("first_name", "Elisha")

            if not text or chat_id != ALLOWED_CHAT_ID:
                save_state(state)
                continue

            print(f"[{now_str()}] 📨 {user_name}: {text}")

            # Match command (strip @botname suffix if present)
            cmd = text.split("@")[0]
            handler = COMMANDS.get(cmd)

            if handler:
                send_typing(chat_id)
                reply = handler()
                send_message(chat_id, reply)
                print(f"[{now_str()}] ✅ Sent response for {cmd}")
            else:
                send_message(chat_id, "❓ Unknown command. Send /help to see available commands.")

            save_state(state)

        time.sleep(POLL_INTERVAL)

if __name__ == "__main__":
    main()
