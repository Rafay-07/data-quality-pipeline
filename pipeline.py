"""Data quality pipeline: read a messy CSV, clean it, validate every row against
rules, quarantine bad rows with the reason, load good rows into SQLite, and write
a plain-text quality report.

Flow:  read -> clean -> validate -> dedupe -> load (good) / quarantine (bad) -> report
"""
import csv
import re
import sqlite3
from datetime import datetime

# Rules per column: required, type, allowed range or pattern.
RULES = {
    "order_id": {"required": True, "pattern": r"^ORD-\d{4}$"},
    "customer": {"required": True},
    "email": {"required": False, "pattern": r"^[\w.+-]+@[\w-]+\.[\w.-]+$"},
    "quantity": {"required": True, "type": int, "min": 1, "max": 1000},
    "unit_price": {"required": True, "type": float, "min": 0.01, "max": 100000},
    "order_date": {"required": True, "type": "date"},
}
DATE_FORMATS = ("%Y-%m-%d", "%d/%m/%Y", "%m-%d-%Y")


def clean(row: dict) -> dict:
    """Fix harmless problems: trim spaces, tidy name case, lowercase email, and
    convert dates written in several formats to ISO (YYYY-MM-DD)."""
    out = {k: (v or "").strip() for k, v in row.items()}
    out["customer"] = out.get("customer", "").title()
    out["email"] = out.get("email", "").lower()
    out["order_id"] = out.get("order_id", "").upper()
    out["unit_price"] = out.get("unit_price", "").replace("$", "").replace(",", "")
    for fmt in DATE_FORMATS:
        try:
            out["order_date"] = datetime.strptime(out.get("order_date", ""), fmt).date().isoformat()
            break
        except ValueError:
            continue
    return out


def validate(row: dict) -> list[str]:
    """Return the list of rule violations for one cleaned row (empty list = valid)."""
    errors = []
    for col, rule in RULES.items():
        value = row.get(col, "")
        if value == "":
            if rule.get("required"):
                errors.append(f"{col}: missing")
            continue
        if "pattern" in rule and not re.match(rule["pattern"], value):
            errors.append(f"{col}: bad format '{value}'")
        typ = rule.get("type")
        if typ in (int, float):
            try:
                num = typ(value)
            except ValueError:
                errors.append(f"{col}: not a number '{value}'")
                continue
            if num < rule["min"] or num > rule["max"]:
                errors.append(f"{col}: {num} outside {rule['min']}-{rule['max']}")
        elif typ == "date":
            try:
                datetime.strptime(value, "%Y-%m-%d")
            except ValueError:
                errors.append(f"{col}: unreadable date '{value}'")
    return errors


def run(csv_path: str, db_path: str = ":memory:"):
    """Process a file. Returns (db connection, stats dict, quarantined rows)."""
    db = sqlite3.connect(db_path)
    db.execute("""CREATE TABLE IF NOT EXISTS orders(order_id TEXT PRIMARY KEY, customer TEXT, email TEXT,
                  quantity INT, unit_price REAL, order_date TEXT)""")
    stats = {"read": 0, "loaded": 0, "duplicates": 0, "rejected": 0}
    quarantine, seen = [], set()
    with open(csv_path, newline="") as f:
        for line_no, raw in enumerate(csv.DictReader(f), start=2):   # line 1 is the header
            stats["read"] += 1
            row = clean(raw)
            errors = validate(row)
            if errors:
                stats["rejected"] += 1
                quarantine.append({"line": line_no, "row": row, "errors": errors})
            elif row["order_id"] in seen:               # same order twice: keep the first
                stats["duplicates"] += 1
            else:
                seen.add(row["order_id"])
                db.execute("INSERT INTO orders VALUES (?,?,?,?,?,?)",
                           (row["order_id"], row["customer"], row["email"] or None,
                            int(row["quantity"]), float(row["unit_price"]), row["order_date"]))
                stats["loaded"] += 1
    db.commit()
    return db, stats, quarantine


def report(stats: dict, quarantine: list) -> str:
    lines = ["DATA QUALITY REPORT", "=" * 19,
             f"Rows read:        {stats['read']}", f"Loaded:           {stats['loaded']}",
             f"Duplicates:       {stats['duplicates']}", f"Rejected:         {stats['rejected']}"]
    pass_rate = 100 * stats["loaded"] / stats["read"] if stats["read"] else 0
    lines.append(f"Pass rate:        {pass_rate:.1f}%")
    if quarantine:
        lines += ["", "Rejected rows:"]
        lines += [f"  line {q['line']}: " + "; ".join(q["errors"]) for q in quarantine]
    return "\n".join(lines)


if __name__ == "__main__":
    import sys
    path = sys.argv[1] if len(sys.argv) > 1 else "sample_orders.csv"
    _, s, q = run(path, "orders.db")
    print(report(s, q))
