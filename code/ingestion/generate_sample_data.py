"""
Generate synthetic POS exports for the pipeline (data/raw/*.csv).

    python code/ingestion/generate_sample_data.py            # full year 2024
    python code/ingestion/generate_sample_data.py --scale 0.2

Everything is fake: generic location codes (LOC-01..LOC-05), invented names,
addresses and menu items. Seeded, so the output is reproducible. The data is
shaped to satisfy code/validation/quality_checks.py (47 menu items, food cost
<= 45%, totals = subtotal + 13% tax, no orders on closed days, ...).
"""
from __future__ import annotations

import argparse
import csv
import os
import random
from datetime import date, datetime, timedelta
from pathlib import Path

BASE = Path(os.environ.get("PIPELINE_HOME", Path(__file__).resolve().parents[2]))
TAX_RATE = 0.13
CLOSED_DAYS = {date(2024, 1, 1), date(2024, 12, 25)}

LOCATIONS = [
    ("LOC-01", "Downtown",     "100 King St",      120, "2019-03-01", "Alex Morgan"),
    ("LOC-02", "Harbourfront", "25 Lakeshore Ave",  90, "2020-06-15", "Sam Rivera"),
    ("LOC-03", "Midtown",      "480 Yonge Blvd",   110, "2018-09-10", "Jordan Lee"),
    ("LOC-04", "West End",     "77 Queen St W",     70, "2021-04-20", "Taylor Chen"),
    ("LOC-05", "Northgate",    "1200 North Rd",    100, "2022-02-01", "Casey Patel"),
]
# relative demand per location
DEMAND = {"LOC-01": 1.3, "LOC-02": 1.0, "LOC-03": 1.15, "LOC-04": 0.75, "LOC-05": 0.9}

# (category, subcategory, base names, price range, sizes)
MENU_SPEC = [
    ("Pizza",    "Classic",   ["Margherita", "Pepperoni", "Hawaiian"],          (12, 19), ["Medium", "Large"]),
    ("Pizza",    "Specialty", ["BBQ Chicken", "Veggie Supreme", "Meat Lovers"], (15, 24), ["Medium", "Large"]),
    ("Burgers",  "Beef",      ["Classic Burger", "Bacon Cheeseburger", "Mushroom Swiss"], (11, 17), ["Regular"]),
    ("Burgers",  "Chicken",   ["Crispy Chicken", "Spicy Chicken"],               (11, 16), ["Regular"]),
    ("Pasta",    "Pasta",     ["Spaghetti Bolognese", "Fettuccine Alfredo", "Penne Arrabbiata"], (13, 20), ["Regular"]),
    ("Salads",   "Salads",    ["Caesar Salad", "Greek Salad", "Garden Salad"],   (8, 14), ["Small", "Large"]),
    ("Sides",    "Sides",     ["Fries", "Onion Rings", "Garlic Bread", "Wings"], (4, 13), ["Regular"]),
    ("Desserts", "Desserts",  ["Cheesecake", "Brownie", "Tiramisu"],             (5, 9), ["Regular"]),
    ("Beverages","Soft Drinks", ["Cola", "Lemonade", "Iced Tea"],                (1.5, 4), ["Regular", "Large"]),
    ("Beverages","Coffee",    ["Coffee", "Latte"],                               (2, 5.5), ["Regular"]),
]


def build_menu(rng: random.Random) -> list[dict]:
    items = []
    for cat, sub, names, (lo, hi), sizes in MENU_SPEC:
        for name in names:
            base = rng.uniform(lo, hi)
            for k, size in enumerate(sizes):
                price = round(base * (1 + 0.3 * k), 2)
                price = round(max(0.99, min(price, 89.99)), 2)
                items.append({
                    "item_name": name if len(sizes) == 1 else f"{name} ({size})",
                    "category": cat, "subcategory": sub, "size": size,
                    "selling_price": price,
                    "cost_price": round(price * rng.uniform(0.22, 0.42), 2),
                    "is_active": True,
                    "launch_date": (date(2022, 1, 1) + timedelta(days=rng.randint(0, 600))).isoformat(),
                    "is_seasonal": False,
                })
    # trim/pad to exactly 47 items (the quality layer expects 47)
    items = items[:47]
    while len(items) < 47:
        extra = dict(items[len(items) % 10]); extra["item_name"] += " Special"; extra["is_seasonal"] = True
        items.append(extra)
    for i, it in enumerate(items, 1):
        it["item_id"] = f"ITM-{i:03d}"
    cols = ["item_id", "item_name", "category", "subcategory", "size", "selling_price",
            "cost_price", "is_active", "launch_date", "is_seasonal"]
    return [{c: it[c] for c in cols} for it in items]


def price_history(menu: list[dict], rng: random.Random) -> list[dict]:
    rows, n = [], 0
    for it in menu:
        if rng.random() < 0.3:                         # ~30% had a price change mid-year
            n += 1
            old = round(it["selling_price"] * 0.93, 2)
            rows.append({"price_history_id": f"PH-{n:04d}", "item_id": it["item_id"],
                         "selling_price": old, "cost_price": round(it["cost_price"] * 0.95, 2),
                         "effective_from": "2024-01-01", "effective_to": "2024-06-30",
                         "is_current": False, "change_reason": "Supplier cost increase"})
            start = "2024-07-01"
        else:
            start = "2024-01-01"
        n += 1
        rows.append({"price_history_id": f"PH-{n:04d}", "item_id": it["item_id"],
                     "selling_price": it["selling_price"], "cost_price": it["cost_price"],
                     "effective_from": start, "effective_to": "", "is_current": True,
                     "change_reason": "Current price"})
    return rows


def promotions() -> list[dict]:
    return [
        {"promo_id": "PRM-01", "promo_name": "Tuesday Pizza Deal", "discount_type": "percent",
         "discount_value": 0.15, "applies_to": "Pizza", "start_date": "2024-01-01",
         "end_date": "2024-12-31", "location_id": "ALL", "day_of_week": "Tuesday"},
        {"promo_id": "PRM-02", "promo_name": "Happy Hour Sides", "discount_type": "percent",
         "discount_value": 0.25, "applies_to": "Sides", "start_date": "2024-03-01",
         "end_date": "2024-10-31", "location_id": "LOC-02", "day_of_week": "ALL"},
    ]


def order_hour(rng: random.Random) -> int:
    return rng.choices(range(11, 23), weights=[9, 14, 12, 5, 4, 6, 12, 14, 11, 7, 4, 2])[0]


def orders_and_items(menu: list[dict], scale: float, rng: random.Random):
    orders, items, o_n, i_n = [], [], 0, 0
    weights = [6 if m["category"] in ("Pizza", "Beverages") else 3 for m in menu]
    day = date(2024, 1, 1)
    while day <= date(2024, 12, 31):
        if day not in CLOSED_DAYS:
            season = 1.15 if day.month in (6, 7, 8, 12) else 1.0
            weekend = 1.35 if day.weekday() >= 4 else 1.0          # Fri-Sun busier
            for loc_id, loc_name, *_ in LOCATIONS:
                n = int(rng.gauss(36, 6) * DEMAND[loc_id] * season * weekend * scale)
                for _ in range(max(n, 0)):
                    o_n += 1
                    oid = f"ORD-{o_n:07d}"
                    is_tue = day.weekday() == 1
                    lines, sub, disc_total = [], 0.0, 0.0
                    for item in rng.choices(menu, weights=weights, k=rng.choice([1, 2, 2, 3, 3, 4])):
                        qty = rng.choices([1, 2, 3], weights=[75, 20, 5])[0]
                        gross = item["selling_price"] * qty
                        disc = round(gross * 0.15, 2) if (is_tue and item["category"] == "Pizza") else 0.0
                        line = round(gross - disc, 2)
                        i_n += 1
                        lines.append({"order_item_id": f"OI-{i_n:08d}", "order_id": oid,
                                      "item_id": item["item_id"], "item_name": item["item_name"],
                                      "category": item["category"], "size": item["size"],
                                      "quantity": qty, "unit_price": item["selling_price"],
                                      "discount_applied": disc, "line_total": line,
                                      "promo_id": "PRM-01" if disc else ""})
                        sub += line; disc_total += disc
                    sub = round(sub, 2)
                    tax = round(sub * TAX_RATE, 2)
                    refund = rng.random() < 0.01
                    sign = -1 if refund else 1
                    hh = order_hour(rng)
                    orders.append({
                        "order_id": oid, "location_id": loc_id, "location_name": loc_name,
                        "order_date": day.isoformat(),
                        "order_time": f"{hh:02d}:{rng.randint(0, 59):02d}:00",
                        "order_type": rng.choices(["Dine-In", "Takeout", "Delivery"], weights=[50, 30, 20])[0],
                        "cashier_id": f"{loc_id}-C{rng.randint(1, 6)}",
                        "subtotal": sign * sub, "discount_amount": round(disc_total, 2),
                        "tax_amount": sign * tax, "total_amount": round(sign * (sub + tax), 2),
                        "payment_method": rng.choices(["Card", "Cash", "Mobile"], weights=[60, 20, 20])[0],
                        "is_refund": refund,
                    })
                    items.extend(lines)
        day += timedelta(days=1)
    return orders, items


def write(path: Path, rows: list[dict]) -> None:
    with path.open("w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=list(rows[0]))
        w.writeheader()
        w.writerows(rows)
    print(f"{len(rows):>9,} rows -> {path}")


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", default=str(BASE / "data" / "raw"))
    ap.add_argument("--scale", type=float, default=1.0, help="order volume multiplier")
    ap.add_argument("--seed", type=int, default=7)
    args = ap.parse_args()

    rng = random.Random(args.seed)
    out = Path(args.out); out.mkdir(parents=True, exist_ok=True)
    menu = build_menu(rng)
    orders, items = orders_and_items(menu, args.scale, rng)
    locations = [{"location_id": l[0], "location_name": l[1], "address": l[2],
                  "seating_capacity": l[3], "opening_date": l[4], "manager_name": l[5],
                  "phone": f"555-01{i:02d}", "is_active": True} for i, l in enumerate(LOCATIONS)]
    write(out / "locations.csv", locations)
    write(out / "menu.csv", menu)
    write(out / "menu_price_history.csv", price_history(menu, rng))
    write(out / "promotions.csv", promotions())
    write(out / "orders.csv", orders)
    write(out / "order_items.csv", items)


if __name__ == "__main__":
    main()
