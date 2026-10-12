import importlib.util
import sys
import unittest
from unittest.mock import MagicMock, patch


for dependency in ("requests", "yfinance"):
    if importlib.util.find_spec(dependency) is None:
        sys.modules[dependency] = MagicMock()

import bot_cartera_telegram as bot


EXPECTED_HISTORICAL = {"RKLB", "ASTS", "TEM", "IONQ", "NBIS"}


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
        "last_date": "25/09/2026",
    }


class PortfolioConfigurationTests(unittest.TestCase):
    def test_historical_positions_remain_tracked_without_contributions(self):
        historical = {
            asset["ticker"]: asset
            for asset in bot.PORTFOLIO
            if asset["ticker"] in EXPECTED_HISTORICAL
        }

        self.assertEqual(set(historical), EXPECTED_HISTORICAL)
        self.assertTrue(
            all(asset["monthly"] == 0.0 for asset in historical.values())
        )

    def test_wisdomtree_etf_has_expected_identity_and_purchase_plan(self):
        wtmt = next(
            asset for asset in bot.PORTFOLIO
            if asset.get("isin") == "IE0007Z28IJ7"
        )

        self.assertEqual(wtmt["name"], "WisdomTree Tech Megatrends UCITS ETF")
        self.assertEqual(wtmt["ticker"], "WTMT.DE")
        self.assertEqual(wtmt["display_ticker"], "WTMT")
        self.assertEqual(wtmt["monthly"], 34.0)
        self.assertEqual(wtmt["purchases_per_month"], 2)
        self.assertEqual(wtmt["amount_per_purchase"], 17.0)

    def test_speculative_contributions_total_34_euros(self):
        speculative_total = sum(
            asset["monthly"]
            for asset in bot.PORTFOLIO
            if asset["type"] == "ESPECULATIVA"
        )

        self.assertEqual(speculative_total, 34.0)
        self.assertEqual(bot.SPECULATIVE_MONTHLY, 34.0)

    def test_full_portfolio_totals(self):
        etf_total = sum(
            asset["monthly"]
            for asset in bot.PORTFOLIO
            if asset["type"] == "ETF"
        )
        total = sum(asset["monthly"] for asset in bot.PORTFOLIO)

        self.assertEqual(etf_total, 110.0)
        self.assertEqual(total, 144.0)
        self.assertEqual(bot.TOTAL_MONTHLY, 144.0)


class ReportTests(unittest.TestCase):
    def test_report_keeps_historical_positions_and_adds_wisdomtree_etf(self):
        results = [
            {
                "asset": asset,
                "data": sample_market_data(),
                "news": [],
                "action": "🟢 MANTENER",
                "explanation": "Continuar.",
            }
            for asset in bot.PORTFOLIO
        ]

        report = bot.build_report(results)

        self.assertIn("CARTERA 144 €", report)
        self.assertIn("110 € ETFs de núcleo + 34 € especulativo", report)
        for ticker in EXPECTED_HISTORICAL:
            self.assertIn(f"<b>{ticker}</b>", report)
            self.assertIn(
                f"<b>{ticker}:</b> mantener la posición; "
                "sin nuevas compras periódicas.",
                report,
            )

        self.assertIn("<b>WTMT</b> — 2 compras de 17,00 € (34,00 €/mes)", report)
        self.assertIn("WisdomTree Tech Megatrends UCITS ETF", report)
        self.assertIn("ISIN IE0007Z28IJ7", report)
        self.assertIn(
            "<b>WTMT:</b> realizar 2 compras de 17 € al mes (34 €/mes).",
            report,
        )

    def test_historical_position_action_does_not_recommend_new_purchases(self):
        rklb = next(asset for asset in bot.PORTFOLIO if asset["ticker"] == "RKLB")

        action, explanation = bot.get_action(rklb, sample_market_data(), [])

        self.assertEqual(action, "🟢 MANTENER")
        self.assertIn("sin nuevas compras periódicas", explanation)


class NebiusProcessingTests(unittest.TestCase):
    @patch.object(bot, "get_news", return_value=[])
    @patch.object(bot, "get_market_data", return_value=sample_market_data())
    def test_nbis_is_processed_like_other_assets(self, market_mock, news_mock):
        nbis = next(asset for asset in bot.PORTFOLIO if asset["ticker"] == "NBIS")

        result = bot.analyze_asset(nbis)

        market_mock.assert_called_once_with("NBIS")
        news_mock.assert_called_once_with("NBIS", limit=3)
        self.assertIs(result["asset"], nbis)
        self.assertEqual(result["action"], "🟢 MANTENER")


if __name__ == "__main__":
    unittest.main()
