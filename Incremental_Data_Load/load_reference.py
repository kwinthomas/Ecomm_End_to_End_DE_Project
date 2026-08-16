import os
import pandas as pd
import requests
from sqlalchemy import text
from db import get_engine

DATA = os.environ.get("DATA_DIR", "../Raw_Data")
CHUNK = 2000


def clean_text(s: pd.Series) -> pd.Series:
    return s.astype("string").str.strip().str.lower().str.slice(0, 64)


def load_customers() -> pd.DataFrame:
    cust = pd.read_csv(f"{DATA}/customers_dataset.csv")
    orders = pd.read_csv(
        f"{DATA}/orders_dataset.csv",
        usecols=["customer_id", "order_purchase_timestamp"],
        parse_dates=["order_purchase_timestamp"],
    )

    merged = cust.merge(orders, on="customer_id", how="inner")
    merged = merged.sort_values("order_purchase_timestamp")
    first = merged.drop_duplicates(subset="customer_unique_id", keep="first")

    out = pd.DataFrame({
        "customer_unique_id": first["customer_unique_id"].astype("string").str.strip(),
        "customer_zip_prefix": first["customer_zip_code_prefix"].astype(int).astype(str).str.zfill(5),
        "customer_city": clean_text(first["customer_city"]),
        "customer_state": first["customer_state"].astype("string").str.strip().str.upper(),
    })
    return out.dropna(subset=["customer_unique_id", "customer_zip_prefix",
                              "customer_city", "customer_state"])


def load_sellers() -> pd.DataFrame:
    s = pd.read_csv(f"{DATA}/sellers_dataset.csv")
    out = pd.DataFrame({
        "seller_id": s["seller_id"].astype("string").str.strip(),
        "seller_zip_prefix": s["seller_zip_code_prefix"].astype(int).astype(str).str.zfill(5),
        "seller_city": clean_text(s["seller_city"]),
        "seller_state": s["seller_state"].astype("string").str.strip().str.upper(),
    })
    return out.drop_duplicates(subset="seller_id")


def load_products() -> pd.DataFrame:
    p = pd.read_csv(f"{DATA}/products_dataset.csv")
    dims = ["product_weight_g", "product_length_cm",
            "product_height_cm", "product_width_cm"]
    out = pd.DataFrame({
        "product_id": p["product_id"].astype("string").str.strip(),
        "product_category_name": clean_text(p["product_category_name"]),
    })
    for c in dims:
        # Int64 = nullable integer. Plain int would crash on the ~600
        # products with missing dimensions; float would send 500.0 to an INT column.
        out[c] = pd.to_numeric(p[c], errors="coerce").astype("Int64")
    return out.drop_duplicates(subset="product_id")


def insert(engine, df: pd.DataFrame, table: str):
    df.to_sql(table, engine, schema="dbo", if_exists="append",
              index=False, chunksize=CHUNK, method=None)
    print(f"  {table}: {len(df):,} rows")


def main():
    engine = get_engine()

    # Idempotent: order matters, children before parents.
    with engine.begin() as conn:
        for t in ["order_items", "orders", "products", "sellers", "customers"]:
            conn.execute(text(f"DELETE FROM dbo.{t};"))
    print("cleared existing rows")

    for name, fn in [("customers", load_customers),
                     ("products", load_products),
                     ("sellers", load_sellers)]:
        df = fn()
        insert(engine, df, name)

    with engine.connect() as conn:
        for t in ["customers", "products", "sellers", "orders", "order_items"]:
            n = conn.execute(text(f"SELECT COUNT(*) FROM dbo.{t}")).scalar()
            print(f"{t:<14} {n:>8,}")
        v = conn.execute(text("SELECT CHANGE_TRACKING_CURRENT_VERSION()")).scalar()
        print(f"\nchange tracking version: {v}")


if __name__ == "__main__":
    main()