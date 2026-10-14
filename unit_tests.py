"""Model-free tests for the deterministic tool and human-gate safeguards."""
import unittest
from agent import lookup_order, calculate_refund, request_refund

class ToolSafetyTests(unittest.TestCase):
    def test_known_order(self):
        self.assertTrue(lookup_order("ORD-1001")["ok"])
    def test_unknown_order_rejected(self):
        self.assertFalse(lookup_order("ORD-9999")["ok"])
    def test_refund_calculation_no_transaction(self):
        result = calculate_refund("ORD-1001", 10)
        self.assertTrue(result["ok"])
        self.assertIn("no transaction", result["note"])
    def test_amount_above_eligibility_rejected(self):
        self.assertFalse(calculate_refund("ORD-1002", 25)["ok"])
    def test_amount_over_global_limit_rejected(self):
        self.assertFalse(calculate_refund("ORD-1001", 5001)["ok"])
    def test_denial_does_not_execute(self):
        result = request_refund("ORD-1001", 10, "damaged", approval="n", interactive=False)
        self.assertFalse(result["executed"])
        self.assertEqual(result["status"], "denied")
    def test_approval_executes_mock_only(self):
        result = request_refund("ORD-1001", 10, "damaged", approval="y", interactive=False)
        self.assertTrue(result["executed"])
        self.assertIn("no real money moved", result["message"])
    def test_invalid_amount_cannot_execute_even_if_approved(self):
        result = request_refund("ORD-1001", 999, "damaged", approval="y", interactive=False)
        self.assertFalse(result["executed"])

if __name__ == "__main__":
    unittest.main(verbosity=2)
