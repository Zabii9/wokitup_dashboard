import streamlit as st
import pandas as pd
import pymysql
import plotly.express as px
import plotly.graph_objects as go
from plotly.subplots import make_subplots
from datetime import datetime, date
import calendar
import warnings
warnings.filterwarnings('ignore')

# ─── Page Config ──────────────────────────────────────────────────────────────
st.set_page_config(
    page_title="Restaurant Analytics",
    page_icon="🍽️",
    layout="wide",
    initial_sidebar_state="expanded"
)

# ─── Custom CSS ───────────────────────────────────────────────────────────────
st.markdown("""
<style>
    @import url('https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700&display=swap');
    html, body, [class*="css"] { font-family: 'Inter', sans-serif; }
    .main { background-color: #0f1117; }
    .metric-card {
        background: linear-gradient(135deg, #1e2130 0%, #252a3d 100%);
        border: 1px solid #2d3550;
        border-radius: 12px;
        padding: 20px 24px;
        text-align: center;
        box-shadow: 0 4px 20px rgba(0,0,0,0.3);
    }
    .metric-card .label {
        font-size: 12px; font-weight: 600; letter-spacing: 1px;
        text-transform: uppercase; color: #8892b0; margin-bottom: 8px;
    }
    .metric-card .value { font-size: 28px; font-weight: 700; color: #e6edf3; }
    .metric-card .delta { font-size: 13px; margin-top: 4px; font-weight: 500; }
    .delta-pos { color: #3ddc97; }
    .delta-neg { color: #ff6b6b; }
    .section-title {
        font-size: 18px; font-weight: 700; color: #cdd6f4;
        margin: 24px 0 12px 0; padding-bottom: 8px;
        border-bottom: 2px solid #2d3550;
    }
    .filter-badge {
        background: #7c3aed22; border: 1px solid #7c3aed55;
        border-radius: 8px; padding: 8px 14px; margin-bottom: 16px;
        color: #a78bfa; font-size: 13px; font-weight: 600;
    }
    div[data-testid="stSelectbox"] label,
    div[data-testid="stDateInput"] label,
    div[data-testid="stMultiSelect"] label {
        color: #8892b0 !important; font-size: 13px !important; font-weight: 600 !important;
    }
    .stTabs [data-baseweb="tab-list"] {
        background-color: #1e2130; border-radius: 10px; padding: 4px; gap: 4px;
    }
    .stTabs [data-baseweb="tab"] {
        color: #8892b0; font-weight: 600; border-radius: 8px; padding: 8px 20px;
    }
    .stTabs [aria-selected="true"] { background-color: #7c3aed !important; color: white !important; }
    .stDataFrame { border-radius: 10px; overflow: hidden; }
    footer { visibility: hidden; }
    #MainMenu { visibility: hidden; }
</style>
""", unsafe_allow_html=True)

# ─── DB Connection ─────────────────────────────────────────────────────────────
@st.cache_resource
def get_connection():
    db = st.secrets["mysql"]
    return pymysql.connect(
        host=db["host"],
        user=db["user"],
        password=db["password"],
        database=db["database"],
        port=int(db.get("port", 3306)),
        connect_timeout=15,
        cursorclass=pymysql.cursors.DictCursor
    )

@st.cache_data(ttl=300, show_spinner=False)
def run_query(sql: str) -> pd.DataFrame:
    try:
        conn = get_connection()
        with conn.cursor() as cur:
            cur.execute(sql)
            rows = cur.fetchall()
        return pd.DataFrame(rows)
    except Exception as e:
        st.error(f"DB Error: {e}")
        return pd.DataFrame()

# ─── Sidebar — Global Date Filter ─────────────────────────────────────────────
with st.sidebar:
    st.markdown("## 🍽️ Restaurant Analytics")
    st.markdown("---")
    st.markdown("### 📅 Date Range")

    DEFAULT_START = date(2026, 5, 1)
    DEFAULT_END   = date.today()

    start_date = st.date_input("Start Date", value=DEFAULT_START,
                                min_value=date(2026, 5, 1), max_value=DEFAULT_END)
    end_date   = st.date_input("End Date",   value=DEFAULT_END,
                                min_value=start_date, max_value=date(2030, 12, 31))

    if start_date > end_date:
        st.error("Start date must be before end date.")
        st.stop()

    START = start_date.strftime("%Y-%m-%d")
    END   = end_date.strftime("%Y-%m-%d")

    st.markdown("---")
    if st.button("🔄 Refresh Data", use_container_width=True):
        st.cache_data.clear()
        st.rerun()

    st.markdown("---")
    st.markdown(
        f"<small style='color:#555'>Connected to MySQL<br>db26619.public.databaseasp.net<br><br>"
        f"Filter: {start_date.strftime('%d %b %Y')} → {end_date.strftime('%d %b %Y')}</small>",
        unsafe_allow_html=True
    )

# ─── Plotly Theme ──────────────────────────────────────────────────────────────
CHART_THEME = dict(
    paper_bgcolor="rgba(0,0,0,0)",
    plot_bgcolor="rgba(0,0,0,0)",
    font=dict(family="Inter", color="#8892b0"),
    xaxis=dict(gridcolor="#2d3550", zerolinecolor="#2d3550"),
    yaxis=dict(gridcolor="#2d3550", zerolinecolor="#2d3550"),
    margin=dict(l=20, r=20, t=40, b=20),
)
PALETTE = ["#7c3aed", "#3ddc97", "#f59e0b", "#60a5fa", "#f472b6", "#34d399"]

def apply_theme(fig):
    fig.update_layout(**CHART_THEME)
    return fig

# ─── Header ───────────────────────────────────────────────────────────────────
st.markdown("## 🍽️ Restaurant Performance Dashboard")
st.markdown(
    f"<div class='filter-badge'>📅 Showing data: "
    f"<b>{start_date.strftime('%d %b %Y')}</b> → <b>{end_date.strftime('%d %b %Y')}</b></div>",
    unsafe_allow_html=True
)

# ─── Build Queries with date params ───────────────────────────────────────────

DAILY_SALES_SQL = f"""
WITH daily_sales AS (
    SELECT 
        business_date,
        COUNT(o.id) AS total_orders,
        SUM(o.order_amount + o.delivery_charge) AS total_amount,
        SUM(CASE WHEN o.order_type = 'delivery'
            THEN o.order_amount + o.delivery_charge ELSE 0 END) AS delivery,
        SUM(CASE WHEN o.order_type = 'dine_in'
            THEN o.order_amount + o.delivery_charge ELSE 0 END) AS dinein,
        SUM(CASE WHEN o.order_type IN ('pos','take_away')
            THEN o.order_amount + o.delivery_charge ELSE 0 END) AS take_away,
        DATE_FORMAT(MIN(o.created_at), '%h:%i %p') AS first_order_time,
        DATE_FORMAT(MAX(o.created_at), '%h:%i %p') AS last_order_time
    FROM (
        SELECT o.*,
            CASE
                WHEN TIME(o.created_at) >= '14:00:00' THEN DATE(o.created_at)
                WHEN TIME(o.created_at) < '04:00:00' THEN DATE_SUB(DATE(o.created_at), INTERVAL 1 DAY)
                ELSE DATE(o.created_at)
            END AS business_date
        FROM orders o
        WHERE o.order_status NOT IN ('canceled','returned')
    ) o
    GROUP BY business_date
)
SELECT 
    d.business_date,
    d.total_orders,
    d.total_amount,
    d.delivery,
    d.dinein,
    d.take_away,
    d.first_order_time,
    d.last_order_time,
    lm.total_amount AS last_month_same_day_sales
FROM daily_sales d
LEFT JOIN daily_sales lm
    ON lm.business_date = DATE_SUB(d.business_date, INTERVAL 1 MONTH)
WHERE d.business_date BETWEEN '{START}' AND '{END}'
ORDER BY d.business_date;
"""

PRODUCT_SQL = f"""
SELECT 
    p.`name`,
    SUM(o.quantity) AS Qty,
    SUM((o.price - discount_on_product) * o.quantity) AS Amount,
    COUNT(oo.user_id) AS Customers,
    c.name AS Category,
    SUM(addon.addon_total) AS AddonAmount
FROM (
    SELECT o.*,
        CASE
            WHEN TIME(o.created_at) >= '14:00:00' THEN DATE(o.created_at)
            WHEN TIME(o.created_at) < '04:00:00' THEN DATE_SUB(DATE(o.created_at), INTERVAL 1 DAY)
            ELSE DATE(o.created_at)
        END AS business_date
    FROM order_details o
    LEFT JOIN orders oo ON oo.id = o.order_id
    WHERE oo.order_status NOT IN ('canceled','returned')
) o
LEFT JOIN (
    SELECT *, JSON_UNQUOTE(JSON_EXTRACT(category_ids, '$[0].id')) AS cat_id
    FROM products
) p ON p.id = o.product_id
LEFT JOIN orders oo ON oo.id = o.order_id
LEFT JOIN categories c ON c.id = p.cat_id
LEFT JOIN (
    SELECT od.id AS order_detail_id,
        SUM(q.qty * pr.price) AS addon_total
    FROM order_details od
    JOIN JSON_TABLE(od.add_on_qtys, '$[*]'
        COLUMNS (idx FOR ORDINALITY, qty INT PATH '$')) q
    JOIN JSON_TABLE(od.add_on_prices, '$[*]'
        COLUMNS (idx FOR ORDINALITY, price DECIMAL(10,2) PATH '$')) pr
    ON q.idx = pr.idx
    GROUP BY od.id
) addon ON addon.order_detail_id = o.id
WHERE oo.order_status NOT IN ('canceled','returned')
  AND business_date BETWEEN '{START}' AND '{END}'
GROUP BY p.`name`, c.name
ORDER BY p.name ASC, Qty DESC;
"""

MOM_CATEGORY_SQL = f"""
SELECT
    year, month, category, category_sales,
    LAG(category_sales) OVER (PARTITION BY category ORDER BY year, month) AS prev_month_sales,
    ROUND(
        (category_sales - LAG(category_sales) OVER (PARTITION BY category ORDER BY year, month))
        / NULLIF(LAG(category_sales) OVER (PARTITION BY category ORDER BY year, month), 0) * 100, 2
    ) AS mom_growth_pct
FROM (
    SELECT
        YEAR(oo.created_at) AS year,
        MONTH(oo.created_at) AS month,
        c.name AS category,
        SUM((o.price - discount_on_product) * o.quantity) AS category_sales
    FROM order_details o
    LEFT JOIN orders oo ON oo.id = o.order_id
    LEFT JOIN products p ON p.id = o.product_id
    LEFT JOIN categories c ON c.id = JSON_UNQUOTE(JSON_EXTRACT(p.category_ids, '$[0].id'))
    WHERE oo.order_status NOT IN ('canceled','returned')
      AND DATE(oo.created_at) BETWEEN '{START}' AND '{END}'
    GROUP BY year, month, category
) t
ORDER BY category, year, month;
"""

PERIOD_SQL = f"""
SELECT 
    YEAR(business_date) AS Yearr,
    MONTH(business_date) AS Monthh,
    CONCAT(MONTH(business_date),'-',YEAR(business_date)) AS m,
    CASE 
        WHEN DAY(business_date) BETWEEN 1 AND 10 THEN 'Day_1_to_10'
        WHEN DAY(business_date) BETWEEN 11 AND 20 THEN 'Day_11_to_20'
        ELSE 'Day_21_to_End'
    END AS Period,
    SUM(order_amount) + SUM(delivery_charge) AS Amount
FROM (
    SELECT *,
        CASE
            WHEN TIME(o.created_at) >= '14:00:00' THEN DATE(o.created_at)
            WHEN TIME(o.created_at) < '04:00:00' THEN DATE(o.created_at) - INTERVAL 1 DAY
            ELSE DATE(o.created_at)
        END AS business_date
    FROM orders o
    WHERE o.order_status NOT IN ('canceled', 'returned')
) O
WHERE business_date BETWEEN '{START}' AND '{END}'
GROUP BY MONTH(business_date), YEAR(business_date),
    CASE 
        WHEN DAY(business_date) BETWEEN 1 AND 10 THEN 'Day_1_to_10'
        WHEN DAY(business_date) BETWEEN 11 AND 20 THEN 'Day_11_to_20'
        ELSE 'Day_21_to_End'
    END
ORDER BY YEAR(business_date), MONTH(business_date), MIN(DAY(business_date));
"""

DAYWISE_SQL = f"""
SELECT 
    YEAR(created_at) AS year,
    MONTH(created_at) AS month,
    DAYNAME(created_at) AS day_name,
    WEEKDAY(created_at) AS day_order,
    SUM(order_amount + delivery_charge) AS total_sales
FROM orders
WHERE order_status NOT IN ('canceled', 'returned')
  AND DATE(created_at) BETWEEN '{START}' AND '{END}'
GROUP BY YEAR(created_at), MONTH(created_at), DAYNAME(created_at), WEEKDAY(created_at)
ORDER BY year, month, day_order;
"""

AOV_MONTHLY_SQL = f"""
SELECT
    YEAR(business_date) AS year,
    MONTH(business_date) AS month,
    SUM(order_amount + delivery_charge) AS total_sales,
    COUNT(DISTINCT id) AS total_orders,
    ROUND(SUM(order_amount + delivery_charge) / NULLIF(COUNT(DISTINCT id), 0), 2) AS monthly_aov
FROM (
    SELECT o.id, o.order_amount, o.delivery_charge,
        CASE
            WHEN TIME(o.created_at) >= '14:00:00' THEN DATE(o.created_at)
            WHEN TIME(o.created_at) < '04:00:00' THEN DATE(o.created_at) - INTERVAL 1 DAY
            ELSE DATE(o.created_at)
        END AS business_date
    FROM orders o
    WHERE o.order_status NOT IN ('canceled', 'returned')
) t
WHERE business_date BETWEEN '{START}' AND '{END}'
GROUP BY YEAR(business_date), MONTH(business_date)
ORDER BY year, month;
"""

AOV_WEEKDAY_SQL = f"""
SELECT
    DAYNAME(business_date) AS weekday_name,
    WEEKDAY(business_date) AS weekday_order,
    SUM(order_amount + delivery_charge) AS total_sales,
    COUNT(DISTINCT id) AS total_orders,
    ROUND(SUM(order_amount + delivery_charge) / NULLIF(COUNT(DISTINCT id), 0), 2) AS aov
FROM (
    SELECT o.id, o.order_amount, o.delivery_charge,
        CASE
            WHEN TIME(o.created_at) >= '14:00:00' THEN DATE(o.created_at)
            WHEN TIME(o.created_at) < '04:00:00' THEN DATE(o.created_at) - INTERVAL 1 DAY
            ELSE DATE(o.created_at)
        END AS business_date
    FROM orders o
    WHERE o.order_status NOT IN ('canceled', 'returned')
) t
WHERE business_date BETWEEN '{START}' AND '{END}'
GROUP BY DAYNAME(business_date), WEEKDAY(business_date)
ORDER BY weekday_order;
"""

EXPENSES_SQL = f"""
SELECT 
    e.id,
    date(e.expense_datee) AS expense_date,
    e.amount,
    ec.name AS category
FROM (select *,CASE
            WHEN TIME(created_at) >= '14:00:00'
                THEN DATE(created_at)
            WHEN TIME(created_at) < '04:00:00'
                THEN DATE(created_at) - INTERVAL 1 DAY
            ELSE DATE(created_at)
        END AS expense_datee from expenses) e
LEFT JOIN expense_categories ec ON ec.id = e.expense_category_id
WHERE DATE(e.expense_date) BETWEEN '{START}' AND '{END}'
ORDER BY e.expense_date;
"""

# ─── Load Data ────────────────────────────────────────────────────────────────
with st.spinner("Loading data…"):
    df_daily    = run_query(DAILY_SALES_SQL)
    df_product  = run_query(PRODUCT_SQL)
    df_mom      = run_query(MOM_CATEGORY_SQL)
    df_period   = run_query(PERIOD_SQL)
    df_day      = run_query(DAYWISE_SQL)
    df_aov_m    = run_query(AOV_MONTHLY_SQL)
    df_aov_w    = run_query(AOV_WEEKDAY_SQL)
    df_expenses = run_query(EXPENSES_SQL)

# ─── TABS ─────────────────────────────────────────────────────────────────────
tab1, tab2, tab3, tab4, tab5, tab6 = st.tabs([
    "📅 Daily Sales", "🛍️ Products", "📊 MoM Trends", "📈 AOV", "🗓️ Patterns", "💸 Expenses"
])

# ══════════════════════════════════════════════════════════════════════════════
# TAB 1 · Daily Sales
# ══════════════════════════════════════════════════════════════════════════════
with tab1:
    if df_daily.empty:
        st.info("No daily sales data found for the selected date range.")
    else:
        df_daily["business_date"] = pd.to_datetime(df_daily["business_date"])
        for c in ["total_amount","delivery","dinein","take_away","last_month_same_day_sales","total_orders"]:
            df_daily[c] = pd.to_numeric(df_daily[c], errors="coerce").fillna(0)
        df_daily = df_daily.sort_values("business_date")

        total_rev = df_daily["total_amount"].sum()
        total_ord = df_daily["total_orders"].sum()
        avg_ord   = total_rev / total_ord if total_ord else 0
        lm_rev    = df_daily["last_month_same_day_sales"].sum()
        delta_pct = ((total_rev - lm_rev) / lm_rev * 100) if lm_rev else 0

        # ── Prepare daily expenses lookup keyed by business_date ──────────────
        daily_exp_map = {}
        if not df_expenses.empty:
            df_expenses["amount"] = pd.to_numeric(df_expenses["amount"], errors="coerce").fillna(0)
            df_expenses["expense_date"] = pd.to_datetime(df_expenses["expense_date"])
            daily_exp_map = (
                df_expenses.groupby("expense_date")["amount"]
                .sum()
                .to_dict()
            )

        total_exp  = df_expenses["amount"].sum() if not df_expenses.empty else 0
        net_profit = total_rev - total_exp

        # ── KPI Cards ─────────────────────────────────────────────────────────
        c1, c2, c3, c4, c5 = st.columns(5)
        for col, label, value, delta in [
            (c1, "Total Revenue",   f"PKR {total_rev:,.0f}", f"{delta_pct:+.1f}% vs last month"),
            (c2, "Total Orders",    f"{int(total_ord):,}", ""),
            (c3, "Avg Order Value", f"PKR {avg_ord:,.0f}", ""),
            (c4, "Total Expenses",  f"PKR {total_exp:,.0f}", ""),
            (c5, "Net Profit",      f"PKR {net_profit:,.0f}", ""),
        ]:
            dclass = "delta-pos" if "+" in delta else "delta-neg" if delta.startswith("-") else ""
            col.markdown(f"""<div class="metric-card">
                <div class="label">{label}</div>
                <div class="value">{value}</div>
                <div class="delta {dclass}">{delta}</div>
            </div>""", unsafe_allow_html=True)

        st.markdown("<div class='section-title'>Daily Revenue vs Last Month Same Day</div>", unsafe_allow_html=True)
        fig = go.Figure()
        fig.add_trace(go.Bar(x=df_daily["business_date"], y=df_daily["total_amount"],
                             name="This Period", marker_color=PALETTE[0], opacity=0.9,
                             text=df_daily["total_amount"], texttemplate="%{text:,.0f}",
                             textposition="outside", textfont=dict(size=10)))
        fig.add_trace(go.Scatter(x=df_daily["business_date"], y=df_daily["last_month_same_day_sales"],
                                 name="Last Month Same Day", mode="lines+markers",
                                 line=dict(color=PALETTE[2], width=2, dash="dot"), marker=dict(size=6)))
        fig.update_layout(title="Revenue Comparison", legend=dict(orientation="h", y=1.1))
        st.plotly_chart(apply_theme(fig), use_container_width=True)

        st.markdown("<div class='section-title'>Order Type Breakdown</div>", unsafe_allow_html=True)
        col1, col2 = st.columns(2)
        with col1:
            mix = {"Delivery": df_daily["delivery"].sum(),
                   "Dine-In":  df_daily["dinein"].sum(),
                   "Take-Away": df_daily["take_away"].sum()}
            fig_pie = px.pie(names=list(mix.keys()), values=list(mix.values()),
                             color_discrete_sequence=PALETTE, hole=0.45)
            fig_pie.update_traces(textinfo="label+percent", textfont_size=13)
            fig_pie.update_layout(title="Sales Mix", legend=dict(orientation="h", y=-0.1))
            st.plotly_chart(apply_theme(fig_pie), use_container_width=True)
        with col2:
            fig_bar = go.Figure()
            for cn, color, label in [("delivery", PALETTE[0], "Delivery"),
                                      ("dinein",   PALETTE[1], "Dine-In"),
                                      ("take_away",PALETTE[2], "Take-Away")]:
                fig_bar.add_trace(go.Bar(x=df_daily["business_date"], y=df_daily[cn],
                                         name=label, marker_color=color,
                                         text=df_daily[cn], texttemplate="%{text:,.0f}",
                                         textposition="inside", textfont=dict(size=9)))
            fig_bar.update_layout(barmode="stack", title="Daily Breakdown by Type")
            st.plotly_chart(apply_theme(fig_bar), use_container_width=True)

        # ── Daily Detail Table with Expenses column ───────────────────────────
        st.markdown("<div class='section-title'>Daily Detail Table</div>", unsafe_allow_html=True)
        disp = df_daily.copy()

        # Map daily expenses onto each business_date row
        disp["Expenses"] = disp["business_date"].map(daily_exp_map).fillna(0)
        disp["Net Profit"] = disp["total_amount"] - disp["Expenses"]

        disp["business_date"] = disp["business_date"].dt.strftime("%d %b %Y")

        # Reorder columns: Date, Orders, Revenue, Expenses, Net Profit, Delivery, Dine-In, Take-Away, First Order, Last Order, Last Month
        disp = disp[["business_date","total_orders","total_amount","Expenses","Net Profit",
                     "delivery","dinein","take_away","first_order_time","last_order_time",
                     "last_month_same_day_sales"]]
        disp.columns = ["Date","Orders","Revenue","Expenses","Net Profit",
                        "Delivery","Dine-In","Take-Away","First Order","Last Order","Last Month"]

        st.dataframe(disp.style.format({
            "Revenue":    "PKR {:,.0f}",
            "Expenses":   "PKR {:,.0f}",
            "Net Profit": "PKR {:,.0f}",
            "Delivery":   "PKR {:,.0f}",
            "Dine-In":    "PKR {:,.0f}",
            "Take-Away":  "PKR {:,.0f}",
            "Last Month": "PKR {:,.0f}",
        }), use_container_width=True, hide_index=True)

# ══════════════════════════════════════════════════════════════════════════════
# TAB 2 · Products
# ══════════════════════════════════════════════════════════════════════════════
with tab2:
    if df_product.empty:
        st.info("No product data for the selected date range.")
    else:
        df_product = df_product.fillna(0)
        for c in ["Amount","Qty","AddonAmount","Customers"]:
            df_product[c] = pd.to_numeric(df_product[c], errors="coerce").fillna(0)

        cats = ["All"] + sorted(df_product["Category"].dropna().unique().tolist())
        sel_cat = st.selectbox("Filter by Category", cats)
        df_p = df_product if sel_cat == "All" else df_product[df_product["Category"] == sel_cat]

        c1, c2, c3 = st.columns(3)
        c1.markdown(f"""<div class="metric-card"><div class="label">Total Products</div>
            <div class="value">{len(df_p)}</div></div>""", unsafe_allow_html=True)
        c2.markdown(f"""<div class="metric-card"><div class="label">Total Revenue</div>
            <div class="value">PKR {df_p['Amount'].sum():,.0f}</div></div>""", unsafe_allow_html=True)
        c3.markdown(f"""<div class="metric-card"><div class="label">Total Qty Sold</div>
            <div class="value">{df_p['Qty'].sum():,.0f}</div></div>""", unsafe_allow_html=True)

        col1, col2 = st.columns(2)
        with col1:
            st.markdown("<div class='section-title'>Top 15 by Revenue</div>", unsafe_allow_html=True)
            fig = px.bar(df_p.nlargest(15, "Amount"), x="Amount", y="name", orientation="h",
                         color="Category", color_discrete_sequence=PALETTE,
                         labels={"Amount": "Revenue (PKR)", "name": ""})
            fig.update_traces(texttemplate="%{x:,.0f}", textposition="outside", textfont=dict(size=10))
            fig.update_layout(title="Top 15 Products", yaxis=dict(autorange="reversed"))
            st.plotly_chart(apply_theme(fig), use_container_width=True)
        with col2:
            st.markdown("<div class='section-title'>Category Revenue Share</div>", unsafe_allow_html=True)
            cat_grp = df_p.groupby("Category")["Amount"].sum().reset_index()
            fig2 = px.pie(cat_grp, names="Category", values="Amount",
                          color_discrete_sequence=PALETTE, hole=0.4)
            fig2.update_traces(textinfo="label+percent")
            st.plotly_chart(apply_theme(fig2), use_container_width=True)

        st.markdown("<div class='section-title'>Add-On Revenue (Top 10)</div>", unsafe_allow_html=True)
        addon_df = df_p[df_p["AddonAmount"] > 0].nlargest(10, "AddonAmount")
        if not addon_df.empty:
            fig3 = px.bar(addon_df, x="name", y="AddonAmount",
                          color_discrete_sequence=[PALETTE[3]],
                          labels={"AddonAmount": "Add-On Revenue (PKR)", "name": "Product"},
                          text="AddonAmount")
            fig3.update_traces(texttemplate="%{text:,.0f}", textposition="outside", textfont=dict(size=10))
            st.plotly_chart(apply_theme(fig3), use_container_width=True)
        else:
            st.info("No add-on revenue data for the selected range.")

        st.markdown("<div class='section-title'>Full Product Table</div>", unsafe_allow_html=True)
        st.dataframe(
            df_p[["name","Category","Qty","Amount","AddonAmount","Customers"]]
            .sort_values("Amount", ascending=False)
            .style.format({"Amount": "PKR {:,.0f}", "AddonAmount": "PKR {:,.0f}"}),
            use_container_width=True, hide_index=True
        )

# ══════════════════════════════════════════════════════════════════════════════
# TAB 3 · MoM Trends
# ══════════════════════════════════════════════════════════════════════════════
with tab3:
    if df_mom.empty:
        st.info("No MoM data for the selected date range.")
    else:
        for c in ["category_sales","mom_growth_pct","prev_month_sales"]:
            df_mom[c] = pd.to_numeric(df_mom[c], errors="coerce").fillna(0)
        df_mom["month_label"] = df_mom.apply(
            lambda r: f"{calendar.month_abbr[int(r['month'])]} {int(r['year'])}", axis=1)
        months_order = (df_mom[["year","month","month_label"]]
                        .drop_duplicates().sort_values(["year","month"])["month_label"].tolist())

        cats_mom = sorted(df_mom["category"].dropna().unique().tolist())
        sel_cats = st.multiselect("Select Categories", cats_mom, default=cats_mom[:5])
        df_m = df_mom[df_mom["category"].isin(sel_cats)] if sel_cats else df_mom

        st.markdown("<div class='section-title'>Monthly Sales by Category</div>", unsafe_allow_html=True)
        fig = px.line(df_m, x="month_label", y="category_sales", color="category",
                      markers=True, color_discrete_sequence=PALETTE,
                      category_orders={"month_label": months_order},
                      labels={"category_sales": "Sales (PKR)", "month_label": "Month", "category": "Category"})
        st.plotly_chart(apply_theme(fig), use_container_width=True)

        st.markdown("<div class='section-title'>MoM Growth % Heatmap</div>", unsafe_allow_html=True)
        pivot = df_mom.pivot_table(index="category", columns="month_label", values="mom_growth_pct")
        if not pivot.empty:
            fig_h = px.imshow(pivot, color_continuous_scale="RdYlGn",
                              labels=dict(color="Growth %"), aspect="auto", zmin=-50, zmax=50)
            fig_h.update_layout(title="Month-over-Month Growth % by Category")
            st.plotly_chart(apply_theme(fig_h), use_container_width=True)

        st.markdown("<div class='section-title'>Stacked Revenue by Category</div>", unsafe_allow_html=True)
        fig_sb = px.bar(df_m, x="month_label", y="category_sales", color="category",
                        barmode="stack", category_orders={"month_label": months_order},
                        color_discrete_sequence=PALETTE,
                        labels={"category_sales": "Sales (PKR)", "month_label": "Month"},
                        text="category_sales")
        fig_sb.update_traces(texttemplate="%{text:,.0f}", textposition="inside", textfont=dict(size=9))
        st.plotly_chart(apply_theme(fig_sb), use_container_width=True)

# ══════════════════════════════════════════════════════════════════════════════
# TAB 4 · AOV
# ══════════════════════════════════════════════════════════════════════════════
with tab4:
    col1, col2 = st.columns(2)

    with col1:
        st.markdown("<div class='section-title'>Monthly AOV Trend</div>", unsafe_allow_html=True)
        if not df_aov_m.empty:
            for c in ["total_sales","total_orders","monthly_aov"]:
                df_aov_m[c] = pd.to_numeric(df_aov_m[c], errors="coerce").fillna(0)
            df_aov_m["month_label"] = df_aov_m.apply(
                lambda r: f"{calendar.month_abbr[int(r['month'])]} {int(r['year'])}", axis=1)

            fig = make_subplots(specs=[[{"secondary_y": True}]])
            fig.add_trace(go.Bar(x=df_aov_m["month_label"], y=df_aov_m["total_sales"],
                                 name="Total Sales", marker_color=PALETTE[0], opacity=0.7,
                                 text=df_aov_m["total_sales"], texttemplate="%{text:,.0f}",
                                 textposition="outside", textfont=dict(size=10)), secondary_y=False)
            fig.add_trace(go.Scatter(x=df_aov_m["month_label"], y=df_aov_m["monthly_aov"],
                                     name="AOV", mode="lines+markers",
                                     line=dict(color=PALETTE[2], width=3), marker=dict(size=8)), secondary_y=True)
            fig.update_layout(title="Monthly AOV", legend=dict(orientation="h", y=1.1), **CHART_THEME)
            fig.update_yaxes(title_text="Revenue (PKR)", secondary_y=False, gridcolor="#2d3550")
            fig.update_yaxes(title_text="AOV (PKR)", secondary_y=True, gridcolor="#2d3550")
            st.plotly_chart(fig, use_container_width=True)

            max_aov = df_aov_m.loc[df_aov_m["monthly_aov"].idxmax()]
            c1, c2 = st.columns(2)
            c1.markdown(f"""<div class="metric-card">
                <div class="label">Best AOV Month</div>
                <div class="value">{max_aov['month_label']}</div>
                <div class="delta delta-pos">PKR {max_aov['monthly_aov']:,.0f}</div>
            </div>""", unsafe_allow_html=True)
            c2.markdown(f"""<div class="metric-card">
                <div class="label">Avg Monthly AOV</div>
                <div class="value">PKR {df_aov_m['monthly_aov'].mean():,.0f}</div>
            </div>""", unsafe_allow_html=True)

    with col2:
        st.markdown("<div class='section-title'>AOV by Weekday</div>", unsafe_allow_html=True)
        if not df_aov_w.empty:
            for c in ["total_sales","total_orders","aov"]:
                df_aov_w[c] = pd.to_numeric(df_aov_w[c], errors="coerce").fillna(0)
            df_aov_w = df_aov_w.sort_values("weekday_order")
            day_order_list = ["Monday","Tuesday","Wednesday","Thursday","Friday","Saturday","Sunday"]
            fig2 = px.bar(df_aov_w, x="weekday_name", y="aov",
                          color="aov", color_continuous_scale="Purples",
                          labels={"weekday_name": "Day", "aov": "AOV (PKR)"},
                          category_orders={"weekday_name": day_order_list})
            fig2.update_traces(texttemplate="%{y:,.0f}", textposition="outside", textfont=dict(size=10))
            fig2.update_coloraxes(showscale=False)
            fig2.update_layout(title="AOV by Day of Week")
            st.plotly_chart(apply_theme(fig2), use_container_width=True)

            best_day = df_aov_w.loc[df_aov_w["aov"].idxmax()]
            st.markdown(f"""<div class="metric-card">
                <div class="label">Best AOV Day</div>
                <div class="value">{best_day['weekday_name']}</div>
                <div class="delta delta-pos">PKR {best_day['aov']:,.0f} per order</div>
            </div>""", unsafe_allow_html=True)

    if not df_aov_m.empty:
        st.markdown("<div class='section-title'>Orders vs AOV (Monthly Bubble)</div>", unsafe_allow_html=True)
        size_vals = df_aov_m["total_sales"].astype(float).tolist()
        fig3 = px.scatter(df_aov_m, x="total_orders", y="monthly_aov",
                          size=size_vals, text="month_label",
                          color="monthly_aov", color_continuous_scale="Viridis",
                          labels={"total_orders": "Total Orders", "monthly_aov": "AOV (PKR)"})
        fig3.update_traces(textposition="top center")
        fig3.update_coloraxes(showscale=False)
        st.plotly_chart(apply_theme(fig3), use_container_width=True)

# ══════════════════════════════════════════════════════════════════════════════
# TAB 5 · Patterns
# ══════════════════════════════════════════════════════════════════════════════
with tab5:
    col1, col2 = st.columns(2)

    with col1:
        st.markdown("<div class='section-title'>Day-of-Week Sales Heatmap</div>", unsafe_allow_html=True)
        if not df_day.empty:
            df_day["total_sales"] = pd.to_numeric(df_day["total_sales"], errors="coerce").fillna(0)
            df_day["month_label"] = df_day.apply(
                lambda r: f"{calendar.month_abbr[int(r['month'])]} {int(r['year'])}", axis=1)
            day_order_list = ["Monday","Tuesday","Wednesday","Thursday","Friday","Saturday","Sunday"]
            pivot_day = df_day.pivot_table(index="day_name", columns="month_label",
                                           values="total_sales", aggfunc="sum")
            pivot_day = pivot_day.reindex([d for d in day_order_list if d in pivot_day.index])
            fig = px.imshow(pivot_day, color_continuous_scale="Purples",
                            labels=dict(color="Sales (PKR)"), aspect="auto")
            fig.update_layout(title="Sales Intensity by Day & Month")
            st.plotly_chart(apply_theme(fig), use_container_width=True)

    with col2:
        st.markdown("<div class='section-title'>Average Sales by Day of Week</div>", unsafe_allow_html=True)
        if not df_day.empty:
            avg_day = df_day.groupby(["day_name","day_order"])["total_sales"].mean().reset_index()
            avg_day = avg_day.sort_values("day_order")
            fig2 = px.bar(avg_day, x="day_name", y="total_sales",
                          color="total_sales", color_continuous_scale="Purples",
                          labels={"day_name": "Day", "total_sales": "Avg Sales (PKR)"})
            fig2.update_traces(texttemplate="%{y:,.0f}", textposition="outside", textfont=dict(size=10))
            fig2.update_coloraxes(showscale=False)
            st.plotly_chart(apply_theme(fig2), use_container_width=True)

    st.markdown("<div class='section-title'>10-Day Period Analysis</div>", unsafe_allow_html=True)
    if not df_period.empty:
        df_period["Amount"] = pd.to_numeric(df_period["Amount"], errors="coerce").fillna(0)
        df_period["month_label"] = df_period.apply(
            lambda r: f"{calendar.month_abbr[int(r['Monthh'])]} {int(r['Yearr'])}", axis=1)
        period_labels = {"Day_1_to_10": "Days 1–10", "Day_11_to_20": "Days 11–20", "Day_21_to_End": "Days 21–End"}
        df_period["Period_Label"] = df_period["Period"].map(period_labels)

        months_sorted = (df_period[["Yearr","Monthh","month_label"]]
                         .drop_duplicates().sort_values(["Yearr","Monthh"])["month_label"].tolist())
        fig3 = px.bar(df_period, x="month_label", y="Amount", color="Period_Label",
                      barmode="group", color_discrete_sequence=PALETTE,
                      category_orders={"month_label": months_sorted,
                                       "Period_Label": ["Days 1–10","Days 11–20","Days 21–End"]},
                      labels={"Amount": "Revenue (PKR)", "month_label": "Month", "Period_Label": "Period"})
        fig3.update_traces(texttemplate="%{y:,.0f}", textposition="outside", textfont=dict(size=9))
        fig3.update_layout(title="Revenue by 10-Day Period per Month", legend=dict(orientation="h", y=1.1))
        st.plotly_chart(apply_theme(fig3), use_container_width=True)

        pivot_p = df_period.pivot_table(index="Period_Label", columns="month_label",
                                        values="Amount", aggfunc="sum")
        pivot_p = pivot_p.reindex([l for l in ["Days 1–10","Days 11–20","Days 21–End"] if l in pivot_p.index])
        avail_months = [m for m in months_sorted if m in pivot_p.columns]
        if avail_months:
            pivot_p = pivot_p[avail_months]
        st.dataframe(pivot_p.style.format("PKR {:,.0f}"), use_container_width=True)

# ══════════════════════════════════════════════════════════════════════════════
# TAB 6 · Expenses
# ══════════════════════════════════════════════════════════════════════════════
with tab6:
    if df_expenses.empty:
        st.info("No expenses data for the selected date range.")
    else:
        df_expenses["amount"] = pd.to_numeric(df_expenses["amount"], errors="coerce").fillna(0)
        df_expenses["expense_date"] = pd.to_datetime(df_expenses["expense_date"])

        total_exp     = df_expenses["amount"].sum()
        num_entries   = len(df_expenses)
        top_cat       = df_expenses.groupby("category")["amount"].sum().idxmax()
        avg_daily_exp = df_expenses.groupby("expense_date")["amount"].sum().mean()

        c1, c2, c3, c4 = st.columns(4)
        c1.markdown(f'''<div class="metric-card">
            <div class="label">Total Expenses</div>
            <div class="value">PKR {total_exp:,.0f}</div></div>''', unsafe_allow_html=True)
        c2.markdown(f'''<div class="metric-card">
            <div class="label">No. of Entries</div>
            <div class="value">{num_entries}</div></div>''', unsafe_allow_html=True)
        c3.markdown(f'''<div class="metric-card">
            <div class="label">Top Category</div>
            <div class="value" style="font-size:20px">{top_cat}</div></div>''', unsafe_allow_html=True)
        c4.markdown(f'''<div class="metric-card">
            <div class="label">Avg Daily Expense</div>
            <div class="value">PKR {avg_daily_exp:,.0f}</div></div>''', unsafe_allow_html=True)

        col1, col2 = st.columns(2)
        with col1:
            st.markdown("<div class='section-title'>Expenses by Category</div>", unsafe_allow_html=True)
            cat_grp = df_expenses.groupby("category")["amount"].sum().reset_index().sort_values("amount", ascending=False)
            fig = px.pie(cat_grp, names="category", values="amount",
                         color_discrete_sequence=PALETTE, hole=0.45)
            fig.update_traces(textinfo="label+percent", textfont_size=13)
            fig.update_layout(title="Expense Mix by Category", legend=dict(orientation="h", y=-0.1))
            st.plotly_chart(apply_theme(fig), use_container_width=True)

        with col2:
            st.markdown("<div class='section-title'>Category Breakdown (Bar)</div>", unsafe_allow_html=True)
            fig2 = px.bar(cat_grp, x="category", y="amount",
                          color="category", color_discrete_sequence=PALETTE,
                          labels={"amount": "Amount (PKR)", "category": "Category"})
            fig2.update_traces(texttemplate="%{y:,.0f}", textposition="outside", textfont=dict(size=10))
            fig2.update_layout(title="Expenses by Category", showlegend=False)
            st.plotly_chart(apply_theme(fig2), use_container_width=True)

        st.markdown("<div class='section-title'>Daily Expenses Over Time</div>", unsafe_allow_html=True)
        daily_exp_df = df_expenses.groupby("expense_date")["amount"].sum().reset_index()
        fig3 = go.Figure()
        fig3.add_trace(go.Bar(x=daily_exp_df["expense_date"], y=daily_exp_df["amount"],
                              marker_color=PALETTE[4], name="Daily Expenses", opacity=0.85,
                              text=daily_exp_df["amount"], texttemplate="%{text:,.0f}",
                              textposition="outside", textfont=dict(size=9)))
        fig3.add_trace(go.Scatter(x=daily_exp_df["expense_date"],
                                  y=daily_exp_df["amount"].rolling(7, min_periods=1).mean(),
                                  name="7-Day Avg", mode="lines",
                                  line=dict(color=PALETTE[2], width=2)))
        fig3.update_layout(title="Daily Expenses + 7-Day Rolling Average",
                           legend=dict(orientation="h", y=1.1))
        st.plotly_chart(apply_theme(fig3), use_container_width=True)

        st.markdown("<div class='section-title'>Monthly Expenses by Category (Stacked)</div>", unsafe_allow_html=True)
        df_expenses["month_label"] = df_expenses["expense_date"].apply(
            lambda d: f"{calendar.month_abbr[d.month]} {d.year}")
        monthly_cat = df_expenses.groupby(["month_label","category"])["amount"].sum().reset_index()
        month_order = (df_expenses[["expense_date","month_label"]]
                       .drop_duplicates().sort_values("expense_date")["month_label"].tolist())
        fig4 = px.bar(monthly_cat, x="month_label", y="amount", color="category",
                      barmode="stack", color_discrete_sequence=PALETTE,
                      category_orders={"month_label": month_order},
                      labels={"amount": "Amount (PKR)", "month_label": "Month", "category": "Category"})
        fig4.update_traces(texttemplate="%{y:,.0f}", textposition="inside", textfont=dict(size=9))
        fig4.update_layout(title="Monthly Expenses by Category", legend=dict(orientation="h", y=1.1))
        st.plotly_chart(apply_theme(fig4), use_container_width=True)

        st.markdown("<div class='section-title'>Expense Entries</div>", unsafe_allow_html=True)
        disp_exp = df_expenses[["expense_date","category","amount"]].copy()
        disp_exp["expense_date"] = disp_exp["expense_date"].dt.strftime("%d %b %Y")
        disp_exp.columns = ["Date","Category","Amount (PKR)"]
        st.dataframe(disp_exp.sort_values("Date", ascending=False)
                     .style.format({"Amount (PKR)": "PKR {:,.0f}"}),
                     use_container_width=True, hide_index=True)