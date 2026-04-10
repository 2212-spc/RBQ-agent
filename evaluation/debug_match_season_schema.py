"""Check match_season schema and sample rows to understand join columns."""
import duckdb
from pathlib import Path

ws = Path("outputs/hdrbench_full150_v1/spider__match_season__01072/workspace")
db = list(ws.glob("*.sqlite"))[0]
print(f"db: {db.name}")

con = duckdb.connect()
con.execute(f"ATTACH '{db}' AS ms (TYPE SQLITE)")

for table in ["match_season", "country"]:
    print(f"\n-- {table} schema:")
    cols = [c[0] for c in con.execute(f"DESCRIBE ms.{table}").fetchall()]
    print("  cols:", cols)
    print(f"\n-- {table} sample:")
    print(con.execute(f"SELECT * FROM ms.{table} LIMIT 3").fetchdf().to_string())
