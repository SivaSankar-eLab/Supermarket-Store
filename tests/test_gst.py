"""
Tests for GST calculation correctness.

These are pure unit tests — no DB needed.
Edge cases: zero slab, high-value rounding, loose items with fractional qty.
"""
from decimal import Decimal

import pytest

from app.tools.gst_utils import compute_gst_line, compute_bill_totals, GSTLine


class TestComputeGSTLine:
    """Unit tests for per-line GST computation."""

    def test_zero_gst_slab(self):
        """0% slab: taxable == line_total, CGST == SGST == 0."""
        line = compute_gst_line(qty=2, unit_price=50, gst_slab=0)
        assert line.taxable_value == Decimal("100.00")
        assert line.cgst_amt == Decimal("0.00")
        assert line.sgst_amt == Decimal("0.00")
        assert line.line_total == Decimal("100.00")

    def test_five_percent_slab(self):
        """5% slab: CGST = SGST = 2.5% each."""
        line = compute_gst_line(qty=1, unit_price=100, gst_slab=5)
        assert line.taxable_value == Decimal("100.00")
        assert line.cgst_amt == Decimal("2.50")
        assert line.sgst_amt == Decimal("2.50")
        assert line.line_total == Decimal("105.00")

    def test_twelve_percent_slab(self):
        """12% slab: CGST = SGST = 6% each."""
        line = compute_gst_line(qty=1, unit_price=200, gst_slab=12)
        assert line.taxable_value == Decimal("200.00")
        assert line.cgst_amt == Decimal("12.00")
        assert line.sgst_amt == Decimal("12.00")
        assert line.line_total == Decimal("224.00")

    def test_eighteen_percent_slab(self):
        """18% slab: CGST = SGST = 9% each."""
        line = compute_gst_line(qty=2, unit_price=150, gst_slab=18)
        assert line.taxable_value == Decimal("300.00")
        assert line.cgst_amt == Decimal("27.00")
        assert line.sgst_amt == Decimal("27.00")
        assert line.line_total == Decimal("354.00")

    def test_twentyeight_percent_slab(self):
        """28% slab: CGST = SGST = 14% each."""
        line = compute_gst_line(qty=1, unit_price=500, gst_slab=28)
        assert line.taxable_value == Decimal("500.00")
        assert line.cgst_amt == Decimal("70.00")
        assert line.sgst_amt == Decimal("70.00")
        assert line.line_total == Decimal("640.00")

    def test_fractional_qty_rounding(self):
        """Fractional quantity with 5% GST — ROUND_HALF_UP applied."""
        # 0.333kg × ₹90 = ₹29.97 taxable
        # CGST = 29.97 × 0.025 = 0.74925 → rounds to ₹0.75
        line = compute_gst_line(qty="0.333", unit_price="90", gst_slab=5)
        assert line.taxable_value == Decimal("29.97")
        assert line.cgst_amt == Decimal("0.75")
        assert line.sgst_amt == Decimal("0.75")
        assert line.line_total == Decimal("31.47")

    def test_large_quantity_precision(self):
        """High-value transaction — no floating point drift."""
        line = compute_gst_line(qty=1000, unit_price="99.99", gst_slab=18)
        assert line.taxable_value == Decimal("99990.00")
        assert line.cgst_amt == Decimal("8999.10")
        assert line.sgst_amt == Decimal("8999.10")
        assert line.line_total == Decimal("117988.20")

    def test_string_inputs_accepted(self):
        """Tool inputs may come as strings — should handle gracefully."""
        line = compute_gst_line(qty="2.5", unit_price="40.00", gst_slab="5")
        assert line.taxable_value == Decimal("100.00")
        assert line.cgst_amt == Decimal("2.50")

    def test_cgst_equals_sgst(self):
        """CGST must always equal SGST for intra-state supply."""
        for slab in [0, 5, 12, 18, 28]:
            line = compute_gst_line(qty=3, unit_price=77.77, gst_slab=slab)
            assert line.cgst_amt == line.sgst_amt, f"CGST != SGST at slab {slab}%"


class TestComputeBillTotals:
    """Unit tests for bill-level totals and round-off."""

    def _make_line(self, taxable: str, cgst: str, sgst: str) -> GSTLine:
        tax = Decimal(taxable)
        c = Decimal(cgst)
        s = Decimal(sgst)
        return GSTLine(
            qty=Decimal("1"),
            unit_price=tax,
            gst_slab=Decimal("5"),
            taxable_value=tax,
            cgst_amt=c,
            sgst_amt=s,
            line_total=tax + c + s,
        )

    def test_round_off_positive(self):
        """Grand total is rounded UP — round_off should be positive."""
        # Raw total: 105.50 → grand_total: 106 → round_off: +0.50
        lines = [self._make_line("100.00", "2.75", "2.75")]  # raw = 105.50
        totals = compute_bill_totals(lines)
        assert totals.subtotal == Decimal("100.00")
        assert totals.cgst_total == Decimal("2.75")
        assert totals.sgst_total == Decimal("2.75")
        # raw = 105.50, rounds to 106
        assert totals.grand_total == Decimal("106.00")
        assert totals.round_off == Decimal("0.50")

    def test_round_off_negative(self):
        """Grand total is rounded DOWN — round_off should be negative."""
        # raw = 105.30 → grand_total: 105 → round_off: -0.30
        lines = [self._make_line("100.00", "2.65", "2.65")]  # raw = 105.30
        totals = compute_bill_totals(lines)
        assert totals.grand_total == Decimal("105.00")
        assert totals.round_off == Decimal("-0.30")

    def test_round_off_zero(self):
        """Exact rupee — no rounding needed."""
        lines = [self._make_line("100.00", "2.50", "2.50")]  # raw = 105.00
        totals = compute_bill_totals(lines)
        assert totals.grand_total == Decimal("105.00")
        assert totals.round_off == Decimal("0.00")

    def test_multiple_lines_different_slabs(self):
        """Multi-line bill sums correctly."""
        lines = [
            compute_gst_line(2, 50, 5),    # 100 taxable, 5% GST
            compute_gst_line(1, 200, 12),  # 200 taxable, 12% GST
            compute_gst_line(3, 30, 0),    # 90 taxable, 0% GST
        ]
        totals = compute_bill_totals(lines)
        assert totals.subtotal == Decimal("390.00")
        # 5% on 100: CGST=2.50+SGST=2.50; 12% on 200: CGST=12.00+SGST=12.00; 0% on 90
        assert totals.cgst_total == Decimal("14.50")
        assert totals.sgst_total == Decimal("14.50")
        # raw = 419.00, grand_total = 419.00
        assert totals.grand_total == Decimal("419.00")

    def test_empty_lines(self):
        """Empty bill returns all zeros."""
        totals = compute_bill_totals([])
        assert totals.grand_total == Decimal("0.00")
        assert totals.subtotal == Decimal("0.00")
