import os
import html
import json
from datetime import date, datetime, timedelta, timezone
from pathlib import Path

import requests
import yfinance as yf


# ============================================================
# CONFIGURACIÓN
# ============================================================

TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN", "").strip()
CHAT_ID = os.getenv("CHAT_ID", "").strip()

TOTAL_WEEKLY = 45.0
FIRST_PURCHASE_DATE = date(2026, 11, 16)
STATE_PATH = Path(__file__).with_name("portfolio_state.json")

# ============================================================
# CARTERA SEMANAL
# ============================================================
#
# TOTAL = 45 €/semana
#

PORTFOLIO = [

    # --------------------------------------------------------
    # APORTACIONES SEMANALES
    # --------------------------------------------------------

    {
        "id": "fidelity_world",
        "name": "Fidelity MSCI World Index P EUR Acc",
        "ticker": None,
        "display_ticker": "Fidelity World",
        "isin": "IE00BYX5NX33",
        "weekly": 23.0,
        "type": "CORE",
        "role": "Núcleo global",
        "fallback_price": 14.54,
        "fallback_price_date": "2026-11-04",
        "price_source": "Último NAV conocido",
    },

    {
        "id": "vanguard_em",
        "name": "Vanguard Emerging Markets Stock Index EUR Acc",
        "ticker": None,
        "display_ticker": "Vanguard EM",
        "isin": "IE0031786696",
        "weekly": 2.0,
        "type": "CORE",
        "role": "Mercados emergentes",
        "fallback_price": 292.83,
        "fallback_price_date": "2026-11-04",
        "price_source": "Último NAV conocido",
    },

    {
        "id": "momentum",
        "name": "iShares Edge MSCI World Momentum Factor UCITS ETF USD (Acc)",
        "ticker": "IS3R.DE",
        "display_ticker": "IS3R",
        "weekly": 5.0,
        "type": "SATELLITE",
        "role": "Factor momentum",
    },

    {
        "id": "materials",
        "name": "Global X Disruptive Materials UCITS ETF USD Acc",
        "ticker": "D6AT.DE",
        "display_ticker": "D6AT",
        "isin": "IE000FP52WM7",
        "weekly": 5.0,
        "type": "SATELLITE",
        "role": "Materiales disruptivos",
    },

    {
        "id": "wtmt",
        "name": "WisdomTree Tech Megatrends UCITS ETF",
        "ticker": "WTMT.DE",
        "display_ticker": "WTMT",
        "isin": "IE0007Z28IJ7",
        "weekly": 5.0,
        "type": "SATELLITE",
        "role": "ETF temático tecnológico",
    },

    {
        "id": "bitcoin",
        "name": "Bitcoin",
        "ticker": "BTC-EUR",
        "display_ticker": "BTC",
        "weekly": 5.0,
        "type": "SATELLITE",
        "role": "Criptoactivo",
    },

    # --------------------------------------------------------
    # POSICIONES HISTÓRICAS SIN NUEVAS COMPRAS
    # --------------------------------------------------------

    {
        "id": "vwce",
        "name": "Vanguard FTSE All-World UCITS ETF USD (Acc)",
        "ticker": "VWCE.DE",
        "display_ticker": "VWCE",
        "weekly": 0.0,
        "type": "HISTORICAL",
        "role": "Núcleo global histórico",
    },

    {
        "id": "rklb",
        "name": "Rocket Lab",
        "ticker": "RKLB",
        "display_ticker": "RKLB",
        "weekly": 0.0,
        "type": "HISTORICAL",
        "role": "Espacial",
    },

    {
        "id": "asts",
        "name": "AST SpaceMobile",
        "ticker": "ASTS",
        "display_ticker": "ASTS",
        "weekly": 0.0,
        "type": "HISTORICAL",
        "role": "Satélites / conectividad",
    },

    {
        "id": "tem",
        "name": "Tempus AI",
        "ticker": "TEM",
        "display_ticker": "TEM",
        "weekly": 0.0,
        "type": "HISTORICAL",
        "role": "IA / salud",
    },

    {
        "id": "ionq",
        "name": "IonQ",
        "ticker": "IONQ",
        "display_ticker": "IONQ",
        "weekly": 0.0,
        "type": "HISTORICAL",
        "role": "Computación cuántica",
    },

    {
        "id": "nbis",
        "name": "Nebius Group",
        "ticker": "NBIS",
        "display_ticker": "NBIS",
        "weekly": 0.0,
        "type": "HISTORICAL",
        "role": "Infraestructura de IA",
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
        item["weekly"]
        for item in PORTFOLIO
    )

    if round(total, 2) != round(TOTAL_WEEKLY, 2):

        raise RuntimeError(
            f"Las aportaciones semanales suman {total:.2f} €, "
            f"pero deberían sumar {TOTAL_WEEKLY:.2f} €."
        )

    ids = [item["id"] for item in PORTFOLIO]

    if len(ids) != len(set(ids)):

        raise RuntimeError(
            "Existen identificadores de activos duplicados."
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


def weight_pct(value):

    if value is None:
        return "N/D"

    return f"{value:.2f}%"


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
# ESTADO Y ESTIMACIÓN DE CARTERA
# ============================================================

def load_state(path=STATE_PATH):

    with open(path, "r", encoding="utf-8") as handle:
        return json.load(handle)


def save_state(state, path=STATE_PATH):

    with open(path, "w", encoding="utf-8") as handle:
        json.dump(
            state,
            handle,
            ensure_ascii=False,
            indent=2,
            sort_keys=True,
        )
        handle.write("\n")


def scheduled_purchase_dates(as_of):

    if as_of < FIRST_PURCHASE_DATE:
        return []

    dates = []
    current = FIRST_PURCHASE_DATE

    while current <= as_of:
        dates.append(current)
        current += timedelta(days=7)

    return dates


def next_purchase_date(as_of):

    current = FIRST_PURCHASE_DATE

    while current <= as_of:
        current += timedelta(days=7)

    return current


def get_price_history(asset, as_of):

    if not asset.get("ticker"):
        return {
            date.fromisoformat(asset["fallback_price_date"]):
            asset["fallback_price"]
        }

    ticker = yf.Ticker(asset["ticker"])
    history = ticker.history(
        start="2026-10-27",
        end=(as_of + timedelta(days=3)).isoformat(),
        interval="1d",
        auto_adjust=True,
    )

    if history is None or history.empty:
        return {}

    prices = {}

    for timestamp, value in history["Close"].dropna().items():
        prices[timestamp.date()] = float(value)

    return prices


def closest_price(prices, target_date):

    if not prices:
        return None

    _, value = min(
        prices.items(),
        key=lambda item: abs(
            (item[0] - target_date).days
        ),
    )

    return value


def latest_price(prices, as_of):

    candidates = [
        (price_date, value)
        for price_date, value in prices.items()
        if price_date <= as_of
    ]

    if not candidates:
        return None

    return max(candidates)[1]


def purchase_price(asset, prices, purchase_date, as_of):

    if not asset.get("ticker"):
        return asset.get("fallback_price")

    candidates = [
        (price_date, value)
        for price_date, value in prices.items()
        if purchase_date <= price_date <= as_of
    ]

    if not candidates:
        return None

    return min(candidates)[1]


def concentration_status(weight):

    if weight is None:
        return "MANTENER"

    if weight >= 20:
        return "REVISAR PARA VENTA"

    if weight >= 15:
        return "REVISAR"

    return "MANTENER"


def estimate_portfolio(state, price_histories, as_of):

    baseline_date = date.fromisoformat(
        state["baseline_date"]
    )
    baseline = state["positions"]
    units = {
        key: float(value)
        for key, value in state.get(
            "estimated_units",
            {},
        ).items()
    }
    static_values = {
        key: float(value)
        for key, value in state.get(
            "static_values",
            {},
        ).items()
    }

    if not state.get("baseline_initialized"):

        for asset in PORTFOLIO:
            baseline_value = baseline.get(
                asset["id"]
            )

            if baseline_value is None:
                continue

            price = closest_price(
                price_histories.get(
                    asset["id"],
                    {},
                ),
                baseline_date,
            )

            if price:
                units[asset["id"]] = (
                    baseline_value / price
                )
            else:
                static_values[asset["id"]] = (
                    baseline_value
                )

        state["baseline_initialized"] = True

    processed = set(
        state.get("processed_purchases", [])
    )
    purchases_added = []
    missing_prices = []

    for purchase_date in scheduled_purchase_dates(as_of):

        for asset in PORTFOLIO:

            if asset["weekly"] <= 0:
                continue

            purchase_key = (
                f"{purchase_date.isoformat()}:"
                f"{asset['id']}"
            )

            if purchase_key in processed:
                continue

            price = purchase_price(
                asset,
                price_histories.get(
                    asset["id"],
                    {},
                ),
                purchase_date,
                as_of,
            )

            if not price:
                missing_prices.append(
                    purchase_key
                )
                continue

            units[asset["id"]] = (
                units.get(asset["id"], 0.0)
                + asset["weekly"] / price
            )
            processed.add(purchase_key)
            purchases_added.append(purchase_key)

    positions = {}
    total = 0.0

    for asset in PORTFOLIO:
        asset_id = asset["id"]
        current_price = latest_price(
            price_histories.get(asset_id, {}),
            as_of,
        )
        estimated_units = units.get(asset_id)

        if estimated_units is not None and current_price:
            value = estimated_units * current_price
        elif asset_id in static_values:
            value = static_values[asset_id]
        else:
            value = 0.0

        positions[asset_id] = {
            "value": value,
            "units": estimated_units,
            "price": current_price,
            "weight": None,
        }
        total += value

    if total:

        for position in positions.values():
            position["weight"] = (
                position["value"] / total * 100
            )

    state["estimated_units"] = units
    state["static_values"] = static_values
    state["processed_purchases"] = sorted(
        processed
    )
    processed_dates = [
        date.fromisoformat(item.split(":", 1)[0])
        for item in processed
    ]
    state["last_purchase_date"] = (
        max(processed_dates).isoformat()
        if processed_dates
        else None
    )

    missing_baseline = [
        asset["id"]
        for asset in PORTFOLIO
        if baseline.get(asset["id"]) is None
    ]

    return {
        "total": total,
        "positions": positions,
        "purchases_added": purchases_added,
        "missing_prices": missing_prices,
        "missing_baseline": missing_baseline,
        "incomplete": bool(
            missing_baseline or missing_prices
        ),
        "state": state,
    }


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

    if asset["weekly"] == 0:

        return (
            "MANTENER",
            "Posición histórica; sin nuevas "
            "compras periódicas ni venta automática."
        )

    week = data.get(
        "week_change"
    )

    if week is None:

        return (
            "MANTENER",
            "Precio de mercado no disponible; "
            "mantener la aportación semanal prevista."
        )

    # --------------------------------------------------------
    # NÚCLEO
    # --------------------------------------------------------

    if asset["type"] == "CORE":

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
            f"de {money(asset['weekly'])}/semana."
        )

    # --------------------------------------------------------
    # SATÉLITES
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
        f"de {money(asset['weekly'])}/semana."
    )


# ============================================================
# ANALIZAR ACTIVO
# ============================================================

def analyze_asset(asset):

    if asset.get("ticker"):

        data = get_market_data(
            asset["ticker"]
        )

        news = get_news(
            asset["ticker"],
            limit=3
        )

    else:

        data = {
            "current": asset.get("fallback_price"),
            "day_change": None,
            "week_change": None,
            "month_change": None,
            "high_3m": None,
            "low_3m": None,
            "distance_high": None,
            "distance_low": None,
            "last_date": asset.get(
                "fallback_price_date"
            ),
        }
        news = []

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

def build_report(results, estimate, as_of=None):

    now = datetime.now(timezone.utc)
    as_of = as_of or now.date()
    lines = [
        "📊 <b>INFORME SEMANAL — MODELO 45 €/SEMANA</b>",
        f"<i>{now.strftime('%d/%m/%Y %H:%M')} UTC</i>",
        "",
        "🏦 <b>APORTACIONES SEMANALES</b>",
        "",
    ]

    for asset in PORTFOLIO:

        if asset["weekly"] <= 0:
            continue

        lines.append(
            f"• <b>{html.escape(asset['display_ticker'])}</b> "
            f"— {money(asset['weekly'])}/semana"
            + (
                f" · ISIN {html.escape(asset['isin'])}"
                if asset.get("isin")
                else ""
            )
        )

    lines.extend([
        f"• <b>TOTAL — {money(TOTAL_WEEKLY)}/semana</b>",
        "<i>Fidelity y Vanguard usan el último NAV conocido "
        "del 04/11/2026; no se inventa ticker bursátil.</i>",
        "",
        "📦 <b>POSICIONES HISTÓRICAS SIN NUEVAS COMPRAS</b>",
        "",
    ])

    for asset in PORTFOLIO:

        if asset["weekly"] != 0:
            continue

        lines.append(
            f"• <b>{html.escape(asset['display_ticker'])}</b> "
            f"— mantener; aportación 0 €"
        )

    lines.extend([
        "",
        "⚖️ <b>VALOR Y PESOS ESTIMADOS</b>",
        "",
        f"Valor estimado conocido: <b>{money(estimate['total'])}</b>",
    ])

    for asset in PORTFOLIO:
        position = estimate["positions"][asset["id"]]

        if (
            position["value"] == 0
            and asset["id"] in estimate["missing_baseline"]
        ):
            lines.append(
                f"• <b>{html.escape(asset['display_ticker'])}</b> "
                f"— sin baseline inicial"
            )
            continue

        lines.append(
            f"• <b>{html.escape(asset['display_ticker'])}</b> "
            f"— {money(position['value'])} · "
            f"peso estimado {weight_pct(position['weight'])}"
        )

    if estimate["incomplete"]:
        lines.extend([
            "",
            "⚠️ Estimación incompleta: falta el valor inicial "
            "de BTC o alguna cotización. No se inventa ese valor.",
        ])

    lines.extend([
        "",
        "🚦 <b>ALERTAS DE CONCENTRACIÓN</b>",
        "",
    ])

    for asset in PORTFOLIO:

        if asset["type"] != "SATELLITE":
            continue

        weight = estimate["positions"][asset["id"]]["weight"]
        status = concentration_status(weight)
        lines.append(
            f"• <b>{html.escape(asset['display_ticker'])}</b>: "
            f"{status} ({weight_pct(weight)})"
        )

    next_date = next_purchase_date(as_of)
    lines.extend([
        "",
        "📅 <b>PRÓXIMA COMPRA PREVISTA</b>",
        "",
        f"Lunes {next_date.strftime('%d/%m/%Y')}.",
        "Si no hay cotización válida, se usa el siguiente "
        "día hábil disponible.",
        "",
        "📈 <b>SEGUIMIENTO DE MERCADO</b>",
        "",
    ])

    for result in results:
        asset = result["asset"]
        data = result["data"]
        lines.append(
            f"• <b>{html.escape(asset['display_ticker'])}</b> "
            f"— {result['action']} · semana "
            f"{pct(data['week_change'])}"
        )

    news_count = 0
    news_lines = []

    for result in results:
        asset = result["asset"]

        for item in result["news"][:1]:
            title = html.escape(item["title"])
            publisher = html.escape(item["publisher"])

            if item["link"]:
                safe_link = html.escape(
                    item["link"],
                    quote=True,
                )
                news_lines.append(
                    f"• <a href=\"{safe_link}\">{title}</a> "
                    f"({publisher}) — {asset['display_ticker']}"
                )
            else:
                news_lines.append(
                    f"• {title} ({publisher}) "
                    f"— {asset['display_ticker']}"
                )

            news_count += 1

    if news_count:
        lines.extend([
            "",
            "📰 <b>NOTICIAS DESTACADAS</b>",
            "",
            *news_lines,
        ])

    lines.extend([
        "",
        "ℹ️ <i>Los valores y pesos son estimados y pueden "
        "diferir de Trade Republic. Las alertas son de "
        "vigilancia: el bot no ejecuta compras ni ventas.</i>",
    ])

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

    as_of = datetime.now(
        timezone.utc
    ).date()
    state = load_state()
    price_histories = {}

    for asset in PORTFOLIO:

        try:
            price_histories[asset["id"]] = (
                get_price_history(asset, as_of)
            )
        except Exception as exc:
            price_histories[asset["id"]] = {}
            print(
                f"Histórico no disponible para "
                f"{asset['display_ticker']}: {exc}"
            )

    estimate = estimate_portfolio(
        state,
        price_histories,
        as_of,
    )

    print(
        "Compras teóricas nuevas procesadas: "
        f"{len(estimate['purchases_added'])}"
    )
    print(
        "Próxima compra programada: "
        f"{next_purchase_date(as_of).strftime('%d/%m/%Y')}"
    )

    print(
        f"Aportación semanal: "
        f"{TOTAL_WEEKLY:.0f} €"
    )

    print("Activos:")

    for asset in PORTFOLIO:

        print(
            f"  "
            f"{asset['display_ticker']}: "
            f"{asset['weekly']:.0f} €/semana "
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
        results,
        estimate,
        as_of,
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

    save_state(estimate["state"])

    print(
        "Informe enviado correctamente."
    )

    print("=" * 60)


# ============================================================
# EJECUCIÓN
# ============================================================

if __name__ == "__main__":

    main()
