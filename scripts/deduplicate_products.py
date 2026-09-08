"""
KiranaBot — Product Catalog Deduplication & Cleanup Script

Merges duplicate products created during multi-run testing into clean canonical records.
Updates all foreign keys (bill_items, stock_movements) to point to the canonical product.
"""
import asyncio
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
os.environ.setdefault("APP_ENV", "development")

from app.database import get_db
from app.models import Product, BillItem, StockMovement
from sqlalchemy import select, update, delete, func


async def deduplicate():
    async with get_db() as db:
        print("Starting catalog deduplication...")

        # 1. Fetch all products
        all_products = (await db.execute(select(Product))).scalars().all()
        print(f"Total product rows before cleanup: {len(all_products)}")

        groups = {}
        test_products = []

        for p in all_products:
            is_dummy_test = (
                "special" in p.name.lower()
                or "test product" in p.name.lower()
                or "sugar test" in p.name.lower()
            )
            if is_dummy_test:
                test_products.append(p)
                continue

            brand_key = (p.brand or "").strip().lower()
            name_key = p.name.strip().lower()
            key = (brand_key, name_key)

            if key not in groups:
                groups[key] = []
            groups[key].append(p)

        canonical_map = {}

        # 2. For each group, pick canonical product
        for (brand_key, name_key), prods in groups.items():
            # Keeper is the one with highest stock, or oldest
            keeper = sorted(prods, key=lambda x: (x.qty_on_hand > 0, -x.created_at.timestamp()), reverse=True)[0]
            canonical_map[(brand_key, name_key)] = keeper.id
            duplicates = [p for p in prods if p.id != keeper.id]

            if duplicates:
                print(f"Merging {len(duplicates)} duplicates for '{keeper.display_name}' into keeper {keeper.id}")
                for dup in duplicates:
                    await db.execute(
                        update(BillItem)
                        .where(BillItem.product_id == dup.id)
                        .values(product_id=keeper.id)
                    )
                    await db.execute(
                        update(StockMovement)
                        .where(StockMovement.product_id == dup.id)
                        .values(product_id=keeper.id)
                    )
                    await db.execute(
                        delete(Product).where(Product.id == dup.id)
                    )

        # 3. Handle test dummy products
        atta_id = canonical_map.get(("aashirvaad", "atta")) or next(iter(canonical_map.values()))
        sugar_id = canonical_map.get(("local", "sugar")) or atta_id
        butter_id = canonical_map.get(("amul", "butter")) or atta_id

        for tp in test_products:
            # Remap bill items
            if "sugar" in tp.name.lower():
                target_id = sugar_id
            elif "butter" in tp.name.lower():
                target_id = butter_id
            else:
                target_id = atta_id

            await db.execute(
                update(BillItem)
                .where(BillItem.product_id == tp.id)
                .values(product_id=target_id)
            )
            await db.execute(delete(StockMovement).where(StockMovement.product_id == tp.id))
            await db.execute(delete(Product).where(Product.id == tp.id))

        await db.commit()

        # 4. Verify final unique products
        final_products = (await db.execute(select(Product).order_by(Product.name))).scalars().all()
        print(f"\n[OK] Deduplication complete! Total active unique products: {len(final_products)}")
        for p in final_products:
            print(f"  - {p.brand or ''} {p.name} ({p.unit}) - Stock: {p.qty_on_hand} | Price: Rs {p.sell_price}")


if __name__ == "__main__":
    asyncio.run(deduplicate())
