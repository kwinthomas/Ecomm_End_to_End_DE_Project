import os
import numpy as np
import pandas as pd

DATA = os.environ.get("DATA_DIR", "../Raw_Data")
START = pd.Timestamp("2017-10-01")
END = pd.Timestamp("2018-09-30 23:59:59")
SEED = 42
CUSTOMER_MOVE_RATE = 0.02
FREIGHT_REVISION_RATE = 0.10


def build():
    rng = np.random.default_rng(SEED)

    orders = pd.read_csv(f"{DATA}/orders_dataset.csv", parse_dates=[
        "order_purchase_timestamp", "order_approved_at",
        "order_delivered_carrier_date", "order_delivered_customer_date",
        "order_estimated_delivery_date"])
    cust = pd.read_csv(f"{DATA}/customers_dataset.csv")
    items = pd.read_csv(f"{DATA}/order_items_dataset.csv",
                        parse_dates=["shipping_limit_date"])

    orders = orders.merge(cust[["customer_id", "customer_unique_id"]],
                          on="customer_id", how="inner")

    # Slice on purchase date.
    orders = orders[(orders.order_purchase_timestamp >= START) &
                    (orders.order_purchase_timestamp <= END)].copy()

    loaded = set(pd.read_csv(f"{DATA}/_loaded_customers.csv").customer_unique_id) \
        if os.path.exists(f"{DATA}/_loaded_customers.csv") else None
    if loaded:
        orders = orders[orders.customer_unique_id.isin(loaded)]

    items = items[items.order_id.isin(set(orders.order_id))].copy()

    prods = set(pd.read_csv(f"{DATA}/products_dataset.csv").product_id)
    sells = set(pd.read_csv(f"{DATA}/sellers_dataset.csv").seller_id)
    before = len(items)
    items = items[items.product_id.isin(prods) & items.seller_id.isin(sells)]
    print(f"orphan order_items filtered: {before - len(items):,}")

    with_items = set(items.order_id)
    orders = orders[orders.order_id.isin(with_items)]
    items = items[items.order_id.isin(set(orders.order_id))]

    ev = []

    for o in orders.itertuples(index=False):
        pt = o.order_purchase_timestamp
        est = o.order_estimated_delivery_date

        ev.append(dict(t=pt, seq=0, kind="order_insert", order_id=o.order_id,
                       customer_unique_id=o.customer_unique_id,
                       status="created",
                       approved_at=None, carrier_date=None, customer_date=None,
                       estimated=est))

        if pd.notna(o.order_approved_at) and o.order_approved_at >= pt:
            ev.append(dict(t=o.order_approved_at, seq=1, kind="order_update",
                           order_id=o.order_id, status="approved",
                           approved_at=o.order_approved_at,
                           carrier_date=None, customer_date=None))

        if pd.notna(o.order_delivered_carrier_date):
            ev.append(dict(t=o.order_delivered_carrier_date, seq=2,
                           kind="order_update", order_id=o.order_id,
                           status="shipped",
                           approved_at=o.order_approved_at,
                           carrier_date=o.order_delivered_carrier_date,
                           customer_date=None))

        if pd.notna(o.order_delivered_customer_date):
            ev.append(dict(t=o.order_delivered_customer_date, seq=3,
                           kind="order_update", order_id=o.order_id,
                           status="delivered",
                           approved_at=o.order_approved_at,
                           carrier_date=o.order_delivered_carrier_date,
                           customer_date=o.order_delivered_customer_date))

        if o.order_status in ("canceled", "unavailable"):
            known = [x for x in [o.order_approved_at, o.order_delivered_carrier_date]
                     if pd.notna(x)]
            cancel_t = (max(known) if known else pt) + pd.Timedelta(days=1)
            ev.append(dict(t=cancel_t, seq=9, kind="order_delete",
                           order_id=o.order_id))

    pt_map = dict(zip(orders.order_id, orders.order_purchase_timestamp))
    for it in items.itertuples(index=False):
        ev.append(dict(t=pt_map[it.order_id], seq=0, kind="item_insert",
                       order_id=it.order_id, order_item_id=int(it.order_item_id),
                       product_id=it.product_id, seller_id=it.seller_id,
                       shipping_limit_date=it.shipping_limit_date,
                       price=float(it.price), freight_value=float(it.freight_value)))

    ship = orders.dropna(subset=["order_delivered_carrier_date"])
    ship_map = dict(zip(ship.order_id, ship.order_delivered_carrier_date))
    rev = items[items.order_id.isin(ship_map)]
    mask = rng.random(len(rev)) < FREIGHT_REVISION_RATE
    for it in rev[mask].itertuples(index=False):
        ev.append(dict(t=ship_map[it.order_id], seq=1, kind="item_update",
                       order_id=it.order_id, order_item_id=int(it.order_item_id),
                       freight_value=round(float(it.freight_value) * 1.15, 2)))

    uniq = orders.customer_unique_id.drop_duplicates().to_numpy()
    movers = rng.choice(uniq, size=int(len(uniq) * CUSTOMER_MOVE_RATE), replace=False)
    states = ["SP", "RJ", "MG", "RS", "PR", "SC", "BA", "GO"]
    span = (END - START).days
    for c in movers:
        ev.append(dict(t=START + pd.Timedelta(days=int(rng.integers(30, span - 30))),
                       seq=5, kind="customer_move",
                       customer_unique_id=c,
                       customer_state=str(rng.choice(states)),
                       customer_city=f"city_{rng.integers(1, 400)}",
                       customer_zip_prefix=str(rng.integers(1000, 99999)).zfill(5)))

    df = pd.DataFrame(ev)
    df = df[(df.t >= START) & (df.t <= END + pd.Timedelta(days=30))]
    df = df.sort_values(["t", "seq"]).reset_index(drop=True)
    df.to_parquet("events.parquet", index=False)

    print(df.kind.value_counts().to_string())
    print(f"\ntotal events: {len(df):,}")
    print(f"window: {df.t.min()} → {df.t.max()}")


if __name__ == "__main__":
    build()