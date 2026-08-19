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

TOTAL_MONTHLY = 130.0

# ============================================================
# CARTERA MENSUAL
# ============================================================
#
# 100 € ETFs
#  30 € especulativa
#
# TOTAL = 130 €
#

PORTFOLIO = [

    # --------------------------------------------------------
    # ETF PRINCIPAL
    # --------------------------------------------------------

    {
        "name": "Vanguard FTSE All-World UCITS ETF",
        "ticker": "VWCE.DE",
        "display_ticker": "VWCE",
        "monthly": 80.0,
        "type": "ETF",
        "role": "Núcleo global",
    },

    # --------------------------------------------------------
    # ETF MOMENTUM
    # --------------------------------------------------------

    {
        "name": "iShares Edge MSCI World Momentum Factor UCITS ETF",
        "ticker": "IS3R.DE",
        "display_ticker": "IS3R",
        "monthly": 20.0,
        "type": "ETF",
        "role": "Factor momentum",
    },

    # --------------------------------------------------------
    # CARTERA ESPECULATIVA
    # --------------------------------------------------------

    {
        "name": "Rocket Lab",
        "ticker": "RKLB",
        "display_ticker": "RKLB",
        "monthly": 10.0,
        "type": "ESPECULATIVA",
        "role": "Espacial",
    },

    {
        "name": "AST SpaceMobile",
        "ticker": "ASTS",
        "display_ticker": "ASTS",
        "monthly": 8.0,
        "type": "ESPECULATIVA",
        "role": "Satélites / conectividad",
    },

    {
        "name": "Tempus AI",
        "ticker": "TEM",
        "display_ticker": "TEM",
        "monthly": 7.0,
        "type": "ESPECULATIVA",
        "role": "IA / salud",
    },

    {
        "name": "IonQ",
        "ticker": "IONQ",
        "display_ticker": "IONQ",
        "monthly": 5.0,
        "type": "ESPECULATIVA",
        "role": "Computación cuántica",
    },
]


# ============================================================
# AJUSTES
# ============================================================

WEEKLY_ALERT = 8.0
STRONG_WEEKLY_ALERT = 15.0

TELEGRAM_TIMEOUT = 30


# ============================================================
# VALIDACIÓN DE CONFIGURACIÓN
# ============================================================

def validate_config():

    total = sum(
        item["monthly"]
        for item in PORTFOLIO
    )

    if round(total, 2) != round(TOTAL_MONTHLY, 2):

        raise RuntimeError(
            f"La cartera suma {total:.2f} €, "
            f"pero debería sumar {TOTAL_MONTHLY:.2f} €."
        )

    if not TELEGRAM_BOT_TOKEN:

        raise RuntimeError(
            "No existe TELEGRAM_BOT_TOKEN."
        )

    if not CHAT_ID:

        raise RuntimeError(
            "No existe CHAT_ID."
        )


# ============================================================
# FORMATO
# ============================================================

def money(value):

    if value is None:
        return "N/D"

    return (
        f"{value:,.2f} €"
        .replace(",", "X")
        .replace(".", ",")
        .replace("X", ".")
    )


def pct(value):

    if value is None:
        return "N/D"

    sign = "+" if value > 0 else ""

    return f"{sign}{value:.2f}%"


def safe_float(value):

    try:

        if value is None:
            return None

        return float(value)

    except (TypeError, ValueError):

        return None


def fmt_date(value):

    if value is None:
        return "N/D"

    try:

        if hasattr(value, "to_pydatetime"):
            value = value.to_pydatetime()

        if value.tzinfo is None:
            value = value.replace(
                tzinfo=timezone.utc
            )

        return value.astimezone(
            timezone.utc
        ).strftime("%d/%m/%Y")

    except Exception:

        return "N/D"


# ============================================================
# DATOS DE MERCADO
# ============================================================

def get_market_data(ticker_symbol):

    ticker = yf.Ticker(
        ticker_symbol
    )

    history = ticker.history(
        period="3mo",
        interval="1d",
        auto_adjust=True,
    )

    if history is None or history.empty:

        raise RuntimeError(
            "No se han recibido datos de mercado."
        )

    closes = history[
        "Close"
    ].dropna()

    if closes.empty:

        raise RuntimeError(
            "No hay precios de cierre disponibles."
        )

    current = safe_float(
        closes.iloc[-1]
    )

    previous = None
    week_ago = None
    month_ago = None

    if len(closes) >= 2:
        previous = safe_float(
            closes.iloc[-2]
        )

    if len(closes) >= 6:
        week_ago = safe_float(
            closes.iloc[-6]
        )

    if len(closes) >= 22:
        month_ago = safe_float(
            closes.iloc[-22]
        )

    day_change = None
    week_change = None
    month_change = None

    if current is not None and previous:
        day_change = (
            current / previous - 1
        ) * 100

    if current is not None and week_ago:
        week_change = (
            current / week_ago - 1
        ) * 100

    if current is not None and month_ago:
        month_change = (
            current / month_ago - 1
        ) * 100

    high_3m = safe_float(
        closes.max()
    )

    low_3m = safe_float(
        closes.min()
    )

    distance_high = None
    distance_low = None

    if current and high_3m:

        distance_high = (
            current / high_3m - 1
        ) * 100

    if current and low_3m:

        distance_low = (
            current / low_3m - 1
        ) * 100

    return {

        "current": current,

        "day_change": day_change,

        "week_change": week_change,

        "month_change": month_change,

        "high_3m": high_3m,

        "low_3m": low_3m,

        "distance_high": distance_high,

        "distance_low": distance_low,

        "last_date": fmt_date(
            history.index[-1]
        ),
    }


# ============================================================
# NOTICIAS
# ============================================================

def get_news(
    ticker_symbol,
    limit=3
):

    try:

        ticker = yf.Ticker(
            ticker_symbol
        )

        raw_news = ticker.news or []

    except Exception:

        return []

    news = []

    for item in raw_news[:limit]:

        try:

            content = item.get(
                "content",
                item
            )

            title = (
                content.get("title")
                or item.get("title")
                or "Noticia sin título"
            )

            publisher = None

            provider = content.get(
                "provider"
            )

            if isinstance(
                provider,
                dict
            ):

                publisher = provider.get(
                    "displayName"
                )

            if not publisher:

                publisher = item.get(
                    "publisher",
                    "Fuente desconocida"
                )

            link = None

            canonical = content.get(
                "canonicalUrl"
            )

            if isinstance(
                canonical,
                dict
            ):

                link = canonical.get(
                    "url"
                )

            if not link:

                click = content.get(
                    "clickThroughUrl"
                )

                if isinstance(
                    click,
                    dict
                ):

                    link = click.get(
                        "url"
                    )

            if not link:

                link = item.get(
                    "link"
                )

            pub_date = content.get(
                "pubDate"
            )

            news.append(
                {
                    "title": str(title),
                    "publisher": str(
                        publisher
                    ),
                    "link": link,
                    "date": pub_date,
                }
            )

        except Exception:

            continue

    return news


# ============================================================
# SEÑAL Y ACCIÓN
# ============================================================

def get_action(
    asset,
    data,
    news
):

    week = data.get(
        "week_change"
    )

    if week is None:

        return (
            "⚪ SIN DATOS",
            "No hay suficientes datos "
            "para valorar esta semana."
        )

    # --------------------------------------------------------
    # ETFs
    # --------------------------------------------------------

    if asset["type"] == "ETF":

        if abs(week) >= STRONG_WEEKLY_ALERT:

            return (
                "🟡 VIGILAR",
                "Movimiento semanal excepcional. "
                "No cambiar la aportación solo por "
                "el movimiento del precio."
            )

        return (
            "🟢 MANTENER",
            f"Seguir con la aportación prevista "
            f"de {money(asset['monthly'])}/mes."
        )

    # --------------------------------------------------------
    # ESPECULATIVAS
    # --------------------------------------------------------

    if abs(week) >= STRONG_WEEKLY_ALERT:

        return (
            "🟠 REVISAR",
            "Movimiento muy fuerte. Revisar "
            "noticias y tesis antes de aumentar "
            "o reducir la posición."
        )

    if abs(week) >= WEEKLY_ALERT:

        return (
            "🟡 VIGILAR",
            "Volatilidad elevada. No tomar "
            "decisiones solo por el precio."
        )

    if news:

        return (
            "🟢 MANTENER / VIGILAR",
            "No hay una acción automática por "
            "precio. Revisar las noticias."
        )

    return (
        "🟢 MANTENER",
        f"Continuar con la aportación prevista "
        f"de {money(asset['monthly'])}/mes."
    )


# ============================================================
# ANALIZAR ACTIVO
# ============================================================

def analyze_asset(asset):

    data = get_market_data(
        asset["ticker"]
    )

    news = get_news(
        asset["ticker"],
        limit=3
    )

    action, explanation = get_action(
        asset,
        data,
        news
    )

    return {

        "asset": asset,

        "data": data,

        "news": news,

        "action": action,

        "explanation": explanation,
    }


# ============================================================
# CONSTRUIR INFORME
# ============================================================

def build_report(results):

    now = datetime.now(
        timezone.utc
    )

    lines = []

    lines.append(
        "📊 <b>INFORME SEMANAL — CARTERA 130 €</b>"
    )

    lines.append(
        f"<i>{now.strftime('%d/%m/%Y %H:%M')} UTC</i>"
    )

    lines.append("")

    lines.append(
        "Plan mensual: "
        "<b>130 €</b> — "
        "100 € ETFs + "
        "30 € especulativo."
    )

    lines.append("")

    # --------------------------------------------------------
    # APORTACIONES
    # --------------------------------------------------------

    lines.append(
        "🏦 <b>APORTACIONES MENSUALES</b>"
    )

    lines.append("")

    for asset in PORTFOLIO:

        lines.append(
            f"• <b>{html.escape(asset['display_ticker'])}</b> "
            f"— {money(asset['monthly'])}/mes"
        )

    lines.append("")

    lines.append(
        "━━━━━━━━━━━━━━━━━━━━"
    )

    lines.append("")

    # --------------------------------------------------------
    # ESTADO
    # --------------------------------------------------------

    lines.append(
        "📈 <b>ESTADO DE LA CARTERA</b>"
    )

    lines.append("")

    for result in results:

        asset = result["asset"]

        data = result["data"]

        lines.append(
            f"<b>{html.escape(asset['display_ticker'])}</b> "
            f"— {html.escape(asset['name'])}"
        )

        if data["current"] is not None:

            lines.append(
                f"💶 Precio: "
                f"<b>{data['current']:.2f}</b>"
            )

        else:

            lines.append(
                "💶 Precio: N/D"
            )

        lines.append(
            f"📅 Semana: "
            f"<b>{pct(data['week_change'])}</b> "
            f"| Mes: "
            f"<b>{pct(data['month_change'])}</b>"
        )

        if (
            data["low_3m"] is not None
            and data["high_3m"] is not None
        ):

            lines.append(
                f"📉 3 meses: "
                f"{data['low_3m']:.2f} — "
                f"{data['high_3m']:.2f}"
            )

        else:

            lines.append(
                "📉 3 meses: N/D"
            )

        lines.append(
            f"➡️ <b>{result['action']}</b>"
        )

        lines.append(
            f"   "
            f"{html.escape(result['explanation'])}"
        )

        lines.append("")

    lines.append(
        "━━━━━━━━━━━━━━━━━━━━"
    )

    lines.append("")

    # --------------------------------------------------------
    # NOTICIAS
    # --------------------------------------------------------

    lines.append(
        "📰 <b>NOTICIAS DESTACADAS</b>"
    )

    lines.append("")

    news_count = 0

    for result in results:

        asset = result["asset"]

        news = result["news"]

        if not news:
            continue

        for item in news[:2]:

            title = html.escape(
                item["title"]
            )

            publisher = html.escape(
                item["publisher"]
            )

            if item["link"]:

                safe_link = html.escape(
                    item["link"],
                    quote=True
                )

                lines.append(
                    f"• <a href=\"{safe_link}\">"
                    f"{title}"
                    f"</a> "
                    f"({publisher}) "
                    f"— {asset['display_ticker']}"
                )

            else:

                lines.append(
                    f"• {title} "
                    f"({publisher}) "
                    f"— {asset['display_ticker']}"
                )

            news_count += 1

    if news_count == 0:

        lines.append(
            "No se han podido obtener "
            "noticias esta semana."
        )

    lines.append("")

    lines.append(
        "━━━━━━━━━━━━━━━━━━━━"
    )

    lines.append("")

    # --------------------------------------------------------
    # QUÉ HACER
    # --------------------------------------------------------

    lines.append(
        "🎯 <b>QUÉ HACER ESTA SEMANA</b>"
    )

    lines.append("")

    lines.append(
        "1. <b>VWCE:</b> mantener "
        "80 €/mes."
    )

    lines.append(
        "2. <b>IS3R:</b> mantener "
        "20 €/mes."
    )

    lines.append(
        "3. <b>RKLB:</b> mantener "
        "10 €/mes salvo cambio de tesis."
    )

    lines.append(
        "4. <b>ASTS:</b> mantener "
        "8 €/mes salvo cambio de tesis."
    )

    lines.append(
        "5. <b>TEM:</b> mantener "
        "7 €/mes salvo cambio de tesis."
    )

    lines.append(
        "6. <b>IONQ:</b> mantener "
        "5 €/mes salvo cambio de tesis."
    )

    lines.append("")

    lines.append(
        "⚠️ <i>Una subida o caída semanal "
        "por sí sola no es motivo para cambiar "
        "la estrategia. En las especulativas, "
        "hay que valorar también resultados, "
        "noticias y evolución de la tesis.</i>"
    )

    return "\n".join(lines)


# ============================================================
# TELEGRAM
# ============================================================

def send_telegram(message):

    url = (
        f"https://api.telegram.org/bot"
        f"{TELEGRAM_BOT_TOKEN}/sendMessage"
    )

    response = requests.post(

        url,

        data={

            "chat_id": CHAT_ID,

            "text": message,

            "parse_mode": "HTML",

            "disable_web_page_preview": True,
        },

        timeout=TELEGRAM_TIMEOUT,
    )

    if not response.ok:

        raise RuntimeError(
            f"Telegram devolvió "
            f"HTTP {response.status_code}: "
            f"{response.text[:500]}"
        )


# ============================================================
# DIVIDIR MENSAJES LARGOS
# ============================================================

def split_message(
    text,
    max_length=3900
):

    if len(text) <= max_length:

        return [text]

    parts = []

    current = ""

    for line in text.split("\n"):

        if len(line) > max_length:

            if current:

                parts.append(
                    current
                )

                current = ""

            while len(line) > max_length:

                parts.append(
                    line[:max_length]
                )

                line = line[
                    max_length:
                ]

            if line:

                current = line

            continue

        if (
            len(current)
            + len(line)
            + 1
            > max_length
        ):

            if current:

                parts.append(
                    current
                )

            current = line

        else:

            if current:

                current += "\n"

            current += line

    if current:

        parts.append(
            current
        )

    return parts


# ============================================================
# MAIN
# ============================================================

def main():

    print("=" * 60)

    print(
        "BOT DE CARTERA"
    )

    print("=" * 60)

    validate_config()

    print(
        f"Cartera mensual: "
        f"{TOTAL_MONTHLY:.0f} €"
    )

    print("Activos:")

    for asset in PORTFOLIO:

        print(
            f"  "
            f"{asset['display_ticker']}: "
            f"{asset['monthly']:.0f} €/mes "
            f"({asset['ticker']})"
        )

    results = []

    for asset in PORTFOLIO:

        print(
            f"Analizando "
            f"{asset['display_ticker']}..."
        )

        try:

            result = analyze_asset(
                asset
            )

            results.append(
                result
            )

            print(
                "  OK — semana: "
                f"{pct(result['data']['week_change'])}"
            )

        except Exception as exc:

            print(
                f"  ERROR en "
                f"{asset['display_ticker']}: "
                f"{exc}"
            )

            results.append(

                {

                    "asset": asset,

                    "data": {

                        "current": None,

                        "day_change": None,

                        "week_change": None,

                        "month_change": None,

                        "high_3m": None,

                        "low_3m": None,

                        "distance_high": None,

                        "distance_low": None,

                        "last_date": None,
                    },

                    "news": [],

                    "action": "⚪ ERROR",

                    "explanation": (
                        "No se ha podido obtener "
                        "correctamente la información "
                        "de este activo."
                    ),
                }
            )

    report = build_report(
        results
    )

    messages = split_message(
        report
    )

    print(
        f"Enviando "
        f"{len(messages)} mensaje(s) "
        f"a Telegram..."
    )

    for message in messages:

        send_telegram(
            message
        )

    print(
        "Informe enviado correctamente."
    )

    print("=" * 60)


# ============================================================
# EJECUCIÓN
# ============================================================

if __name__ == "__main__":

    main()
