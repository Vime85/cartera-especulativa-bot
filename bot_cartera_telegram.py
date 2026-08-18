import os
import yfinance as yf
from telegram import Update
from telegram.ext import Application, CommandHandler, ContextTypes

TICKERS = {
    "RKLB": "Rocket Lab",
    "ASTS": "AST SpaceMobile",
    "TEM": "Tempus AI",
    "IONQ": "IonQ",
}
MONTHLY = {"RKLB": 10, "ASTS": 8, "TEM": 7, "IONQ": 5}
ALERTS = {t: 5.0 for t in TICKERS}
LAST = {}
TOKEN = os.environ["TELEGRAM_BOT_TOKEN"]
CHAT_ID = os.getenv("TELEGRAM_CHAT_ID")

def prices():
    out = {}
    for t in TICKERS:
        try:
            d = yf.Ticker(t).history(period="2d", interval="1d")
            c = d["Close"].dropna()
            if len(c):
                p = float(c.iloc[-1])
                prev = float(c.iloc[-2]) if len(c) > 1 else None
                out[t] = (p, ((p/prev)-1)*100 if prev else None)
        except Exception:
            pass
    return out

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "🤖 Bot de tu cartera especulativa\n\n"
        "/precio - precios\n/carrrtera - plan mensual\n"
        "/alertas - umbrales\n/setalerta RKLB 5 - cambia una alerta\n/news - noticias"
    )

async def precio(update, context):
    p = prices()
    lines = ["📊 Precios"]
    for t, n in TICKERS.items():
        if t in p:
            price, ch = p[t]
            lines.append(f"{t} ({n}): {price:.2f} USD ({ch:+.2f}%)" if ch is not None else f"{t}: {price:.2f} USD")
    await update.message.reply_text("\n".join(lines))

async def cartera(update, context):
    total = sum(MONTHLY.values())
    lines = ["💰 Plan mensual"]
    for t, amount in MONTHLY.items():
        lines.append(f"{t}: {amount} €/mes ({amount/total*100:.1f}%)")
    lines.append(f"Total: {total} €/mes | 12 meses: {total*12} €")
    await update.message.reply_text("\n".join(lines))

async def alertas(update, context):
    await update.message.reply_text(
        "🔔 Alertas\n" + "\n".join(f"{t}: ±{v:.1f}%" for t, v in ALERTS.items())
    )

async def setalerta(update, context):
    if len(context.args) != 2 or context.args[0].upper() not in TICKERS:
        await update.message.reply_text("Uso: /setalerta RKLB 5")
        return
    try:
        pct = float(context.args[1])
        if pct <= 0: raise ValueError
    except ValueError:
        await update.message.reply_text("El porcentaje debe ser positivo.")
        return
    t = context.args[0].upper()
    ALERTS[t] = pct
    await update.message.reply_text(f"✅ {t}: alerta ±{pct:.1f}%")

async def news(update, context):
    lines = ["📰 Noticias disponibles"]
    for t in TICKERS:
        try:
            for item in yf.Ticker(t).news[:2]:
                title = item.get("title", "Sin título")
                link = item.get("link", "")
                lines.append(f"{t}: {title}\n{link}")
        except Exception:
            pass
    await update.message.reply_text("\n\n".join(lines)[:4000])

async def monitor(context: ContextTypes.DEFAULT_TYPE):
    if not CHAT_ID:
        return
    p = prices()
    alerts = []
    for t, (current, _) in p.items():
        previous = LAST.get(t)
        if previous:
            change = (current/previous - 1)*100
            if abs(change) >= ALERTS[t]:
                alerts.append(f"🚨 {t}: {change:+.2f}% | {current:.2f} USD")
        LAST[t] = current
    if alerts:
        await context.bot.send_message(chat_id=CHAT_ID, text="\n".join(alerts))

def main():
    app = Application.builder().token(TOKEN).build()
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("precio", precio))
    app.add_handler(CommandHandler("cartera", cartera))
    app.add_handler(CommandHandler("alertas", alertas))
    app.add_handler(CommandHandler("setalerta", setalerta))
    app.add_handler(CommandHandler("news", news))
    app.job_queue.run_repeating(monitor, interval=3600, first=30)
    app.run_polling()

if __name__ == "__main__":
    main()
