import importlib.util
import json
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SPEC = importlib.util.spec_from_file_location("update_market", ROOT / "work" / "update_market.py")
MODEL = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(MODEL)


class ModelRulesTest(unittest.TestCase):
    def test_leveraged_and_inverse_etf_are_not_long_term_eligible(self):
        for code, name in [("00631L", "元大台灣50正2"), ("00632R", "元大台灣50反1"), ("00635U", "期元大S&P黃金")]:
            self.assertFalse(MODEL.is_long_term_etf({"asset_type": "ETF", "code": code, "name": name, "industry": "ETF"}))

    def test_plain_etf_is_long_term_eligible(self):
        self.assertTrue(MODEL.is_long_term_etf({"asset_type": "ETF", "code": "0050", "name": "元大台灣50", "industry": "股票／資產 ETF"}))

    def test_financial_industry_detection(self):
        self.assertTrue(MODEL.is_financial({"industry": "金融保險業"}))
        self.assertFalse(MODEL.is_financial({"industry": "半導體業"}))

    def test_generated_payload_has_required_contract(self):
        payload = json.loads((ROOT / "outputs" / "market-data.json").read_text(encoding="utf-8"))
        self.assertTrue(payload["stocks"])
        self.assertEqual(payload["model_version"], "2.0.0")
        self.assertIn("market_filter", payload)
        self.assertIn("confidence", payload)
        self.assertIn("data_quality", payload)
        self.assertTrue(payload["data_quality"]["adjusted_prices"])
        self.assertLessEqual(payload["data_quality"]["price_history_days"], 300)
        self.assertGreaterEqual(payload["confidence"]["validation"]["periods"], 1)


if __name__ == "__main__":
    unittest.main()
