import os
import time
import requests
from telegram import Update
from telegram.ext import (
    ApplicationBuilder,
    CommandHandler,
    ContextTypes,
)

# =====================
# CONFIG
# =====================
TOKEN = os.getenv("TOKEN")
CHAT_ID = int(os.getenv("CHAT_ID"))

DEXSCREENER_SOL = "https://api.dexscreener.com/latest/dex/pairs/solana"
MAX_ALERTS_PER_DAY = 3
SCAN_INTERVAL = 1800  # 30 min
REPORT_HOUR = 23  # UTC

# =====================
# STATE
# =====================
daily_alerts = 0
daily_scans = 0
top_score = 0
last_report_day = None

# =====================
# LOGIC
# =====================
def anti_rug(p):
    try:
        return (
            p["liquidity"]["usd"] >= 30000
            and p["fdv"] <= 10_000_000
            and p["txns"]["h24"]["buys"] > p["txns"]["h24"]["sells"]
        )
    except:
        return False

def score_token(p):
    score = 0
    l = p["liquidity"]["usd"]
    v = p["volume"]["h24"]
    b = p["txns"]["h24"]["buys"]
    s = p["txns"]["h24"]["sells"]
    fdv = p["fdv"]
    age = (time.time()*1000 - p["pairCreatedAt"]) / 60000

    if l > 200_000: score += 30
    elif l > 100_000: score += 20
    elif l > 50_000: score += 10

    if v > l * 5: score += 25
    elif v > l * 2: score += 15

    if b > s * 1.5: score += 20
    elif b > s: score += 10

    if fdv < 2_000_000: score += 15
    elif fdv < 5_000_000: score += 8

    if age > 240: score += 10
    elif age > 120: score += 5

    return score

# =====================
# JOBS
# =====================
async def scan(context: ContextTypes.DEFAULT_TYPE):
    global daily_alerts, daily_scans, top_score

    if daily_alerts >= MAX_ALERTS_PER_DAY:
        return

    try:
        r = requests.get(DEXSCREENER_SOL, timeout=10)
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

        await context.bot.send_message(
            chat_id=CHAT_ID,
            text=f"""{emoji} SOLANA MEME ALERT
Token: {p['baseToken']['symbol']}
Score: {score}/100
Liquidity: ${p['liquidity']['usd']:,.0f}
Market Cap: ${p['fdv']:,.0f}
{p['url']}"""
        )

        daily_alerts += 1
        break

async def report(context: ContextTypes.DEFAULT_TYPE):
    global daily_alerts, daily_scans, top_score, last_report_day

    today = time.strftime("%Y-%m-%d")
    if last_report_day == today or int(time.strftime("%H")) != REPORT_HOUR:
        return

    await context.bot.send_message(
        chat_id=CHAT_ID,
        text=f"""📊 REPORT GIORNALIERO
Analizzati: {daily_scans}
Alert: {daily_alerts}
Top score: {top_score}/100"""
    )

    daily_alerts = daily_scans = top_score = 0
    last_report_day = today

# =====================
# COMMANDS
# =====================
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("🤖 Bot Solana ONLINE")

async def status(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        f"🟢 Online | Alert: {daily_alerts}/{MAX_ALERTS_PER_DAY}"
    )

# =====================
# MAIN
# =====================
def main():
    app = ApplicationBuilder().token(TOKEN).build()

    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("status", status))

    app.job_queue.run_repeating(scan, interval=SCAN_INTERVAL, first=20)
    app.job_queue.run_repeating(report, interval=3600, first=60)

    app.run_polling()

if __name__ == "__main__":
    main()
