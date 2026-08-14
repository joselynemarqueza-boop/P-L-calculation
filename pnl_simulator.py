import pandas as pd

# === 1. Load CSVs ===
pricing = pd.read_csv("pricing.csv")
gtn = pd.read_csv("GTN.csv")
volume = pd.read_csv("volume.csv")

# === 2. Normalize months in GTN ===
month_map = {
    "Jan": 1, "Feb": 2, "Mar": 3, "Apr": 4,
    "May": 5, "Jun": 6, "Jul": 7, "Aug": 8,
    "Sep": 9, "Oct": 10, "Nov": 11, "Dec": 12
}

gtn["month_num"] = gtn["month"].map(month_map)

# === 3. Structural GTN (Annual, All) ===
gtn_structural = (
    gtn[(gtn["month"] == "Annual") & (gtn["category"] == "All")]
    .groupby(["client_code", "client_name"], as_index=False)
    .agg(structural_gtn_pct=("gtn_pct", "sum"))
)

# === 4. Tactical GTN (by month, client, category) ===
gtn_tactical = (
    gtn[gtn["month"] != "Annual"]
    .groupby(["month_num", "client_code", "client_name", "category"], as_index=False)
    .agg(tactical_gtn_pct=("gtn_pct", "sum"))
)

# === 5. Merge volume with pricing (PXQ) ===
# Ensure same client_code and sku keys
pxq = volume.merge(
    pricing,
    on=["client_code", "client_name", "channel", "sku", "product_name", "category"],
    how="left"
)

# Calculate gross sales and COGS
pxq["gross_sales"] = pxq["units_sold"] * pxq["price_to_client_gbp"]
pxq["cogs"] = pxq["units_sold"] * pxq["cogs_per_unit_gbp"]

# === 6. Attach structural GTN to all rows (by client) ===
pxq = pxq.merge(
    gtn_structural[["client_code", "structural_gtn_pct"]],
    on="client_code",
    how="left"
)

# Fill missing structural with 0 (in case of any client not in GTN)
pxq["structural_gtn_pct"] = pxq["structural_gtn_pct"].fillna(0.0)

# === 7. Attach tactical GTN (by month, client, category) ===
pxq = pxq.merge(
    gtn_tactical[["month_num", "client_code", "category", "tactical_gtn_pct"]],
    left_on=["month", "client_code", "category"],
    right_on=["month_num", "client_code", "category"],
    how="left"
)

pxq["tactical_gtn_pct"] = pxq["tactical_gtn_pct"].fillna(0.0)

# === 8. Total GTN, NTS, GP Std ===
pxq["total_gtn_pct"] = pxq["structural_gtn_pct"] + pxq["tactical_gtn_pct"]
pxq["nts"] = pxq["gross_sales"] * (1 - pxq["total_gtn_pct"])
pxq["gp_std"] = pxq["nts"] - pxq["cogs"]

# === 9. Final P&L output (by year, month, client, sku) ===
pnl_cols = [
    "year", "month", "client_code", "client_name", "channel",
    "sku", "product_name", "category", "units_sold",
    "gross_sales", "structural_gtn_pct", "tactical_gtn_pct",
    "total_gtn_pct", "nts", "cogs", "gp_std"
]

pnl = pxq[pnl_cols].copy()

# === 10. Export CSV ===
pnl.to_csv("client_sku_month_pnl.csv", index=False)
