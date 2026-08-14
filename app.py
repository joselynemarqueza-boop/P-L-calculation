import streamlit as st
import pandas as pd
from pathlib import Path

# ============================================================================
# PAGE CONFIGURATION
# ============================================================================
st.set_page_config(
    page_title="BeautyLab – P&L Visualizer",
    layout="wide",
    page_icon="📊"
)

# ============================================================================
# CUSTOM CSS
# ============================================================================
st.markdown("""
    <style>
    .stDataFrame { width: 100% !important; }
    .stMetric { 
        background-color: #f8f9fa; 
        border-radius: 10px; 
        padding: 15px; 
        border: 1px solid #e0e0e0; 
    }
    .main-header {
        font-size: 2.5rem;
        font-weight: 700;
        color: #2C2C3E;
        margin-bottom: 0.5rem;
    }
    .sub-header {
        font-size: 1rem;
        color: #666;
        margin-bottom: 2rem;
    }
    .footer {
        margin-top: 3rem;
        font-size: 0.8rem;
        color: #999;
        text-align: center;
        border-top: 1px solid #eee;
        padding-top: 1rem;
    }
    </style>
""", unsafe_allow_html=True)

# ============================================================================
# FILE PATHS
# ============================================================================
DATA_DIR = Path("Data")

PRICING_PATH = DATA_DIR / "pricing.csv"
GTN_PATH = DATA_DIR / "GTN.csv"
VOLUME_PATH = DATA_DIR / "volume.csv"

# ============================================================================
# DATA LOADING & CALCULATION ENGINE
# ============================================================================
@st.cache_data
def load_and_calculate():
    """Load CSV files and calculate P&L up to GP Std."""
    
    pricing = pd.read_csv(PRICING_PATH)
    gtn = pd.read_csv(GTN_PATH)
    volume = pd.read_csv(VOLUME_PATH)

    # Normalize months
    month_map = {
        "Jan": 1, "Feb": 2, "Mar": 3, "Apr": 4,
        "May": 5, "Jun": 6, "Jul": 7, "Aug": 8,
        "Sep": 9, "Oct": 10, "Nov": 11, "Dec": 12
    }
    gtn["month_num"] = gtn["month"].map(month_map)

    # Structural GTN
    gtn_structural = (
        gtn[(gtn["month"] == "Annual") & (gtn["category"] == "All")]
        .groupby(["client_code", "client_name"], as_index=False)
        .agg(structural_gtn_pct=("gtn_pct", "sum"))
    )

    # Tactical GTN
    gtn_tactical = (
        gtn[gtn["month"] != "Annual"]
        .groupby(["month_num", "client_code", "client_name", "category"], as_index=False)
        .agg(tactical_gtn_pct=("gtn_pct", "sum"))
    )

    # Merge volume with pricing
    pxq = volume.merge(
        pricing,
        on=["client_code", "client_name", "channel", "sku", "product_name", "category"],
        how="left"
    )

    # Calculate Gross Sales and COGS
    pxq["gross_sales"] = pxq["units_sold"] * pxq["price_to_client_gbp"]
    pxq["cogs"] = pxq["units_sold"] * pxq["cogs_per_unit_gbp"]

    # Merge Structural GTN
    pxq = pxq.merge(
        gtn_structural[["client_code", "structural_gtn_pct"]],
        on="client_code",
        how="left"
    )
    pxq["structural_gtn_pct"] = pxq["structural_gtn_pct"].fillna(0.0)

    # Merge Tactical GTN
    pxq = pxq.merge(
        gtn_tactical[["month_num", "client_code", "category", "tactical_gtn_pct"]],
        left_on=["month", "client_code", "category"],
        right_on=["month_num", "client_code", "category"],
        how="left"
    )
    pxq["tactical_gtn_pct"] = pxq["tactical_gtn_pct"].fillna(0.0)

    # P&L Calculations
    pxq["total_gtn_pct"] = pxq["structural_gtn_pct"] + pxq["tactical_gtn_pct"]
    pxq["returns"] = pxq["gross_sales"] * 0.02
    pxq["bonus"] = pxq["gross_sales"] * 0.015
    pxq["gtn_amount"] = pxq["gross_sales"] * pxq["total_gtn_pct"]
    pxq["nts"] = pxq["gross_sales"] - pxq["returns"] - pxq["bonus"] - pxq["gtn_amount"]
    pxq["gp_std"] = pxq["nts"] - pxq["cogs"]
    pxq["gp_std_pct"] = (pxq["gp_std"] / pxq["nts"] * 100).round(1)

    # Ensure no division by zero in gp_std_pct
    pxq.loc[pxq["nts"] == 0, "gp_std_pct"] = 0

    # Define column order
    column_order = [
        "year", "month", "client_code", "client_name", "channel",
        "sku", "product_name", "category", "units_sold",
        "gross_sales", "returns", "bonus",
        "structural_gtn_pct", "tactical_gtn_pct", "total_gtn_pct", "gtn_amount",
        "nts", "cogs", "gp_std", "gp_std_pct"
    ]

    return pxq[column_order].copy()

# ============================================================================
# LOAD DATA
# ============================================================================
st.markdown('<p class="main-header">📊 BeautyLab</p>', unsafe_allow_html=True)
st.markdown('<p class="sub-header">P&L Visualizer — Gross Trade Sales to GP Std</p>', unsafe_allow_html=True)

# Check files exist
missing_files = []
if not PRICING_PATH.exists():
    missing_files.append("pricing.csv")
if not GTN_PATH.exists():
    missing_files.append("GTN.csv")
if not VOLUME_PATH.exists():
    missing_files.append("volume.csv")

if missing_files:
    st.error(f"❌ Missing files in 'Data/' folder: {', '.join(missing_files)}")
    st.stop()

with st.spinner("Loading and calculating data..."):
    try:
        df = load_and_calculate()
    except Exception as e:
        st.error(f"❌ Error loading data: {str(e)}")
        st.stop()

st.success(f"✅ Data loaded: {len(df):,} rows")

# ============================================================================
# SIDEBAR FILTERS
# ============================================================================
with st.sidebar:
    st.header("🔍 Filters")
    st.divider()

    # Year
    year_options = sorted(df["year"].unique(), reverse=True)
    selected_year = st.selectbox("Year", year_options)

    # Client (multi-select)
    client_options = sorted(df[df["year"] == selected_year]["client_name"].unique())
    selected_clients = st.multiselect(
        "Clients",
        options=client_options,
        default=client_options
    )

    # Category (multi-select)
    cat_options = sorted(df[df["year"] == selected_year]["category"].unique())
    selected_cats = st.multiselect(
        "Categories",
        options=cat_options,
        default=cat_options
    )

    st.divider()
    st.caption("📈 Metrics update based on filters")

# ============================================================================
# APPLY BASE FILTERS (Year, Client, Category)
# ============================================================================
df_filtered = df[
    (df["year"] == selected_year) &
    (df["client_name"].isin(selected_clients)) &
    (df["category"].isin(selected_cats))
]

# ============================================================================
# TABS
# ============================================================================
tab_summary, tab_monthly, tab_gtn, tab_raw = st.tabs([
    "📊 P&L Summary (Annual)",
    "📈 Monthly P&L",
    "📊 GTN Breakdown",
    "📋 Raw Data"
])

# ============================================================================
# TAB 1: P&L SUMMARY (ANNUAL)
# ============================================================================
with tab_summary:
    st.subheader(f"Annual P&L Summary – {selected_year}")

    # Aggregate by year using modern syntax
    df_annual = df_filtered.groupby("year", as_index=False).agg(
        gross_sales=("gross_sales", "sum"),
        returns=("returns", "sum"),
        bonus=("bonus", "sum"),
        gtn_amount=("gtn_amount", "sum"),
        nts=("nts", "sum"),
        cogs=("cogs", "sum"),
        gp_std=("gp_std", "sum")
    )

    # Calculate percentages
    if not df_annual.empty:
        row = df_annual.iloc[0]
        total_gts = row["gross_sales"]
        
        df_annual["gross_sales_pct"] = 100.0
        df_annual["returns_pct"] = (row["returns"] / total_gts * 100).round(1) if total_gts > 0 else 0
        df_annual["bonus_pct"] = (row["bonus"] / total_gts * 100).round(1) if total_gts > 0 else 0
        df_annual["gtn_pct"] = (row["gtn_amount"] / total_gts * 100).round(1) if total_gts > 0 else 0
        df_annual["nts_pct"] = (row["nts"] / total_gts * 100).round(1) if total_gts > 0 else 0
        df_annual["cogs_pct"] = (row["cogs"] / row["nts"] * 100).round(1) if row["nts"] > 0 else 0
        df_annual["gp_std_pct"] = (row["gp_std"] / row["nts"] * 100).round(1) if row["nts"] > 0 else 0

    # Display metrics
    col1, col2, col3, col4 = st.columns(4)
    total_gts = df_annual["gross_sales"].iloc[0] if not df_annual.empty else 0
    total_nts = df_annual["nts"].iloc[0] if not df_annual.empty else 0
    total_gp = df_annual["gp_std"].iloc[0] if not df_annual.empty else 0
    gp_pct = df_annual["gp_std_pct"].iloc[0] if not df_annual.empty else 0

    col1.metric("💰 Gross Sales", f"£{total_gts:,.0f}")
    col2.metric("📊 NTS", f"£{total_nts:,.0f}")
    col3.metric("💎 GP Std", f"£{total_gp:,.0f}")
    col4.metric("📈 GP %", f"{gp_pct:.1f}%")

    st.divider()

    # P&L Table by Account
    st.subheader("P&L by Account")

    # Build P&L rows
    pl_data = []

    if not df_annual.empty:
        row = df_annual.iloc[0]
        pl_data.append({"Account": "Gross Trade Sales (GTS)", "Value": row["gross_sales"], "% of GTS": 100.0})
        pl_data.append({"Account": "Returns (2%)", "Value": -row["returns"], "% of GTS": -row["returns_pct"]})
        pl_data.append({"Account": "Bonuses (1.5%)", "Value": -row["bonus"], "% of GTS": -row["bonus_pct"]})
        pl_data.append({"Account": "GTN (Structural + Tactical)", "Value": -row["gtn_amount"], "% of GTS": -row["gtn_pct"]})
        pl_data.append({"Account": "Net Trade Sales (NTS)", "Value": row["nts"], "% of GTS": row["nts_pct"]})
        pl_data.append({"Account": "COGS", "Value": -row["cogs"], "% of NTS": -row["cogs_pct"]})
        pl_data.append({"Account": "Gross Profit (GP Std)", "Value": row["gp_std"], "% of NTS": row["gp_std_pct"]})

    df_pl = pd.DataFrame(pl_data) if pl_data else pd.DataFrame(columns=["Account", "Value", "% of GTS"])

    if not df_pl.empty:
        # Apply styling using the modern .map() method
        styled_df = df_pl.style.format({
            "Value": "£{:,.0f}",
            "% of GTS": "{:.1f}%"
        })

        # Apply conditional styling to the 'Account' column
        styled_df = styled_df.map(
            lambda x: "font-weight: bold; background-color: #f0f0f0" if isinstance(x, str) and "GTS" in x else
                      "font-weight: bold; background-color: #f0f0f0" if isinstance(x, str) and "NTS" in x else
                      "font-weight: bold; background-color: #e6f3e6" if isinstance(x, str) and "GP" in x else
                      "",
            subset=["Account"]
        )

        st.dataframe(styled_df, use_container_width=True, hide_index=True)
    else:
        st.info("No data available for the selected filters.")

    # Also show by Client
    st.subheader("P&L by Client")

    df_client = df_filtered.groupby("client_name", as_index=False).agg(
        gross_sales=("gross_sales", "sum"),
        nts=("nts", "sum"),
        gp_std=("gp_std", "sum")
    )

    if not df_client.empty:
        df_client["gp_pct"] = (df_client["gp_std"] / df_client["nts"] * 100).round(1)
        df_client = df_client.sort_values("gp_std", ascending=False)

        st.dataframe(
            df_client.style.format({
                "gross_sales": "£{:,.0f}",
                "nts": "£{:,.0f}",
                "gp_std": "£{:,.0f}",
                "gp_pct": "{:.1f}%"
            }),
            use_container_width=True,
            hide_index=True
        )
    else:
        st.info("No client data available for the selected filters.")

    # Download summary
    if not df_pl.empty:
        csv_summary = df_pl.to_csv(index=False).encode("utf-8")
        st.download_button(
            label="📥 Download P&L Summary",
            data=csv_summary,
            file_name=f"pl_summary_{selected_year}.csv",
            mime="text/csv"
        )

# ============================================================================
# TAB 2: MONTHLY P&L
# ============================================================================
with tab_monthly:
    st.subheader(f"Monthly P&L Evolution – {selected_year}")

    # Aggregate by month
    df_monthly = df_filtered.groupby("month", as_index=False).agg(
        gross_sales=("gross_sales", "sum"),
        nts=("nts", "sum"),
        gp_std=("gp_std", "sum")
    ).sort_values("month")

    # Add month names
    month_names = {
        1: "Jan", 2: "Feb", 3: "Mar", 4: "Apr",
        5: "May", 6: "Jun", 7: "Jul", 8: "Aug",
        9: "Sep", 10: "Oct", 11: "Nov", 12: "Dec"
    }
    df_monthly["month_name"] = df_monthly["month"].map(month_names)

    if not df_monthly.empty:
        df_monthly["gp_pct"] = (df_monthly["gp_std"] / df_monthly["nts"] * 100).round(1)
    else:
        df_monthly["gp_pct"] = 0

    # Display metrics
    col1, col2, col3 = st.columns(3)
    col1.metric("📊 Avg Monthly NTS", f"£{df_monthly['nts'].mean():,.0f}" if not df_monthly.empty else "£0")
    col2.metric("💎 Avg Monthly GP", f"£{df_monthly['gp_std'].mean():,.0f}" if not df_monthly.empty else "£0")
    col3.metric("📈 Avg Monthly GP %", f"{df_monthly['gp_pct'].mean():.1f}%" if not df_monthly.empty else "0.0%")

    st.divider()

    # Monthly table
    if not df_monthly.empty:
        st.dataframe(
            df_monthly[[
                "month_name", "gross_sales", "nts", "gp_std", "gp_pct"
            ]].style.format({
                "gross_sales": "£{:,.0f}",
                "nts": "£{:,.0f}",
                "gp_std": "£{:,.0f}",
                "gp_pct": "{:.1f}%"
            }),
            use_container_width=True,
            hide_index=True,
            column_config={
                "month_name": "Month",
                "gross_sales": "Gross Sales",
                "nts": "NTS",
                "gp_std": "GP Std",
                "gp_pct": "GP %"
            }
        )
    else:
        st.info("No data available for the selected filters.")

    # Download monthly data
    if not df_monthly.empty:
        csv_monthly = df_monthly.to_csv(index=False).encode("utf-8")
        st.download_button(
            label="📥 Download Monthly P&L",
            data=csv_monthly,
            file_name=f"pl_monthly_{selected_year}.csv",
            mime="text/csv"
        )

# ============================================================================
# TAB 3: GTN BREAKDOWN
# ============================================================================
with tab_gtn:
    st.subheader(f"Gross-to-Net (GTN) Breakdown – {selected_year}")
    st.caption("Desglose de inversión comercial por cliente, categoría y componente")

    # --- FILTROS ESPECÍFICOS PARA GTN ---
    col1, col2 = st.columns(2)

    with col1:
        # Cliente (multi-select)
        gtn_client_options = sorted(df_filtered["client_name"].unique())
        gtn_selected_clients = st.multiselect(
            "Select Clients (GTN)",
            options=gtn_client_options,
            default=gtn_client_options,
            key="gtn_clients"
        )

    with col2:
        # Categoría (multi-select)
        gtn_cat_options = sorted(df_filtered["category"].unique())
        gtn_selected_cats = st.multiselect(
            "Select Categories (GTN)",
            options=gtn_cat_options,
            default=gtn_cat_options,
            key="gtn_cats"
        )

    # Aplicar filtros
    df_gtn_filtered = df_filtered[
        (df_filtered["client_name"].isin(gtn_selected_clients)) &
        (df_filtered["category"].isin(gtn_selected_cats))
    ]

    # --- MÉTRICAS DE GTN ---
    c1, c2, c3, c4 = st.columns(4)

    total_gts = df_gtn_filtered["gross_sales"].sum()
    total_gtn = df_gtn_filtered["gtn_amount"].sum()
    total_nts = df_gtn_filtered["nts"].sum()
    avg_gtn_pct = (total_gtn / total_gts * 100) if total_gts > 0 else 0

    c1.metric("💰 GTS (Gross Trade Sales)", f"£{total_gts:,.0f}")
    c2.metric("📉 GTN Total", f"£{total_gtn:,.0f}")
    c3.metric("📊 NTS (Net Trade Sales)", f"£{total_nts:,.0f}")
    c4.metric("📈 GTN % Promedio", f"{avg_gtn_pct:.1f}%")

    st.divider()

    # --- VISTA 1: GTN POR CLIENTE Y CATEGORÍA (PIVOT) ---
    st.subheader("📊 GTN % by Client and Category")

    # Calcular GTN promedio por cliente y categoría
    df_gtn_pivot = df_gtn_filtered.groupby(["client_name", "category"]).agg({
        "gross_sales": "sum",
        "gtn_amount": "sum"
    }).reset_index()

    df_gtn_pivot["gtn_pct"] = (df_gtn_pivot["gtn_amount"] / df_gtn_pivot["gross_sales"] * 100).round(1)

    # Crear pivot table
    gtn_pivot_table = df_gtn_pivot.pivot(index="client_name", columns="category", values="gtn_pct")

    st.dataframe(
        gtn_pivot_table.style.format("{:.1f}%"),
        use_container_width=True,
        height=300
    )

    # --- VISTA 2: DESGLOSE DE GTN ESTRUCTURAL ---
    st.subheader("🏗️ Structural GTN Breakdown")

    # Calcular GTN estructural por cliente (promedio)
    df_structural = df_gtn_filtered.groupby("client_name").agg({
        "structural_gtn_pct": "mean",
        "gross_sales": "sum"
    }).reset_index()

    df_structural["structural_gtn_pct"] = (df_structural["structural_gtn_pct"] * 100).round(1)
    df_structural = df_structural.sort_values("structural_gtn_pct", ascending=False)

    st.dataframe(
        df_structural.style.format({
            "structural_gtn_pct": "{:.1f}%",
            "gross_sales": "£{:,.0f}"
        }),
        use_container_width=True,
        hide_index=True
    )

    # --- VISTA 3: DESGLOSE DE GTN TÁCTICO ---
    st.subheader("🎯 Tactical GTN Breakdown")

    # Calcular GTN táctico por cliente y categoría
    df_tactical = df_gtn_filtered.groupby(["client_name", "category"]).agg({
        "tactical_gtn_pct": "mean",
        "gross_sales": "sum"
    }).reset_index()

    df_tactical["tactical_gtn_pct"] = (df_tactical["tactical_gtn_pct"] * 100).round(1)
    df_tactical = df_tactical.sort_values("tactical_gtn_pct", ascending=False)

    st.dataframe(
        df_tactical.style.format({
            "tactical_gtn_pct": "{:.1f}%",
            "gross_sales": "£{:,.0f}"
        }),
        use_container_width=True,
        hide_index=True
    )

    # --- VISTA 4: COMPARATIVO ESTRUCTURAL VS TÁCTICO ---
    st.subheader("⚖️ Structural vs Tactical GTN Comparison")

    # Merge estructural y táctico para comparativa
    df_compare = df_structural[["client_name", "structural_gtn_pct"]].merge(
        df_tactical.groupby("client_name").agg({"tactical_gtn_pct": "mean"}).reset_index(),
        on="client_name",
        how="outer"
    ).fillna(0)

    df_compare["total_gtn_pct"] = df_compare["structural_gtn_pct"] + df_compare["tactical_gtn_pct"]
    df_compare = df_compare.sort_values("total_gtn_pct", ascending=False)

    st.dataframe(
        df_compare.style.format({
            "structural_gtn_pct": "{:.1f}%",
            "tactical_gtn_pct": "{:.1f}%",
            "total_gtn_pct": "{:.1f}%"
        }),
        use_container_width=True,
        hide_index=True
    )

    # --- VISTA 5: DETALLE DE GTN POR MES (Solo si hay datos mensuales) ---
    st.subheader("📅 Monthly GTN Evolution")

    # Calcular GTN mensual
    df_gtn_monthly = df_gtn_filtered.groupby("month").agg({
        "gross_sales": "sum",
        "gtn_amount": "sum"
    }).reset_index().sort_values("month")

    df_gtn_monthly["gtn_pct"] = (df_gtn_monthly["gtn_amount"] / df_gtn_monthly["gross_sales"] * 100).round(1)

    # Añadir nombres de meses
    month_names = {
        1: "Jan", 2: "Feb", 3: "Mar", 4: "Apr",
        5: "May", 6: "Jun", 7: "Jul", 8: "Aug",
        9: "Sep", 10: "Oct", 11: "Nov", 12: "Dec"
    }
    df_gtn_monthly["month_name"] = df_gtn_monthly["month"].map(month_names)

    st.dataframe(
        df_gtn_monthly[["month_name", "gross_sales", "gtn_amount", "gtn_pct"]].style.format({
            "gross_sales": "£{:,.0f}",
            "gtn_amount": "£{:,.0f}",
            "gtn_pct": "{:.1f}%"
        }),
        use_container_width=True,
        hide_index=True
    )

    # --- DESCARGA DE DATOS GTN ---
    st.divider()
    st.subheader("📥 Download GTN Data")

    col_btn1, col_btn2 = st.columns(2)

    with col_btn1:
        # Preparar datos GTN para descarga (formato largo)
        gtn_export_cols = [
            "client_name", "category", "structural_gtn_pct", "tactical_gtn_pct", 
            "total_gtn_pct", "gross_sales", "gtn_amount", "nts"
        ]
        df_gtn_export = df_gtn_filtered.groupby(["client_name", "category"]).agg({
            "structural_gtn_pct": "mean",
            "tactical_gtn_pct": "mean",
            "total_gtn_pct": "mean",
            "gross_sales": "sum",
            "gtn_amount": "sum",
            "nts": "sum"
        }).reset_index()

        df_gtn_export["structural_gtn_pct"] = (df_gtn_export["structural_gtn_pct"] * 100).round(1)
        df_gtn_export["tactical_gtn_pct"] = (df_gtn_export["tactical_gtn_pct"] * 100).round(1)
        df_gtn_export["total_gtn_pct"] = (df_gtn_export["total_gtn_pct"] * 100).round(1)

        csv_gtn = df_gtn_export.to_csv(index=False).encode("utf-8")
        st.download_button(
            label="📥 Download GTN Summary",
            data=csv_gtn,
            file_name=f"gtn_summary_{selected_year}.csv",
            mime="text/csv",
            use_container_width=True
        )

    with col_btn2:
        # Descargar datos detallados de GTN
        gtn_detail_cols = [
            "year", "month", "client_name", "category", "sku", "product_name",
            "structural_gtn_pct", "tactical_gtn_pct", "total_gtn_pct", 
            "gross_sales", "gtn_amount", "nts"
        ]
        df_gtn_detail = df_gtn_filtered[gtn_detail_cols].copy()
        df_gtn_detail["structural_gtn_pct"] = (df_gtn_detail["structural_gtn_pct"] * 100).round(1)
        df_gtn_detail["tactical_gtn_pct"] = (df_gtn_detail["tactical_gtn_pct"] * 100).round(1)
        df_gtn_detail["total_gtn_pct"] = (df_gtn_detail["total_gtn_pct"] * 100).round(1)

        csv_gtn_detail = df_gtn_detail.to_csv(index=False).encode("utf-8")
        st.download_button(
            label="📥 Download GTN Detail",
            data=csv_gtn_detail,
            file_name=f"gtn_detail_{selected_year}.csv",
            mime="text/csv",
            use_container_width=True
        )
        
# ============================================================================
# TAB 4: RAW DATA 
# ============================================================================
with tab_raw:
    st.subheader(f"Raw Data by Account – {selected_year}")
    st.caption("P&L accounts as columns (GTS, Returns, Bonus, GTN, NTS, COGS, GP Std)")

    # Month filter for raw data
    month_options = sorted(df_filtered["month"].unique())
    selected_months_raw = st.multiselect(
        "Select Months",
        options=month_options,
        default=month_options if month_options else [],
        key="raw_months"
    )

    # Apply month filter
    df_raw = df_filtered[df_filtered["month"].isin(selected_months_raw)] if selected_months_raw else df_filtered

    # --- BUILD LONG FORMAT BY ACCOUNT ---
    # Create a list to store all account rows
    account_rows = []

    # Define the accounts and their corresponding columns
    account_mapping = {
        "Gross Sales": "gross_sales",
        "Returns": "returns",
        "Bonuses": "bonus",
        "GTN": "gtn_amount",
        "Net Trade Sales": "nts",
        "COGS": "cogs",
        "Gross Profit Std": "gp_std"
    }

    # Iterate over each row in the filtered dataframe
    for _, row in df_raw.iterrows():
        for account_name, col_name in account_mapping.items():
            value = row[col_name]
            # For negative accounts, we show absolute value
            if account_name in ["Gross Sales", "Net Trade Sales", "Gross Profit Std"]:
                display_value = value
            else:
                display_value = abs(value)
            
            account_rows.append({
                "Year": row["year"],
                "Month": row["month"],
                "Client": row["client_name"],
                "Client Code": row["client_code"],
                "SKU": row["sku"],
                "Product": row["product_name"],
                "Category": row["category"],
                "Channel": row["channel"],
                "Account": account_name,
                "Value": display_value
            })

    # Convert to DataFrame
    df_accounts = pd.DataFrame(account_rows)

    # Display metrics
    col1, col2, col3 = st.columns(3)
    total_rows = len(df_accounts)
    total_gp = df_accounts[df_accounts["Account"] == "Gross Profit Std"]["Value"].sum() if not df_accounts.empty else 0
    total_nts = df_accounts[df_accounts["Account"] == "Net Trade Sales"]["Value"].sum() if not df_accounts.empty else 0
    gp_pct = (total_gp / total_nts * 100) if total_nts > 0 else 0

    col1.metric("📋 Total Rows", f"{total_rows:,}")
    col2.metric("💎 GP Std", f"£{total_gp:,.0f}")
    col3.metric("📈 GP %", f"{gp_pct:.1f}%")

    st.divider()

    # ============================================================================
    # SECTION 1: PIVOT VIEW (Accounts as columns)
    # ============================================================================
    st.subheader("📊 Pivot View: Accounts as columns")

    if not df_accounts.empty:
        # Create a pivot table for better visualization
        pivot_cols = ["Year", "Month", "Client", "Client Code", "Channel", "Category", "SKU", "Product"]
        pivot_df = df_accounts.pivot_table(
            index=pivot_cols,
            columns="Account",
            values="Value",
            aggfunc="sum"
        ).reset_index()

        # Reorder columns for better display
        col_order = ["Year", "Month", "Client", "Client Code", "Channel", "Category", "SKU", "Product",
                    "Gross Sales", "Returns", "Bonuses", "GTN", "Net Trade Sales", "COGS", "Gross Profit Std"]
        
        # Only keep columns that exist
        col_order = [c for c in col_order if c in pivot_df.columns]
        pivot_df = pivot_df[col_order]

        st.dataframe(
            pivot_df.style.format({
                "Gross Sales": "£{:,.2f}",
                "Returns": "£{:,.2f}",
                "Bonuses": "£{:,.2f}",
                "GTN": "£{:,.2f}",
                "Net Trade Sales": "£{:,.2f}",
                "COGS": "£{:,.2f}",
                "Gross Profit Std": "£{:,.2f}"
            }),
            use_container_width=True,
            hide_index=True,
            height=500
        )
    else:
        st.info("No data available for the selected filters.")

    st.divider()

    # ============================================================================
    # SECTION 2: EXPORT EXACT FORMAT
    # ============================================================================
    st.subheader("📥 Export Exact Format")
    st.caption("Format: Year, Month, Client, Client Code, SKU, Account, Value")

    if not df_accounts.empty:
        # Select only the requested columns
        export_df = df_accounts[["Year", "Month", "Client", "Client Code", "SKU", "Account", "Value"]].copy()
        
        # Remove duplicates if any
        export_df = export_df.drop_duplicates()
        
        # Show sample
        st.caption(f"Preview ({len(export_df):,} rows)")
        st.dataframe(
            export_df.head(20).style.format({
                "Value": "£{:,.2f}"
            }),
            use_container_width=True,
            hide_index=True,
            height=250
        )
        
        # Download button
        csv_export = export_df.to_csv(index=False).encode("utf-8")
        st.download_button(
            label="📥 Download Full Raw Data (Year, Month, Client, Client Code, SKU, Account, Value)",
            data=csv_export,
            file_name=f"pl_raw_data_exact_format_{selected_year}.csv",
            mime="text/csv",
            use_container_width=True
        )
    else:
        st.info("No data available for the selected filters.")
