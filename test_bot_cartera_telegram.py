import importlib.util
import sys
import unittest
from unittest.mock import MagicMock, patch


for dependency in ("requests", "yfinance"):
    if importlib.util.find_spec(dependency) is None:
        sys.modules[dependency] = MagicMock()

import bot_cartera_telegram as bot


EXPECTED_SPECULATIVE = {
    "RKLB": 10.0,
    "ASTS": 8.0,
    "TEM": 7.0,
    "IONQ": 5.0,
    "NBIS": 5.0,
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
        "last_date": "25/09/2026",
    }


class PortfolioConfigurationTests(unittest.TestCase):
    def test_speculative_portfolio_has_exact_tickers_and_amounts(self):
        speculative = {
            asset["ticker"]: asset["monthly"]
            for asset in bot.PORTFOLIO
            if asset["type"] == "ESPECULATIVA"
        }

        self.assertEqual(speculative, EXPECTED_SPECULATIVE)
        self.assertEqual(sum(speculative.values()), 35.0)
        self.assertEqual(bot.SPECULATIVE_MONTHLY, 35.0)

    def test_full_portfolio_totals(self):
        etf_total = sum(
            asset["monthly"]
            for asset in bot.PORTFOLIO
            if asset["type"] == "ETF"
        )
        total = sum(asset["monthly"] for asset in bot.PORTFOLIO)

        self.assertEqual(etf_total, 110.0)
        self.assertEqual(total, 145.0)
        self.assertEqual(bot.TOTAL_MONTHLY, 145.0)

    def test_speculative_weights_match_monthly_amounts(self):
        expected_weights = {
            "RKLB": 10 / 35,
            "ASTS": 8 / 35,
            "TEM": 7 / 35,
            "IONQ": 5 / 35,
            "NBIS": 5 / 35,
        }

        actual_weights = {
            asset["ticker"]: asset["monthly"] / bot.SPECULATIVE_MONTHLY
            for asset in bot.PORTFOLIO
            if asset["type"] == "ESPECULATIVA"
        }

        self.assertEqual(actual_weights, expected_weights)


class ReportTests(unittest.TestCase):
    def test_report_includes_all_five_speculative_positions(self):
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

        self.assertIn("CARTERA 145 €", report)
        self.assertIn("110 € ETFs + 35 € especulativo", report)
        for ticker, amount in EXPECTED_SPECULATIVE.items():
            self.assertIn(f"<b>{ticker}</b> — {amount:.2f}".replace(".", ","), report)
            self.assertIn(f"<b>{ticker}:</b> mantener {amount:.0f} €/mes", report)


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
