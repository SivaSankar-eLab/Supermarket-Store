"""
Tests for finalize_bill idempotency.

The idempotency_key must:
  1. Allow duplicate calls to return the CACHED result (not re-run side effects)
  2. Stock must be deducted exactly ONCE regardless of how many retries are made
  3. A different bill with the same key must be rejected
"""
import pytest

from tests.conftest import create_test_product


@pytest.mark.asyncio
async def test_idempotent_finalize_same_key_returns_cached():
    """
    Calling finalize_bill twice with the same idempotency_key must:
    - Both return ok=True
    - Second call must return {"idempotent": True}
    - Same grand_total in both responses
    """
    from app.tools.billing import start_bill, add_bill_item, finalize_bill

    product = await create_test_product(qty_on_hand=20.0)
    pid = product["id"]
    idem_key = "test-idem-001"

    bill = (await start_bill())["data"]["bill"]
    bid = bill["id"]
    await add_bill_item(bid, pid, 2.0)

    # First call
    r1 = await finalize_bill(bid, "CASH", idem_key)
    assert r1["ok"], f"First call failed: {r1}"
    gt1 = r1["data"]["totals"]["grand_total"]

    # Second call — same bill_id, same key
    r2 = await finalize_bill(bid, "CASH", idem_key)
    assert r2["ok"], f"Second call failed: {r2}"
    assert r2["data"].get("idempotent") is True, "Should be flagged as idempotent"
    gt2 = r2["data"]["bill"]["grand_total"]

    assert gt1 == gt2, "Grand total should be identical on idempotent retry"


@pytest.mark.asyncio
async def test_idempotent_finalize_stock_deducted_exactly_once():
    """
    After two finalize_bill calls with the same key, stock must be deducted only once.
    """
    from app.tools.billing import start_bill, add_bill_item, finalize_bill
    from app.tools.inventory import get_stock

    product = await create_test_product(qty_on_hand=10.0)
    pid = product["id"]
    idem_key = "test-idem-stock-001"

    bill = (await start_bill())["data"]["bill"]
    bid = bill["id"]
    await add_bill_item(bid, pid, 3.0)

    # Call twice
    r1 = await finalize_bill(bid, "CASH", idem_key)
    assert r1["ok"]
    r2 = await finalize_bill(bid, "CASH", idem_key)
    assert r2["ok"]

    # Stock should be 10 - 3 = 7, NOT 10 - 6 = 4
    stock = await get_stock(pid)
    actual_qty = stock["data"]["product"]["qty_on_hand"]
    assert actual_qty == 7.0, (
        f"Stock deducted twice! Expected 7.0, got {actual_qty}. "
        "Idempotency failed."
    )


@pytest.mark.asyncio
async def test_duplicate_key_different_bill_rejected():
    """
    A different bill with an already-used idempotency_key must return the cached
    result of the ORIGINAL bill — not finalize the new bill.
    """
    from app.tools.billing import start_bill, add_bill_item, finalize_bill
    from app.tools.inventory import get_stock

    p1 = await create_test_product(name="Salt", qty_on_hand=50.0)
    p2 = await create_test_product(name="Sugar", qty_on_hand=50.0, sell_price=40.0)
    idem_key = "shared-key-001"

    # First bill
    bill1 = (await start_bill())["data"]["bill"]
    await add_bill_item(bill1["id"], p1["id"], 1.0)
    r1 = await finalize_bill(bill1["id"], "CASH", idem_key)
    assert r1["ok"]

    # Second bill with SAME key
    bill2 = (await start_bill())["data"]["bill"]
    await add_bill_item(bill2["id"], p2["id"], 5.0)
    r2 = await finalize_bill(bill2["id"], "CASH", idem_key)

    # Should return cached result (idempotent hit) NOT finalize bill2
    assert r2["ok"]
    assert r2["data"].get("idempotent") is True

    # Bill2's product stock should be UNCHANGED
    s2 = await get_stock(p2["id"])
    assert s2["data"]["product"]["qty_on_hand"] == 50.0, (
        f"Bill2 was incorrectly finalized! Stock: {s2['data']['product']['qty_on_hand']}"
    )


@pytest.mark.asyncio
async def test_multiple_concurrent_idempotent_keys_all_succeed():
    """Each unique key finalizes successfully — uniqueness constraint works."""
    import asyncio
    from app.tools.billing import start_bill, add_bill_item, finalize_bill

    product = await create_test_product(qty_on_hand=100.0)
    pid = product["id"]

    async def make_bill(n: int):
        bill = (await start_bill())["data"]["bill"]
        await add_bill_item(bill["id"], pid, 1.0)
        return await finalize_bill(bill["id"], "CASH", f"unique-key-{n}")

    results = await asyncio.gather(*[make_bill(i) for i in range(5)])
    for i, r in enumerate(results):
        assert r["ok"], f"Bill {i} failed: {r}"


@pytest.mark.asyncio
async def test_idempotency_key_uniqueness_enforced_at_db():
    """
    Verify that bills.idempotency_key has a UNIQUE constraint at the DB level.
    (This protects against application-level bugs bypassing the check.)
    """
    from sqlalchemy import text
    from app.database import get_db

    async with get_db() as db:
        # Check the unique constraint exists
        result = await db.execute(
            text("""
                SELECT constraint_name
                FROM information_schema.table_constraints
                WHERE table_name = 'bills'
                  AND constraint_type = 'UNIQUE'
                  AND constraint_name LIKE '%idempotency%'
            """)
        )
        constraints = result.fetchall()

    assert len(constraints) >= 1, (
        "bills.idempotency_key UNIQUE constraint not found in DB! "
        "This is a critical safety mechanism."
    )
