"""
KiranaBot — GST Calculation Utilities

All monetary arithmetic uses Python Decimal with ROUND_HALF_UP.
These functions are unit-tested in tests/test_gst.py.
"""
from decimal import Decimal, ROUND_HALF_UP
from dataclasses import dataclass


TWO_DP = Decimal("0.01")
THREE_DP = Decimal("0.001")


@dataclass
class GSTLine:
    qty: Decimal
    unit_price: Decimal
    gst_slab: Decimal        # 0 / 5 / 12 / 18 / 28
    taxable_value: Decimal
    cgst_amt: Decimal
    sgst_amt: Decimal
    line_total: Decimal


@dataclass
class BillTotals:
    subtotal: Decimal
    cgst_total: Decimal
    sgst_total: Decimal
    round_off: Decimal
    grand_total: Decimal     # nearest rupee


def compute_gst_line(
    qty: Decimal | float | str,
    unit_price: Decimal | float | str,
    gst_slab: Decimal | float | str,
) -> GSTLine:
    """
    Compute a single bill-item's GST breakdown.

    Formula (intra-state supply, split equally into CGST + SGST):
        taxable  = qty × unit_price                        → 2 dp
        cgst     = taxable × (slab / 2) / 100             → 2 dp, ROUND_HALF_UP
        sgst     = cgst                                    (always equal)
        line_total = taxable + cgst + sgst
    """
    qty = Decimal(str(qty))
    unit_price = Decimal(str(unit_price))
    gst_slab = Decimal(str(gst_slab))

    taxable = (qty * unit_price).quantize(TWO_DP, rounding=ROUND_HALF_UP)
    half_rate = gst_slab / Decimal("200")          # slab/2/100
    cgst = (taxable * half_rate).quantize(TWO_DP, rounding=ROUND_HALF_UP)
    sgst = cgst                                     # intra-state: CGST == SGST
    line_total = taxable + cgst + sgst

    return GSTLine(
        qty=qty,
        unit_price=unit_price,
        gst_slab=gst_slab,
        taxable_value=taxable,
        cgst_amt=cgst,
        sgst_amt=sgst,
        line_total=line_total,
    )


def compute_bill_totals(lines: list[GSTLine]) -> BillTotals:
    """
    Sum all lines and compute the single rupee-rounding adjustment.
    grand_total = round(raw_total) — nearest rupee.
    round_off   = grand_total - raw_total  (can be +ve or -ve paise)
    """
    subtotal = sum((ln.taxable_value for ln in lines), Decimal("0")).quantize(TWO_DP)
    cgst_total = sum((ln.cgst_amt for ln in lines), Decimal("0")).quantize(TWO_DP)
    sgst_total = sum((ln.sgst_amt for ln in lines), Decimal("0")).quantize(TWO_DP)
    raw_total = subtotal + cgst_total + sgst_total
    grand_total = Decimal(str(round(raw_total))).quantize(TWO_DP)
    round_off = (grand_total - raw_total).quantize(TWO_DP)

    return BillTotals(
        subtotal=subtotal,
        cgst_total=cgst_total,
        sgst_total=sgst_total,
        round_off=round_off,
        grand_total=grand_total,
    )
