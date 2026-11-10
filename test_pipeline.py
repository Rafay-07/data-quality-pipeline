import pipeline


def test_clean_normalizes_text_and_dates():
    r = pipeline.clean({"order_id": " ord-1 ", "customer": "  ann LEE ", "email": "A@B.COM",
                        "unit_price": "$1,200.50", "order_date": "03/10/2026", "quantity": "1"})
    assert r["customer"] == "Ann Lee" and r["email"] == "a@b.com" and r["unit_price"] == "1200.50"
    assert r["order_date"] == "2026-10-03" and r["order_id"] == "ORD-1"


def good():
    return {"order_id": "ORD-1001", "customer": "Ann", "email": "a@b.com", "quantity": "2",
            "unit_price": "5.00", "order_date": "2026-10-01"}


def test_valid_row_has_no_errors():
    assert pipeline.validate(good()) == []


def test_each_rule_fires():
    cases = [("order_id", "X1", "bad format"), ("customer", "", "missing"), ("email", "nope", "bad format"),
             ("quantity", "0", "outside"), ("quantity", "two", "not a number"),
             ("unit_price", "-5", "outside"), ("order_date", "soon", "unreadable")]
    for col, val, text in cases:
        row = good(); row[col] = val
        assert any(text in e for e in pipeline.validate(row)), (col, val)


def test_optional_email_may_be_blank():
    row = good(); row["email"] = ""
    assert pipeline.validate(row) == []


def test_full_run_on_sample_file():
    db, stats, quarantine = pipeline.run("sample_orders.csv")
    assert stats == {"read": 9, "loaded": 3, "duplicates": 1, "rejected": 5}
    assert db.execute("SELECT COUNT(*) FROM orders").fetchone()[0] == 3
    assert {q["line"] for q in quarantine} == {3, 4, 7, 8, 9}
    assert "Pass rate" in pipeline.report(stats, quarantine)


def test_duplicate_keeps_first_row():
    db, _, _ = pipeline.run("sample_orders.csv")
    name = db.execute("SELECT customer FROM orders WHERE order_id='ORD-1001'").fetchone()[0]
    assert name == "Alice Smith"
