import copy
import importlib.util
import sys
import unittest
from datetime import date
from unittest.mock import MagicMock, patch


for dependency in ("requests", "yfinance"):
    if importlib.util.find_spec(dependency) is None:
        sys.modules[dependency] = MagicMock()

import bot_cartera_telegram as bot


EXPECTED_WEEKLY = {
    "fidelity_world": 23.0,
    "vanguard_em": 2.0,
    "momentum": 5.0,
    "materials": 5.0,
    "wtmt": 5.0,
    "bitcoin": 5.0,
}
EXPECTED_HISTORICAL = {
    "vwce",
    "rklb",
    "asts",
    "tem",
    "ionq",
    "nbis",
}


def sample_market_data():
    return {
        "current": 10.0,
        "day_change": 1.0,
        "week_change": 2.0,
        "month_change": 3.0,
        "high_3m": 12.0,
        "low_3m": 8.0,
        "distance_high": -16.67,
        "distance_low": 25.0,
        "last_date": "05/11/2026",
    }


def fresh_state():
    return copy.deepcopy(bot.load_state())


def sample_histories():
    prices = {}

    for asset in bot.PORTFOLIO:
        prices[asset["id"]] = {
            date(2026, 11, 5): 10.0,
            date(2026, 11, 6): 10.0,
            date(2026, 11, 16): 10.0,
        }

    return prices


class PortfolioConfigurationTests(unittest.TestCase):
    def test_weekly_allocations_total_45_euros(self):
        active = {
            asset["id"]: asset["weekly"]
            for asset in bot.PORTFOLIO
            if asset["weekly"] > 0
        }

        self.assertEqual(active, EXPECTED_WEEKLY)
        self.assertEqual(sum(active.values()), 45.0)
        self.assertEqual(bot.TOTAL_WEEKLY, 45.0)

    def test_historical_positions_remain_with_zero_contribution(self):
        historical = {
            asset["id"]: asset["weekly"]
            for asset in bot.PORTFOLIO
            if asset["id"] in EXPECTED_HISTORICAL
        }

        self.assertEqual(set(historical), EXPECTED_HISTORICAL)
        self.assertTrue(all(value == 0 for value in historical.values()))

    def test_fund_isins_have_no_invented_market_ticker(self):
        fidelity = next(a for a in bot.PORTFOLIO if a["id"] == "fidelity_world")
        vanguard = next(a for a in bot.PORTFOLIO if a["id"] == "vanguard_em")

        self.assertEqual(fidelity["isin"], "IE00BYX5NX33")
        self.assertEqual(vanguard["isin"], "IE0031786696")
        self.assertIsNone(fidelity["ticker"])
        self.assertIsNone(vanguard["ticker"])
        self.assertGreater(fidelity["fallback_price"], 0)
        self.assertGreater(vanguard["fallback_price"], 0)

    def test_baseline_visible_total_is_389_71(self):
        state = fresh_state()
        known_total = sum(
            value
            for value in state["positions"].values()
            if value is not None
        )

        self.assertAlmostEqual(known_total, 389.71, places=2)
        self.assertEqual(state["visible_total"], 389.71)
        self.assertIsNone(state["positions"]["bitcoin"])


class ScheduleAndEstimationTests(unittest.TestCase):
    def test_first_purchase_is_16_november_and_subsequent_are_mondays(self):
        self.assertEqual(bot.scheduled_purchase_dates(date(2026, 11, 15)), [])
        dates = bot.scheduled_purchase_dates(date(2026, 12, 7))

        self.assertEqual(dates[0], date(2026, 11, 16))
        self.assertEqual(
            dates,
            [
                date(2026, 11, 16),
                date(2026, 11, 23),
                date(2026, 11, 30),
                date(2026, 12, 7),
            ],
        )
        self.assertTrue(all(value.weekday() == 0 for value in dates))

    def test_known_baseline_weights_are_calculated(self):
        estimate = bot.estimate_portfolio(
            fresh_state(),
            sample_histories(),
            date(2026, 11, 6),
        )

        self.assertAlmostEqual(estimate["total"], 389.71, places=2)
        expected = 250.57 / 389.71 * 100
        self.assertAlmostEqual(
            estimate["positions"]["vwce"]["weight"],
            expected,
            places=6,
        )

    def test_missing_bitcoin_baseline_does_not_break_estimation(self):
        estimate = bot.estimate_portfolio(
            fresh_state(),
            sample_histories(),
            date(2026, 11, 6),
        )

        self.assertTrue(estimate["incomplete"])
        self.assertIn("bitcoin", estimate["missing_baseline"])
        self.assertEqual(estimate["positions"]["bitcoin"]["value"], 0.0)

    def test_weekly_purchase_is_idempotent_by_date_and_asset(self):
        state = fresh_state()
        histories = sample_histories()
        first = bot.estimate_portfolio(
            state,
            histories,
            date(2026, 11, 16),
        )
        units_after_first = copy.deepcopy(first["state"]["estimated_units"])
        second = bot.estimate_portfolio(
            first["state"],
            histories,
            date(2026, 11, 16),
        )

        self.assertEqual(len(first["purchases_added"]), 6)
        self.assertEqual(second["purchases_added"], [])
        self.assertEqual(second["state"]["estimated_units"], units_after_first)
        self.assertEqual(len(second["state"]["processed_purchases"]), 6)

    def test_concentration_thresholds(self):
        self.assertEqual(bot.concentration_status(14.99), "MANTENER")
        self.assertEqual(bot.concentration_status(15.0), "REVISAR")
        self.assertEqual(bot.concentration_status(19.99), "REVISAR")
        self.assertEqual(bot.concentration_status(20.0), "REVISAR PARA VENTA")


class ReportTests(unittest.TestCase):
    def test_report_contains_weekly_plan_weights_and_historical_positions(self):
        results = [
            {
                "asset": asset,
                "data": sample_market_data(),
                "news": [],
                "action": "MANTENER",
                "explanation": "Continuar.",
            }
            for asset in bot.PORTFOLIO
        ]
        estimate = bot.estimate_portfolio(
            fresh_state(),
            sample_histories(),
            date(2026, 11, 6),
        )

        report = bot.build_report(results, estimate, date(2026, 11, 6))

        self.assertIn("MODELO 45 €/SEMANA", report)
        self.assertIn("Fidelity World</b> — 23,00 €/semana", report)
        self.assertIn("Vanguard EM</b> — 2,00 €/semana", report)
        self.assertIn("D6AT</b> — 5,00 €/semana", report)
        self.assertIn("WTMT</b> — 5,00 €/semana", report)
        self.assertIn("BTC</b> — 5,00 €/semana", report)
        self.assertIn("Valor estimado conocido: <b>389,71 €</b>", report)
        self.assertIn("peso estimado", report)
        self.assertIn("Lunes 16/11/2026", report)
        self.assertIn("falta el valor inicial de BTC", report)

        for asset_id in EXPECTED_HISTORICAL:
            asset = next(a for a in bot.PORTFOLIO if a["id"] == asset_id)
            self.assertIn(
                f"<b>{asset['display_ticker']}</b> — mantener; aportación 0 €",
                report,
            )

    def test_historical_action_never_recommends_automatic_sale(self):
        rklb = next(asset for asset in bot.PORTFOLIO if asset["id"] == "rklb")
        data = sample_market_data()
        data["week_change"] = -35.0

        action, explanation = bot.get_action(rklb, data, [])

        self.assertEqual(action, "MANTENER")
        self.assertIn("sin nuevas compras", explanation)
        self.assertIn("venta automática", explanation)


class MarketProcessingTests(unittest.TestCase):
    @patch.object(bot, "get_news", return_value=[])
    @patch.object(bot, "get_market_data", return_value=sample_market_data())
    def test_nebius_still_uses_market_tracking(self, market_mock, news_mock):
        nbis = next(asset for asset in bot.PORTFOLIO if asset["id"] == "nbis")

        result = bot.analyze_asset(nbis)

        market_mock.assert_called_once_with("NBIS")
        news_mock.assert_called_once_with("NBIS", limit=3)
        self.assertEqual(result["action"], "MANTENER")

    def test_fund_without_ticker_uses_fallback_nav(self):
        fidelity = next(a for a in bot.PORTFOLIO if a["id"] == "fidelity_world")

        result = bot.analyze_asset(fidelity)

        self.assertEqual(result["data"]["current"], 14.54)
        self.assertEqual(result["data"]["last_date"], "2026-11-04")
        self.assertEqual(result["news"], [])


if __name__ == "__main__":
    unittest.main()
