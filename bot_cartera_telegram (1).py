import os
import html
from datetime import datetime, timezone

import requests
import yfinance as yf


# ============================================================
# CONFIGURACIÓN
# ============================================================

TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN", "").strip()
CHAT_ID = os.getenv("CHAT_ID", "").strip()

# Cambia aquí los activos que quieras vigilar.
# Ejemplos:
# "AAPL"       Apple
# "NVDA"       Nvidia
# "TSLA"       Tesla
# "AMD"        AMD
# "BTC-USD"    Bitcoin
# "ETH-USD"    Ethereum
# "QQQ"        Nasdaq 100
# "SPY"        S&P 500

TICKERS = [
    "NVDA",
    "TSLA",
    "AMD",
    "BTC-USD",
    "ETH-USD",
]

# Porcentaje diario a partir del cual se genera una alerta.
ALERTS = {
    "NVDA": 3.0,
    "TSLA": 4.0,
    "AMD": 4.0,
    "BTC-USD": 3.0,
    "ETH-USD": 4.0,
}


# ============================================================
# TELEGRAM
# ============================================================

def telegram_url(method):
    return (
        f"https://api.telegram.org/bot"
        f"{TELEGRAM_BOT_TOKEN}/{method}"
    )


def send_telegram(message):
    if not TELEGRAM_BOT_TOKEN:
        raise RuntimeError(
            "Falta el secret TELEGRAM_BOT_TOKEN"
        )

    if not CHAT_ID:
        raise RuntimeError(
            "Falta el secret CHAT_ID"
        )

    response = requests.post(
        telegram_url("sendMessage"),
        json={
            "chat_id": CHAT_ID,
            "text": message,
            "parse_mode": "HTML",
            "disable_web_page_preview": True,
        },
        timeout=30,
    )

    if not response.ok:
        raise RuntimeError(
            f"Telegram devolvió HTTP {response.status_code}: "
            f"{response.text}"
        )

    data = response.json()

    if not data.get("ok"):
        raise RuntimeError(
            f"Error de Telegram: {data}"
        )


# ============================================================
# PRECIOS
# ============================================================

def get_price(ticker):
    """
    Obtiene precio actual y variación diaria aproximada.
    """

    try:
        stock = yf.Ticker(ticker)

        history = stock.history(
            period="2d",
            interval="1d",
            auto_adjust=False,
        )

        if history.empty:
            return None

        closes = history["Close"].dropna()

        if len(closes) == 0:
            return None

        current = float(closes.iloc[-1])

        if len(closes) >= 2:
            previous = float(closes.iloc[-2])

            if previous != 0:
                change = (
                    (current / previous) - 1
                ) * 100
            else:
                change = 0.0
        else:
            change = 0.0

        return {
            "ticker": ticker,
            "price": current,
            "change": change,
        }

    except Exception as exc:
        print(
            f"[ERROR] {ticker}: {exc}"
        )
        return None


# ============================================================
# CARTERA
# ============================================================

def get_portfolio():
    results = []

    for ticker in TICKERS:
        result = get_price(ticker)

        if result:
            results.append(result)

    return results


# ============================================================
# FORMATO
# ============================================================

def format_price(price):
    if price >= 1000:
        return f"{price:,.2f}"

    if price >= 1:
        return f"{price:,.2f}"

    return f"{price:,.4f}"


def change_symbol(change):
    if change > 0:
        return "🟢"

    if change < 0:
        return "🔴"

    return "⚪"


def format_portfolio(results):
    lines = [
        "💼 <b>CARPETA ESPECULATIVA</b>",
        "",
    ]

    for item in results:
        ticker = html.escape(item["ticker"])
        price = format_price(item["price"])
        change = item["change"]

        symbol = change_symbol(change)

        lines.append(
            f"{symbol} <b>{ticker}</b>  "
            f"{price}  "
            f"<b>{change:+.2f}%</b>"
        )

    return "\n".join(lines)


# ============================================================
# ALERTAS
# ============================================================

def build_alerts(results):
    alerts = []

    for item in results:
        ticker = item["ticker"]
        change = item["change"]

        threshold = ALERTS.get(ticker)

        if threshold is None:
            continue

        if abs(change) >= threshold:

            if change > 0:
                emoji = "🚀"
                direction = "SUBIDA"
            else:
                emoji = "🚨"
                direction = "CAÍDA"

            alerts.append(
                f"{emoji} <b>{direction}</b>\n"
                f"<b>{html.escape(ticker)}</b>: "
                f"{change:+.2f}%\n"
                f"Umbral: ±{threshold:.2f}%"
            )

    return alerts


# ============================================================
# PRUEBA DE CONEXIÓN
# ============================================================

def test_telegram():
    """
    Comprueba que Telegram funciona.
    """

    now = datetime.now(
        timezone.utc
    ).strftime("%Y-%m-%d %H:%M UTC")

    message = (
        "🤖 <b>BOT CARTERA ESPECULATIVA</b>\n\n"
        "✅ Bot conectado correctamente.\n"
        f"🕐 {now}\n\n"
        "Comenzando análisis de cartera..."
    )

    send_telegram(message)


# ============================================================
# EJECUCIÓN PRINCIPAL
# ============================================================

def main():

    print("=" * 60)
    print("BOT CARTERA ESPECULATIVA")
    print("=" * 60)

    # --------------------------------------------------------
    # Comprobar configuración
    # --------------------------------------------------------

    if not TELEGRAM_BOT_TOKEN:
        raise RuntimeError(
            "No existe TELEGRAM_BOT_TOKEN"
        )

    if not CHAT_ID:
        raise RuntimeError(
            "No existe CHAT_ID"
        )

    if not TICKERS:
        raise RuntimeError(
            "TICKERS está vacío"
        )

    print(
        f"Activos a analizar: {', '.join(TICKERS)}"
    )

    # --------------------------------------------------------
    # 1. Prueba Telegram
    # --------------------------------------------------------

    print("Enviando prueba a Telegram...")

    test_telegram()

    print("Telegram OK")

    # --------------------------------------------------------
    # 2. Obtener cartera
    # --------------------------------------------------------

    print("Consultando precios...")

    results = get_portfolio()

    if not results:
        raise RuntimeError(
            "No se pudo obtener ningún precio."
        )

    print(
        f"Activos obtenidos: {len(results)}"
    )

    # --------------------------------------------------------
    # 3. Mensaje de cartera
    # --------------------------------------------------------

    portfolio_message = format_portfolio(
        results
    )

    send_telegram(
        portfolio_message
    )

    print("Cartera enviada.")

    # --------------------------------------------------------
    # 4. Alertas
    # --------------------------------------------------------

    alerts = build_alerts(results)

    if alerts:

        alert_message = (
            "⚠️ <b>ALERTAS DE MERCADO</b>\n\n"
            + "\n\n".join(alerts)
        )

        send_telegram(
            alert_message
        )

        print(
            f"Alertas enviadas: {len(alerts)}"
        )

    else:

        print(
            "No hay movimientos que superen "
            "los umbrales."
        )

    # --------------------------------------------------------
    # 5. Final
    # --------------------------------------------------------

    print("=" * 60)
    print("BOT FINALIZADO CORRECTAMENTE")
    print("=" * 60)


if __name__ == "__main__":
    main()
