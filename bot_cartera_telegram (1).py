import os
import html
from datetime import datetime, timezone

import requests
import yfinance as yf


# ============================================================
# BOT DE SEGUIMIENTO DE CARTERA
# ============================================================
#
# Cartera mensual:
#
#   80 €  VWCE      - Vanguard FTSE All-World
#   20 €  IWMO.MI   - iShares Edge MSCI World Momentum
#   10 €  RKLB      - Rocket Lab
#    8 €  ASTS      - AST SpaceMobile
#    7 €  TEM       - Tempus AI
#    5 €  IONQ      - IonQ
#
# Total: 130 €/mes
#
# El bot NO ejecuta compras ni ventas.
# Solo analiza y envía un informe a Telegram.
#
# Recomendación:
#   🟢 MANTENER
#   🟡 VIGILAR
#   🔴 REVISAR
#
# Para las posiciones especulativas se evita recomendar
# vender simplemente por una caída de precio.
# ============================================================


# ============================================================
# CONFIGURACIÓN TELEGRAM
# ============================================================

TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN", "").strip()
CHAT_ID = os.getenv("CHAT_ID", "").strip()


# ============================================================
# CARTERA
# ============================================================

PORTFOLIO = [
    {
        "ticker": "VWCE.AS",
        "name": "Vanguard FTSE All-World",
        "short": "VWCE",
        "monthly": 80,
        "type": "ETF",
        "speculative": False,
    },
    {
        "ticker": "IWMO.MI",
        "name": "iShares Edge MSCI World Momentum",
        "short": "IWMO",
        "monthly": 20,
        "type": "ETF",
        "speculative": False,
    },
    {
        "ticker": "RKLB",
        "name": "Rocket Lab",
        "short": "RKLB",
        "monthly": 10,
        "type": "Acción",
        "speculative": True,
    },
    {
        "ticker": "ASTS",
        "name": "AST SpaceMobile",
        "short": "ASTS",
        "monthly": 8,
        "type": "Acción",
        "speculative": True,
    },
    {
        "ticker": "TEM",
        "name": "Tempus AI",
        "short": "TEM",
        "monthly": 7,
        "type": "Acción",
        "speculative": True,
    },
    {
        "ticker": "IONQ",
        "name": "IonQ",
        "short": "IONQ",
        "monthly": 5,
        "type": "Acción",
        "speculative": True,
    },
]


TOTAL_MONTHLY = sum(x["monthly"] for x in PORTFOLIO)


# ============================================================
# FUNCIONES GENERALES
# ============================================================

def safe_float(value):
    """Convierte un valor a float sin romper el programa."""
    try:
        if value is None:
            return None

        value = float(value)

        if value != value:
            return None

        return value

    except Exception:
        return None


def format_price(value):
    """Formatea un precio."""
    value = safe_float(value)

    if value is None:
        return "N/D"

    if value >= 1000:
        return f"{value:,.0f}"

    if value >= 100:
        return f"{value:,.2f}"

    if value >= 1:
        return f"{value:,.2f}"

    return f"{value:.4f}"


def format_percent(value):
    """Formatea un porcentaje."""
    value = safe_float(value)

    if value is None:
        return "N/D"

    sign = "+" if value > 0 else ""

    return f"{sign}{value:.2f}%"


def escape(text):
    """Escapa texto para Telegram HTML."""
    return html.escape(str(text))


# ============================================================
# TELEGRAM
# ============================================================

def send_telegram(message):
    """Envía un mensaje a Telegram."""

    if not TELEGRAM_BOT_TOKEN:
        raise RuntimeError(
            "Falta la variable TELEGRAM_BOT_TOKEN."
        )

    if not CHAT_ID:
        raise RuntimeError(
            "Falta la variable CHAT_ID."
        )

    url = (
        f"https://api.telegram.org/bot"
        f"{TELEGRAM_BOT_TOKEN}/sendMessage"
    )

    payload = {
        "chat_id": CHAT_ID,
        "text": message,
        "parse_mode": "HTML",
        "disable_web_page_preview": True,
    }

    response = requests.post(
        url,
        json=payload,
        timeout=30,
    )

    response.raise_for_status()

    data = response.json()

    if not data.get("ok"):
        raise RuntimeError(
            f"Telegram respondió con error: {data}"
        )


# ============================================================
# DATOS DE MERCADO
# ============================================================

def download_history(ticker):
    """
    Descarga aproximadamente un año de datos diarios.
    """

    try:
        data = yf.download(
            ticker,
            period="1y",
            interval="1d",
            auto_adjust=True,
            progress=False,
            threads=False,
        )

        if data is None or data.empty:
            return None

        # Algunas versiones de yfinance devuelven columnas
        # MultiIndex. Las simplificamos.
        if hasattr(data.columns, "nlevels"):
            if data.columns.nlevels > 1:
                try:
                    data.columns = data.columns.get_level_values(0)
                except Exception:
                    pass

        if "Close" not in data.columns:
            return None

        data = data.dropna(subset=["Close"])

        if data.empty:
            return None

        return data

    except Exception as e:
        print(f"Error descargando {ticker}: {e}")
        return None


def calculate_metrics(data):
    """
    Calcula métricas básicas de tendencia.
    """

    if data is None or data.empty:
        return None

    close = data["Close"]

    try:
        current = safe_float(close.iloc[-1])

        if current is None:
            return None

        # Últimos días disponibles
        one_week = safe_float(close.iloc[-6]) if len(close) >= 6 else None
        one_month = safe_float(close.iloc[-22]) if len(close) >= 22 else None
        three_months = (
            safe_float(close.iloc[-66])
            if len(close) >= 66
            else None
        )

        year_ago = (
            safe_float(close.iloc[0])
            if len(close) >= 2
            else None
        )

        high_52 = safe_float(close.max())
        low_52 = safe_float(close.min())

        def variation(old):
            if old is None or old == 0:
                return None

            return ((current / old) - 1) * 100

        week_change = variation(one_week)
        month_change = variation(one_month)
        three_month_change = variation(three_months)
        year_change = variation(year_ago)

        distance_high = None

        if high_52 and high_52 != 0:
            distance_high = ((current / high_52) - 1) * 100

        # Medias móviles
        ma20 = None
        ma50 = None
        ma200 = None

        if len(close) >= 20:
            ma20 = safe_float(close.tail(20).mean())

        if len(close) >= 50:
            ma50 = safe_float(close.tail(50).mean())

        if len(close) >= 200:
            ma200 = safe_float(close.tail(200).mean())

        return {
            "current": current,
            "week": week_change,
            "month": month_change,
            "three_months": three_month_change,
            "year": year_change,
            "high_52": high_52,
            "low_52": low_52,
            "distance_high": distance_high,
            "ma20": ma20,
            "ma50": ma50,
            "ma200": ma200,
        }

    except Exception as e:
        print(f"Error calculando métricas: {e}")
        return None


# ============================================================
# NOTICIAS
# ============================================================

def get_news(ticker):
    """
    Obtiene las noticias disponibles desde yfinance.

    No utiliza ninguna API de pago.
    """

    try:
        stock = yf.Ticker(ticker)

        news = stock.news

        if not news:
            return []

        results = []

        for item in news[:5]:

            try:
                content = item.get("content", item)

                title = (
                    content.get("title")
                    or item.get("title")
                    or ""
                )

                publisher = (
                    content.get("provider", {}).get("displayName")
                    if isinstance(
                        content.get("provider"),
                        dict
                    )
                    else ""
                )

                if not publisher:
                    publisher = (
                        item.get("publisher")
                        or ""
                    )

                if title:
                    results.append(
                        {
                            "title": str(title),
                            "publisher": str(publisher),
                        }
                    )

            except Exception:
                continue

        return results

    except Exception as e:
        print(f"Error obteniendo noticias de {ticker}: {e}")
        return []


# ============================================================
# ANÁLISIS
# ============================================================

def get_signal(metrics, speculative):
    """
    Genera una señal sencilla.

    Importante:
    No es una recomendación financiera profesional.

    Para especulativas:
      - Se da más peso a la tendencia.
      - Una caída fuerte no genera automáticamente VENDER.
    """

    if not metrics:
        return (
            "⚪ SIN DATOS",
            "No hay suficientes datos para analizarla."
        )

    score = 0

    week = metrics["week"] or 0
    month = metrics["month"] or 0
    three_months = metrics["three_months"] or 0
    year = metrics["year"] or 0

    current = metrics["current"]
    ma20 = metrics["ma20"]
    ma50 = metrics["ma50"]
    ma200 = metrics["ma200"]

    # --------------------------------------------------------
    # Tendencia de corto plazo
    # --------------------------------------------------------

    if week > 3:
        score += 1
    elif week < -7:
        score -= 1

    # --------------------------------------------------------
    # Tendencia mensual
    # --------------------------------------------------------

    if month > 5:
        score += 1
    elif month < -10:
        score -= 1

    # --------------------------------------------------------
    # Tendencia trimestral
    # --------------------------------------------------------

    if three_months > 8:
        score += 1
    elif three_months < -15:
        score -= 1

    # --------------------------------------------------------
    # Tendencia anual
    # --------------------------------------------------------

    if year > 10:
        score += 1
    elif year < -20:
        score -= 1

    # --------------------------------------------------------
    # Medias móviles
    # --------------------------------------------------------

    if current is not None and ma50 is not None:
        if current > ma50:
            score += 1
        else:
            score -= 1

    if current is not None and ma200 is not None:
        if current > ma200:
            score += 1
        else:
            score -= 1

    # --------------------------------------------------------
    # Posiciones especulativas
    # --------------------------------------------------------

    if speculative:

        # No se dispara "vender" solo por caída.
        if score >= 3:
            return (
                "🟢 MANTENER / ACUMULAR",
                "La tendencia reciente es favorable."
            )

        if score <= -4:
            return (
                "🟡 VIGILAR TESIS",
                "La evolución es débil. No implica vender automáticamente; "
                "conviene revisar noticias, resultados y la tesis."
            )

        return (
            "🟡 MANTENER / VIGILAR",
            "Hay señales mixtas. Mantener mientras la tesis siga intacta."
        )

    # --------------------------------------------------------
    # ETFs
    # --------------------------------------------------------

    if score >= 3:
        return (
            "🟢 MANTENER",
            "La tendencia general es favorable."
        )

    if score <= -4:
        return (
            "🟡 VIGILAR",
            "La tendencia se ha debilitado. Revisar, pero evitar "
            "decisiones impulsivas por una sola semana."
        )

    return (
        "🟢 MANTENER",
        "No aparece un cambio suficiente para modificar la estrategia."
    )


# ============================================================
# RESUMEN DE UN ACTIVO
# ============================================================

def analyze_asset(asset):
    ticker = asset["ticker"]

    print(f"Analizando {ticker}...")

    data = download_history(ticker)

    metrics = calculate_metrics(data)

    news = get_news(ticker)

    signal, explanation = get_signal(
        metrics,
        asset["speculative"],
    )

    return {
        "asset": asset,
        "metrics": metrics,
        "news": news,
        "signal": signal,
        "explanation": explanation,
    }


# ============================================================
# GENERAR INFORME
# ============================================================

def build_report(results):
    now = datetime.now(timezone.utc)

    date_text = now.strftime("%d/%m/%Y")

    lines = []

    lines.append(
        "<b>📊 INFORME SEMANAL DE TU CARTERA</b>"
    )

    lines.append(
        f"📅 {date_text}"
    )

    lines.append("")

    lines.append(
        f"<b>💶 Aportación mensual: {TOTAL_MONTHLY} €</b>"
    )

    lines.append(
        "Objetivo: crecimiento a largo plazo + "
        "pequeña parte especulativa."
    )

    lines.append("")

    # --------------------------------------------------------
    # TABLA / RESUMEN
    # --------------------------------------------------------

    lines.append("<b>📌 RESUMEN</b>")

    for result in results:

        asset = result["asset"]
        metrics = result["metrics"]

        name = asset["name"]
        monthly = asset["monthly"]
        signal = result["signal"]

        if metrics:
            week = format_percent(metrics["week"])
            month = format_percent(metrics["month"])
        else:
            week = "N/D"
            month = "N/D"

        lines.append(
            f"{signal} <b>{escape(name)}</b> "
            f"({monthly} €/mes)"
        )

        lines.append(
            f"   Semana: {week} | Mes: {month}"
        )

    lines.append("")

    # --------------------------------------------------------
    # DETALLE
    # --------------------------------------------------------

    lines.append("<b>🔎 ANÁLISIS DETALLADO</b>")

    for result in results:

        asset = result["asset"]
        metrics = result["metrics"]
        signal = result["signal"]
        explanation = result["explanation"]

        name = asset["name"]
        ticker = asset["short"]
        monthly = asset["monthly"]

        lines.append("")

        if asset["speculative"]:
            category = "ESPECULATIVA"
        else:
            category = "ETF"

        lines.append(
            f"<b>{escape(ticker)} — "
            f"{escape(name)}</b>"
        )

        lines.append(
            f"💶 Aportación: {monthly} €/mes"
        )

        lines.append(
            f"🏷️ Tipo: {category}"
        )

        if metrics:

            lines.append(
                f"💵 Precio: {format_price(metrics['current'])}"
            )

            lines.append(
                f"📅 Semana: "
                f"{format_percent(metrics['week'])}"
            )

            lines.append(
                f"📆 Mes: "
                f"{format_percent(metrics['month'])}"
            )

            lines.append(
                f"📊 3 meses: "
                f"{format_percent(metrics['three_months'])}"
            )

            lines.append(
                f"📈 1 año: "
                f"{format_percent(metrics['year'])}"
            )

            lines.append(
                f"🏔️ Distancia máximo 52 sem.: "
                f"{format_percent(metrics['distance_high'])}"
            )

            if metrics["ma50"] is not None:
                position_ma50 = (
                    "encima"
                    if metrics["current"] > metrics["ma50"]
                    else "debajo"
                )

                lines.append(
                    f"📏 Precio {position_ma50} de MA50"
                )

            if metrics["ma200"] is not None:
                position_ma200 = (
                    "encima"
                    if metrics["current"] > metrics["ma200"]
                    else "debajo"
                )

                lines.append(
                    f"📏 Precio {position_ma200} de MA200"
                )

        else:

            lines.append(
                "⚠️ No se han podido obtener datos de mercado."
            )

        lines.append("")

        lines.append(
            f"<b>{signal}</b>"
        )

        lines.append(
            f"💡 {escape(explanation)}"
        )

        # ----------------------------------------------------
        # NOTICIAS
        # ----------------------------------------------------

        news = result["news"]

        if news:

            lines.append("")
            lines.append("<b>📰 Noticias recientes:</b>")

            for item in news[:3]:

                title = escape(
                    item.get("title", "")
                )

                publisher = escape(
                    item.get("publisher", "")
                )

                if publisher:
                    lines.append(
                        f"• {title} "
                        f"<i>({publisher})</i>"
                    )
                else:
                    lines.append(
                        f"• {title}"
                    )

        else:

            lines.append("")
            lines.append(
                "📰 No se han encontrado noticias recientes."
            )

    # --------------------------------------------------------
    # PLAN DE APORTACIÓN
    # --------------------------------------------------------

    lines.append("")
    lines.append(
        "<b>💰 PLAN DE APORTACIÓN MENSUAL</b>"
    )

    lines.append(
        "🌍 VWCE: <b>80 €</b>"
    )

    lines.append(
        "📈 IWMO: <b>20 €</b>"
    )

    lines.append(
        "🚀 RKLB: <b>10 €</b>"
    )

    lines.append(
        "🛰️ ASTS: <b>8 €</b>"
    )

    lines.append(
        "🧬 TEM: <b>7 €</b>"
    )

    lines.append(
        "⚛️ IONQ: <b>5 €</b>"
    )

    lines.append(
        "━━━━━━━━━━━━━━"
    )

    lines.append(
        f"<b>TOTAL: {TOTAL_MONTHLY} €/mes</b>"
    )

    # --------------------------------------------------------
    # CONCLUSIÓN
    # --------------------------------------------------------

    lines.append("")
    lines.append(
        "<b>🧠 CONCLUSIÓN DE LA SEMANA</b>"
    )

    lines.append(
        "La estrategia base sigue siendo aportar de forma "
        "periódica y evitar decisiones impulsivas por "
        "movimientos de corto plazo."
    )

    lines.append("")

    lines.append(
        "En las posiciones especulativas, una caída de precio "
        "por sí sola NO significa vender. El punto importante "
        "es comprobar si ha cambiado la tesis de inversión."
    )

    lines.append("")

    lines.append(
        "⚠️ Este informe es informativo y utiliza reglas "
        "automáticas. No constituye asesoramiento financiero "
        "personalizado ni ejecuta operaciones."
    )

    return "\n".join(lines)


# ============================================================
# DIVIDIR MENSAJES LARGOS
# ============================================================

def split_m
