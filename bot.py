import requests
import time
import os
from telegram import Update, Bot
from telegram.ext import ApplicationBuilder, CommandHandler, ContextTypes

TOKEN = os.getenv("TOKEN")
CHAT_ID = int(os.getenv("CHAT_ID"))

URL = "https://api.dexscreener.com/latest/dex/search?q=solana"

MAX_ALERTS_PER_DAY = 3
alerts_sent = 0
last_token = "Nessuno"
current_day = time.strftime("%Y-%m-%d")

bot = Bot(token=TOKEN)

def anti_rug(pair):
def score_token(pair):
    score = 0

    liquidity = pair["liquidity"]["usd"]
    volume = pair["volume"]["h24"]
    buys = pair["txns"]["h24"]["buys"]
    sells = pair["txns"]["h24"]["sells"]
    fdv = pair["fdv"]
    age = (time.time()*1000 - pair["pairCreatedAt"]) / 60000

    if liquidity > 200000: score += 30
    elif liquidity > 100000: score += 20
    elif liquidity > 50000: score += 10

    if volume > liquidity * 5: score += 25
    elif volume > liquidity * 2: score += 15

    if buys > sells * 1.5: score += 20
    elif buys > sells: score += 10

    if fdv < 2_000_000: score += 15
    elif fdv < 5_000_000: score += 8

    if age > 240: score += 10
    elif age > 120: score += 5

    return score

    try:
        liquidity = pair["liquidity"]["usd"]
        volume = pair["volume"]["h24"]
        buys = pair["txns"]["h24"]["buys"]
        sells = pair["txns"]["h24"]["sells"]
        fdv = pair["fdv"]
        age_minutes = (time.time()*1000 - pair["pairCreatedAt"]) / 60000

        if liquidity < 50000: return False
        if fdv is None or fdv < 300000: return False
        if volume < liquidity * 2: return False
        if buys <= sells: return False
        if age_minutes < 60: return False

        return True
    except:
        return False

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("🤖 Bot Solana attivo.")

async def status(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        f"🟢 Online\nAlert oggi: {alerts_sent}/{MAX_ALERTS_PER_DAY}"
    )

async def last(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(f"Ultimo token segnalato:\n{last_token}")

def scan():
    global alerts_sent, current_day, last_token

    today = time.strftime("%Y-%m-%d")
    if today != current_day:
        alerts_sent = 0
        current_day = today

    r = requests.get(URL)
    pairs = r.json()["pairs"]

    for p in pairs:
        if alerts_sent >= MAX_ALERTS_PER_DAY:
            return
        if p["chainId"] != "solana":
            continue
        if anti_rug(p):
            alerts_sent += 1
            last_token = p["baseToken"]["symbol"]

            msg = f"""
🟢 SOLANA MEME ALERT

Token: {p['baseToken']['symbol']}
Liquidity: ${p['liquidity']['usd']:,.0f}
Market Cap: ${p['fdv']:,.0f}
Volume 24h: ${p['volume']['h24']:,.0f}

Anti-Rug: OK
{p['url']}
"""
            bot.send_message(chat_id=CHAT_ID, text=msg)

async def loop(app):
    while True:
        scan()
        await app.bot.initialize()
        time.sleep(3600)  # ogni 1 ora

def main():
    app = ApplicationBuilder().token(TOKEN).build()
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("status", status))
    app.add_handler(CommandHandler("last", last))
    app.run_polling()

if __name__ == "__main__":
    main()
