# Change Data Capture Pipeline for Operational Order Data

I built a data pipeline that keeps a copy of an online store's order database in sync — automatically, and without copying everything each time.

**Stack:** Azure SQL Database · Azure Data Factory · ADLS Gen2 · Databricks (PySpark, Delta Lake, Unity Catalog)

---

## The problem I set out to solve

Most companies have an operational database that runs the business — in this case, one holding e-commerce orders. Analysts can't query it directly, because heavy reporting queries would slow down the system customers are actually using. So the data has to be copied somewhere else.

The naive approach is to copy the whole database every night. That works until the database is large, at which point it's slow, expensive, and always out of date.

The better approach is **change data capture**: only copy the rows that actually changed since last time. That sounds simple, but it introduces problems that don't exist in a full copy:

- An order might change several times between copies. Which version is correct?
- An order might be **cancelled and deleted**. A copy of "rows that changed" doesn't naturally include rows that no longer exist.
- If the pipeline fails halfway and I run it again, will I end up with duplicate orders?

Solving those three problems is what this project is about.

---

## What I built

```
Azure SQL Database  →  Azure Data Factory  →  ADLS Gen2  →  Databricks  →  Star schema
   (the source)         (finds changes)      (change log)    (merge)       (for analysis)
```

### 1. A realistic source database

I used the Olist dataset — around 100,000 real Brazilian e-commerce orders. The problem is that it's a historical export: every order already shows as delivered. Nothing ever changes, so there'd be nothing to capture.

Each order does carry its real lifecycle timestamps, though — when it was purchased, approved, shipped, and delivered. So I worked backwards and reconstructed the individual changes that must have produced those timestamps, then replayed them against the database on a compressed clock. Orders get created, updated as they move through each stage, and deleted when cancelled — the same way they would in a live system.

### 2. A pipeline that finds only what changed

I enabled SQL Server's change tracking, which records which rows have been touched since a given point.

The pipeline keeps a **watermark table** — a small record of how far it got last time. On each run it reads that number, asks the database "what changed since then", writes the results to cloud storage, and updates the watermark.

It also checks whether the watermark has gone stale. Change tracking only remembers changes for a limited period, so if the pipeline hasn't run in too long, some changes will have been purged and the copy would silently be missing data. Rather than continuing and producing a quietly wrong result, the pipeline stops and reports the problem.

### 3. Merge logic that produces one accurate view

The change log is a running record of every change, so the same order can appear in it multiple times. In my test run, 14,806 change records covered 11,755 distinct orders.

I wrote merge logic in Databricks to collapse that into a single current view, handling three cases that break a naive approach:

| Problem | How I handled it |
|---|---|
| One order changed several times | Keep only the most recent version of each order before merging |
| An order was cancelled and deleted | Deleted rows arrive with no data attached, so they're handled separately — the order is flagged as cancelled rather than blanked out |
| The pipeline runs twice on the same data | Each order carries a version number, and an update only applies if the incoming version is genuinely newer |

That last point matters most. **Re-running the pipeline on data it has already processed changes nothing at all** — no duplicates, no lost data. I verified this by running the merge twice and confirming the second run wrote zero rows.

### 4. A model built for analysis

**Fact table (accumulating snapshot):** one row per order, with the timestamp of each stage and the time spent between them. As an order progresses, its row fills in. This answers questions like *how long do orders typically sit before shipping?* and *how often do we beat our own delivery estimate?*

**Type 2 customer dimension:** when a customer moves, I keep both the old and new address with the dates each was valid. This means an order placed last year is still correctly attributed to where the customer lived at the time, rather than where they live now.

---

## How I know it works

| Check | Result |
|---|---|
| Order count matches the source database | Exact match |
| Running the pipeline twice changes nothing | Zero rows written on the second run |
| Every order appears exactly once | No duplicates |
| No customer has two conflicting address records at once | None found |
| Past states can be reconstructed | Verified via Delta Lake versioning |

---

## What I'd do differently in production

Databricks and Azure both offer managed tools that do this merge automatically. I deliberately wrote it by hand so I'd understand what those tools do underneath — the ordering, the deletes, the re-run safety. In a real production system I'd likely use the managed option and spend the time saved on data quality and monitoring instead.

I'd also add alerting on pipeline failure, and run the source database's reference tables on a different refresh schedule from the fast-changing order tables, since they change far less often.

---

## Repository

```
sql/          Database schema, change tracking setup, watermark table
python/        Reference data load and change replay scripts
adf/           Data Factory pipeline definitions
databricks/    Merge logic and star schema models
```
