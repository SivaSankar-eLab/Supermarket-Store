"""
KiranaBot — Seed Data Script

Creates a realistic set of products, customers, and some initial stock
for manual testing and demo recordings.

Usage:
    python scripts/seed_data.py
"""
import asyncio
import os
import sys

# Add project root to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

os.environ.setdefault("APP_ENV", "development")


async def seed():
    from app.tools.inventory import add_product, find_product, receive_stock
    from app.tools.credit import add_customer
    from app.tools.preferences import set_preference
    from app.database import get_db
    from app.models import Shop
    from app.config import get_settings
    import uuid
    from sqlalchemy import select

    settings = get_settings()
    shop_id = uuid.UUID(settings.shop_id)

    # Ensure shop exists
    async with get_db() as db:
        result = await db.execute(select(Shop).where(Shop.id == shop_id))
        shop = result.scalar_one_or_none()
        if not shop:
            shop = Shop(
                id=shop_id,
                name=settings.shop_name,
                owner_name=settings.shop_owner_name,
                gstin=settings.shop_gstin or None,
                address=settings.shop_address or None,
            )
            db.add(shop)

    print("Seeding SupermarketBot...")

    # ── Preferences ────────────────────────────────────────────────────────
    prefs = [
        ("shop_name", "Sharma Supermarket Store"),
        ("owner_name", "Rajesh Sharma"),
        ("gstin", "27AABCU9603R1ZX"),
        ("address", "123 MG Road, Near Bus Stand, Mumbai - 400001"),
        ("invoice_footer", "Thank you for shopping with us! Come again."),
        ("timezone", "Asia/Kolkata"),
    ]
    for key, val in prefs:
        await set_preference(key, val)
    print("  Preferences set")

    # ── Products ────────────────────────────────────────────────────────────
    products = [
        # name, brand, unit, gst_slab, cost, sell, qty, reorder, is_loose, hsn
        ("Atta", "Aashirvaad", "kg", 5, 42.0, 50.0, 100.0, 20.0, True, "1101"),
        ("Basmati Rice", "India Gate", "kg", 5, 65.0, 80.0, 80.0, 15.0, True, "1006"),
        ("Toor Dal", "Tata Sampann", "kg", 5, 85.0, 100.0, 60.0, 10.0, True, "0713"),
        ("Sunflower Oil", "Saffola", "l", 5, 130.0, 155.0, 30.0, 5.0, False, "1512"),
        ("Groundnut Oil", "Fortune", "l", 5, 140.0, 165.0, 25.0, 5.0, False, "1508"),
        ("Sugar", "Local", "kg", 5, 38.0, 45.0, 75.0, 15.0, True, "1701"),
        ("Salt", "Tata", "kg", 0, 10.0, 15.0, 50.0, 10.0, True, "2501"),
        ("Turmeric", "MDH", "g", 5, 0.12, 0.18, 5000.0, 500.0, True, "0910"),
        ("Milk", "Amul", "l", 5, 52.0, 58.0, 40.0, 10.0, False, "0401"),
        ("Butter", "Amul", "pkt", 12, 55.0, 65.0, 20.0, 5.0, False, "0405"),
        ("Detergent", "Surf Excel", "pkt", 18, 85.0, 98.0, 25.0, 5.0, False, "3402"),
        ("Soap", "Dettol", "pc", 18, 30.0, 38.0, 50.0, 10.0, False, "3401"),
        ("Biscuits", "Parle G", "pkt", 18, 5.0, 7.0, 100.0, 20.0, False, "1905"),
        ("Chips", "Lays", "pkt", 18, 18.0, 25.0, 40.0, 10.0, False, "2008"),
        ("Maggi Noodles", "Nestle", "pkt", 18, 12.0, 16.0, 60.0, 15.0, False, "1902"),
    ]

    for name, brand, unit, gst_slab, cost, sell, qty, reorder, is_loose, hsn in products:
        result = await add_product(
            name=name,
            brand=brand,
            unit=unit,
            gst_slab=gst_slab,
            cost_price=cost,
            sell_price=sell,
            initial_qty=qty,
            reorder_level=reorder,
            is_loose=is_loose,
            hsn_code=hsn,
        )
        if result["ok"]:
            print(f"  Added {brand} {name} - {qty}{unit} @ Rs{sell}")
        else:
            # If already exists, top up stock if depleted
            f_prod = await find_product(f"{brand} {name}")
            if f_prod.get("ok") and f_prod["data"].get("candidates"):
                p_cand = f_prod["data"]["candidates"][0]
                if float(p_cand.get("qty_on_hand", 0)) < 10.0:
                    await receive_stock(
                        product_id=p_cand["id"],
                        qty=qty,
                        cost_price=cost,
                        note="Seed data stock replenishment",
                    )
                    print(f"  Replenished {brand} {name} stock (+{qty}{unit})")
                else:
                    print(f"  {brand} {name} already exists with {p_cand.get('qty_on_hand')}{unit} stock")
            else:
                print(f"  Failed {brand} {name}: {result.get('message')}")

    # ── Customers ────────────────────────────────────────────────────────────
    customers = [
        ("Ravi Kumar", "9876543210"),
        ("Sunita Devi", "9876543211"),
        ("Mohammed Ali", "9876543212"),
        ("Priya Sharma", "9876543213"),
        ("Ramesh Patel", "9876543214"),
    ]
    for name, phone in customers:
        result = await add_customer(name, phone)
        if result["ok"]:
            print(f"  Added customer: {name} ({phone})")
        else:
            print(f"  Failed {name}: {result.get('message')}")

    print("\nSeed complete! Start the bot and test away.")


if __name__ == "__main__":
    asyncio.run(seed())
