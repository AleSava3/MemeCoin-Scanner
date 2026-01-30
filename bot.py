import os
import time
import requests
from telegram import Update
from telegram.ext import (
    ApplicationBuilder,
    CommandHandler,
    ContextTypes,
)

# =========================
# CONFIG
# =========================
TOKEN = os.getenv("TOKEN")
CHAT_ID = int(os.getenv("CHAT_ID"))

DEXSCREENER_SOL = "https://api.dexscreener.com/latest/dex/pairs/solana"

MAX_ALERTS_PER_DAY = 3
SCAN_INTERVAL = 1800  # 30 min
REPORT_HOUR = 23  # UTC

# =========================
# STATO
# =========================
daily_alerts = 0
daily_scans = 0
top_score = 0
last_report_day = None

# =========================
# ANTI RUG
# =========================
def anti_rug(p):
    try:
        if p["liquidity"]["usd"] < 30000:
            return False
        if p["fdv"] > 10_000_000:
            return False
        if p["txns"]["h24"]["buys"] < p["txns"]["h24"]["sells"]:
            return False
        return True
    except:
        return False

# =========================
# SCORE
# =========================
def score_token(p):
    score = 0
    liquidity = p["liquidity"]["usd"]
    volume = p["volume"]["h24"]
    buys = p["txns"]["h24"]["buys"]
    sells = p["txns"]["h24"]["sells"]
    fdv = p["fdv"]
    age = (time.time()*1000 - p["pairCreatedAt"]) / 60000

    if liquidity > 200_000: score += 30
    elif liquidity > 100_000: score += 20
    elif liquidity > 50_000: score += 10

    if volume > liquidity * 5: score += 25
    elif volume > liquidity * 2: score += 15

    if buys > sells * 1.5: score += 20
    elif buys > sells: score += 10

    if fdv < 2_000_000: score += 15
    elif fdv < 5_000_000: score += 8

    if age > 240: score += 10
    elif age > 120: score += 5

    return score

# =========================
# SCAN
# =========================
async def scan(context: ContextTypes.DEFAULT_TYPE):
    global daily_alerts, daily_scans, top_score

    if daily_alerts >= MAX_ALERTS_PER_DAY:
        return

    try:
        r = requests.get(DEXSCREENER_SOL, timeout=10)
        if r.status_code != 200:
            return
        pairs = r.json().get("pairs", [])
    except:
        return

    for p in pairs:
        if daily_alerts >= MAX_ALERTS_PER_DAY:
            break

        daily_scans += 1

        if not anti_rug(p):
            continue

        score = score_token(p)
        if score < 60:
            continue

        emoji = "🔥" if score >= 75 else "⚠️"
        top_score = max(top_score, score)

        msg = f"""{emoji} SOLANA MEME ALERT

Token: {p['baseToken']['symbol']}
Score: {score}/100

Liquidity: ${p['liquidity']['usd']:,.0f}
Market Cap: ${p['fdv']:,.0f}
Volume 24h: ${p['volume']['h24']:,.0f}

Anti-Rug: OK
{p['url']}
"""

        await context.bot.send_message(chat_id=CHAT_ID, text=msg)
        daily_alerts += 1
        break

# =========================
# REPORT
# =========================
async def daily_report(context: ContextTypes.DEFAULT_TYPE):
    global daily_alerts, daily_scans, top_score, last_report_day

    today = time.strftime("%Y-%m-%d")
    hour = int(time.strftime("%H"))

    if last_report_day == today or hour != REPORT_HOUR:
        return

    msg = f"""📊 REPORT GIORNALIERO

Analizzati: {daily_scans}
Alert: {daily_alerts}
Top score: {top_score}/100
"""

    await context.bot.send_message(chat_id=CHAT_ID, text=msg)

    daily_alerts = 0
    daily_scans = 0
    top_score = 0
    last_report_day = today

# =========================
# COMANDI
# =========================
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("🤖 Bot Solana ONLINE")

async def status(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        f"🟢 Online\nAlert oggi: {daily_alerts}/{MAX_ALERTS_PER_DAY}"
    )

# =========================
# MAIN
# =========================
def main():
    app = ApplicationBuilder().token(TOKEN).build()

    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("status", status))

    app.job_queue.run_repeating(scan, interval=SCAN_INTERVAL, first=15)
    app.job_queue.run_repeating(daily_report, interval=3600, first=60)

    app.run_polling()

if __name__ == "__main__":
    main()
