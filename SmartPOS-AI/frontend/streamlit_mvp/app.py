

import streamlit as st
from turtle import left
import pandas as pd
import numpy as np
import plotly.express as px
from datetime import datetime

import api_client as api
import data_sources as ds 
import os
import upi_qr
from datetime import timedelta,datetime
SHOP_UPI_ID = os.environ.get("SMARTPOS_SHOP_UPI_ID", "divyanshpratap175@ybl")
SHOP_NAME = os.environ.get("SMARTPOS_SHOP_NAME", "SmartPOS Shop") # kept only for the Excel template generator

# ----------------------------------------------------------------------------
# Page config & global style
# ----------------------------------------------------------------------------
st.set_page_config(
    page_title="SmartPOS AI",
    page_icon="🛒",
    layout="wide",
    initial_sidebar_state="expanded",
)

PRIMARY = "#2563EB"
GREEN = "#16A34A"
AMBER = "#D97706"
RED = "#DC2626"

st.markdown("""
<style>
.metric-card {
    background: #FFFFFF;
    border: 1px solid #E5E7EB;
    border-radius: 12px;
    padding: 18px 20px;
    box-shadow: 0 1px 2px rgba(0,0,0,0.04);
}
.metric-label { font-size: 0.8rem; color: #6B7280; font-weight: 600; text-transform: uppercase; letter-spacing: 0.03em;}
.metric-value { font-size: 1.6rem; font-weight: 700; color: #111827; }
.metric-sub { font-size: 0.78rem; color: #9CA3AF; }
.pill {
    display: inline-block; padding: 2px 10px; border-radius: 999px;
    font-size: 0.72rem; font-weight: 600;
}
.pill-high { background:#FEE2E2; color:#DC2626; }
.pill-medium { background:#FEF3C7; color:#D97706; }
.pill-low { background:#DBEAFE; color:#2563EB; }
section[data-testid="stSidebar"] { background-color: #0F172A; }
section[data-testid="stSidebar"] * { color: #E2E8F0 !important; }
</style>
""", unsafe_allow_html=True)


def metric_card(label, value, sub=""):
    st.markdown(f"""
    <div class="metric-card">
        <div class="metric-label">{label}</div>
        <div class="metric-value">{value}</div>
        <div class="metric-sub">{sub}</div>
    </div>
    """, unsafe_allow_html=True)


# ----------------------------------------------------------------------------
# Session state
# ----------------------------------------------------------------------------
if "cart" not in st.session_state:
    st.session_state.cart = {}
if "chat_history" not in st.session_state:
    st.session_state.chat_history = []
if "token" not in st.session_state:
    st.session_state.token = None
    st.session_state.username = None
    st.session_state.role = None


def logout():
    st.session_state.token = None
    st.session_state.username = None
    st.session_state.role = None
    st.session_state.cart = {}
    st.session_state.chat_history = []


# ----------------------------------------------------------------------------
# Backend connectivity check — before even showing the login form, since a
# dead backend means login can't work either.
# ----------------------------------------------------------------------------
if not api.is_healthy():
    st.error(
        f"**Can't reach the backend** at `{api.API_BASE_URL}`.\n\n"
        f"Start it in a separate terminal:\n\n"
        f"```bash\ncd backend\nuvicorn main:app --reload\n```"
    )
    st.stop()

# ----------------------------------------------------------------------------
# Login gate — every page below this requires a signed-in user, since
# checkout/refunds/catalog changes/the assistant are all auth-protected now.
# ----------------------------------------------------------------------------
if not st.session_state.token:
    st.title("🛒 SmartPOS AI")
    st.caption("Sign in to continue.")

    with st.form("login_form"):
        username = st.text_input("Username")
        password = st.text_input("Password", type="password")
        submitted = st.form_submit_button("Sign in", type="primary")

    if submitted:
        try:
            result = api.login(username, password)
        except api.APIError as e:
            st.error(f"Login failed: {e}")
        else:
            st.session_state.token = result["access_token"]
            st.session_state.username = result["username"]
            st.session_state.role = result["role"]
            st.rerun()

    st.caption(
"Don't have an account? Ask your shop owner to create one for you.")
    
    st.stop()

token = st.session_state.token
role = st.session_state.role

# ----------------------------------------------------------------------------
# Cached backend calls
# ----------------------------------------------------------------------------
@st.cache_data(ttl=10, show_spinner=False)
def load_products():
    return api.get_products()

@st.cache_data(ttl=5, show_spinner=False)
def load_dashboard_summary(start_date=None, end_date=None):
    return api.get_dashboard_summary(start_date=start_date, end_date=end_date)

@st.cache_data(ttl=15, show_spinner=False)
def load_history(days=30, start_date=None, end_date=None):
    return api.get_transaction_history(days=days, start_date=start_date, end_date=end_date)

@st.cache_data(ttl=5, show_spinner=False)
def load_todays_transactions():
    return api.get_todays_transactions()

@st.cache_data(ttl=10, show_spinner=False)
def load_reorder_suggestions():
    return api.get_reorder_suggestions()

@st.cache_data(ttl=15, show_spinner=False)
def load_fraud_alerts():
    return api.get_fraud_alerts()


def refresh_all():
    load_products.clear()
    load_history.clear()
    load_dashboard_summary.clear()
    load_todays_transactions.clear()
    load_reorder_suggestions.clear()
    load_fraud_alerts.clear()


def call_authed(fn, *args, **kwargs):
    """Wraps any token-requiring api_client call: on a 401, forces logout
    and reruns to the login screen instead of just showing an error the
    user can't act on."""
    try:
        return fn(*args, **kwargs)
    except api.AuthError:
        logout()
        st.warning("Your session expired — please sign in again.")
        st.rerun()

# ----------------------------------------------------------------------------
# Sidebar navigation
# ----------------------------------------------------------------------------
PAGES = ["📊 Dashboard", "🧾 Billing (POS)", "📦 Inventory", "🤖 AI Business Assistant", "🚨 Fraud & Alerts"]
if role == "owner":
    PAGES.append("🔌 Data Source")  # catalog reset/upload/user management — owner only

with st.sidebar:
    st.markdown("## 🛒 SmartPOS AI")
    st.caption("AI-powered Retail Operating System")
    st.markdown("---")
    page = st.radio("Navigate", PAGES, label_visibility="collapsed")
    st.markdown("---")
    st.caption(f"Signed in as **{st.session_state.username}**  \nRole: `{role}`")
    if st.button("🚪 Log out", use_container_width=True):
        logout()
        st.rerun()
    st.markdown("---")
    st.caption(f"Today: {datetime.now().strftime('%d %b %Y')}")
    st.caption(f"🟢 Backend: `{api.API_BASE_URL}`")

try:
    products_df = load_products()
except api.APIError as e:
    st.error(f"Couldn't load products from the backend: {e}")
    st.stop()

# --- THE FIX ---
if products_df.empty and page != "🔌 Data Source":
    st.warning("No products in the catalog right now. Go to **🔌 Data Source** to load sample data or upload your own.")
    st.stop()
# --- END FIX ---

# ----------------------------------------------------------------------------
# PAGE: DASHBOARD
# ----------------------------------------------------------------------------

import streamlit as st
import plotly.express as px
from datetime import datetime, timedelta

# Placeholders for defined constants/functions in your codebase
# PRIMARY = "#2563EB"
# AMBER = "#F59E0B"
# GREEN = "#10B981"

if page == "📊 Dashboard":
    st.title("Business Dashboard")

    today = datetime.now().date()
    range_choice = st.selectbox(
        "Range", 
        ["Today", "Last 7 days", "Last 30 days", "Custom range"],
        key="dash_range_choice"
    )

    if range_choice == "Today":
        start_date, end_date, range_label = None, None, "Today"
    elif range_choice == "Last 7 days":
        start_date, end_date = today - timedelta(days=6), today
        range_label = "Last 7 days"
    elif range_choice == "Last 30 days":
        start_date, end_date = today - timedelta(days=29), today
        range_label = "Last 30 days"
    else:
        picked = st.date_input("Custom range", value=(today - timedelta(days=7), today), max_value=today, key="dash_date_picker")
        if isinstance(picked, tuple) and len(picked) == 2:
            start_date, end_date = picked
        else:
            start_date, end_date = today, today
        range_label = f"{start_date} to {end_date}"

    st.caption(f"Showing: **{range_label}**")

    try:
        summary = load_dashboard_summary(start_date, end_date)
        hist = load_history(days=30, start_date=start_date, end_date=end_date)
        alerts = load_fraud_alerts()
    except api.APIError as e:
        st.error(f"Couldn't load dashboard data: {e}")
        st.stop()

    c1, c2, c3, c4, c5 = st.columns(5)
    with c1: metric_card(f"Revenue ({range_label})", f"₹{summary['revenue']:,.0f}", f"{summary['transaction_count']} transactions")
    with c2: metric_card("Cash Collected", f"₹{summary['cash']:,.0f}")
    with c3: metric_card("UPI Collected", f"₹{summary['upi']:,.0f}")
    with c4: metric_card("Card Collected", f"₹{summary['card']:,.0f}")
    with c5: metric_card("Profit", f"₹{summary['profit']:,.0f}")
    
    st.markdown("#### ")
    left, right = st.columns([2, 1])
    
    with left:
        # Drop-down to switch sales trend graph type
        selected_graph = st.selectbox(
            "Select Chart View", 
            [
                "📈 Line Graph", 
                "📊 Bar Graph"
            ],
            key="dash_selected_graph"
        )

        st.subheader(f"Sales Trend — {range_label}")

        if hist.empty:
            st.info("No sales history yet. Visit **Data Source** to generate sample history, or make a few sales in Billing.")
        else:
            daily = hist.groupby("date")["revenue"].sum().reset_index()
            daily["date"] = daily["date"].astype(str)

            # Option 1: Sales Trend (Line Graph)
            if selected_graph == "📈 Line Graph":
                fig = px.line(
                    daily, 
                    x="date", 
                    y="revenue", 
                    markers=True,
                    labels={"revenue": "Revenue (₹)", "date": "Date"}
                )
                fig.update_traces(line_color=PRIMARY, line_width=3)

            # Option 2: Sales Trend (Bar Graph)
            else:
                fig = px.bar(
                    daily, 
                    x="date", 
                    y="revenue", 
                    labels={"revenue": "Revenue (₹)", "date": "Date"},
                    text_auto=',.0f'
                )
                fig.update_traces(marker_color=PRIMARY, width=0.4 if len(daily) == 1 else None)

            # Format axis and render chart
            fig.update_xaxes(type='category')
            fig.update_layout(height=320, margin=dict(l=10, r=10, t=10, b=10))
            st.plotly_chart(fig, use_container_width=True)

            st.subheader(f"Payment Method Split — {range_label}")
            pay_split = hist.groupby("payment_method")["revenue"].sum().reset_index()
            fig2 = px.pie(
                pay_split, 
                names="payment_method", 
                values="revenue", 
                hole=0.55,
                color="payment_method",
                color_discrete_map={"Cash": AMBER, "UPI": PRIMARY, "Card": GREEN}
            )
            fig2.update_layout(height=300, margin=dict(l=10, r=10, t=10, b=10))
            st.plotly_chart(fig2, use_container_width=True)

    with right:
        st.subheader("Top Products (by revenue)")
        if hist.empty:
            st.caption("No sales yet.")
        else:
            top = hist.groupby("name")["revenue"].sum().sort_values(ascending=False).head(8).reset_index()
            fig3 = px.bar(top, x="revenue", y="name", orientation="h", labels={"revenue": "₹", "name": ""})
            fig3.update_traces(marker_color=PRIMARY)
            fig3.update_layout(height=340, margin=dict(l=10, r=10, t=10, b=10), yaxis=dict(autorange="reversed"))
            st.plotly_chart(fig3, use_container_width=True)

        st.subheader("⚠️ Alerts")
        st.markdown(f"**{summary['low_stock_count']}** products low on stock")
        st.markdown(f"**{summary['expiring_soon_count']}** products expiring within 5 days")
        st.markdown(f"**{len(alerts)}** fraud/anomaly flags today")
        st.caption("Fraud flags are computed live from refund/discount patterns — see Fraud & Alerts.")
# ----------------------------------------------------------------------------
# PAGE: BILLING (POS)
# ----------------------------------------------------------------------------
elif page == "🧾 Billing (POS)":
    st.title("Point of Sale")
    st.caption(f"Signed in as **{st.session_state.username}** — sales are attributed to you automatically.")

    col_catalog, col_cart = st.columns([2, 1])

    with col_catalog:
        search = st.text_input("🔍 Search product", placeholder="e.g. Milk, Rice, Shampoo...")
        cat_filter = st.selectbox("Category", ["All"] + sorted(products_df.category.unique().tolist()))

        filtered = products_df.copy()
        if search:
            filtered = filtered[filtered.name.str.contains(search, case=False)]
        if cat_filter != "All":
            filtered = filtered[filtered.category == cat_filter]

        st.markdown(f"**{len(filtered)} products**")
        n_cols = 3
        rows = [filtered.iloc[i:i+n_cols] for i in range(0, len(filtered), n_cols)]
        for row in rows:
            cols = st.columns(n_cols)
            for col, (_, p) in zip(cols, row.iterrows()):
                with col:
                    with st.container(border=True):
                        st.markdown(f"**{p['name']}**")
                        st.caption(f"{p['category']} · Stock: {p['stock']} · GST: {p['gst_rate']:.0f}%")
                        st.markdown(f"₹{p['price']:.0f}")
                        if st.button("➕ Add", key=f"add_{p['product_id']}", use_container_width=True):
                            st.session_state.cart[p["product_id"]] = st.session_state.cart.get(p["product_id"], 0) + 1
                            st.rerun()
        
    
    with col_cart:
        st.subheader("🛒 Cart")
        if not st.session_state.cart:
            st.info("Cart is empty. Add products from the left.")

        else:
            cart_rows = []
            total = 0
            total_gst_embedded = 0

            # -----------------------------------
            # Build cart rows
            # -----------------------------------
            for pid, qty in st.session_state.cart.items():

                match = products_df[products_df.product_id == pid]

                if match.empty:
                    continue

                p = match.iloc[0]

                line_total = p["price"] * qty

                # GST is already included in product price
                line_taxable = line_total / (1 + p["gst_rate"] / 100)
                line_gst = line_total - line_taxable

                total += line_total
                total_gst_embedded += line_gst

                cart_rows.append(
                    (
                        pid,
                        p["name"],
                        p["price"],
                        qty,
                        line_total
                    )
                )

            # -----------------------------------
            # Display cart items
            # -----------------------------------
            for pid, name, price, qty, line_total in cart_rows:

                c1, c2, c3, c4 = st.columns([3, 2, 2, 1])

                # Product name and price
                with c1:
                    st.markdown(
                        f"**{name}**  \n"
                        f"₹{price:.2f} × {qty}"
                    )

                # -----------------------------------
                # Quantity
                # -----------------------------------
                with c2:

                    new_qty = st.number_input(
                        "Qty",
                        min_value=1,
                        max_value=999,
                        value=int(qty),
                        key=f"qty_{pid}",
                        label_visibility="collapsed"
                    )

                    if new_qty != qty:
                        st.session_state.cart[pid] = new_qty
                        st.rerun()

                # -----------------------------------
                # Line total
                # -----------------------------------
                with c3:
                    st.markdown(
                        f"**₹{line_total:,.2f}**"
                    )

                # -----------------------------------
                # Remove item
                # -----------------------------------
                with c4:

                    if st.button(
                        "🗑️",
                        key=f"remove_{pid}",
                        help=f"Remove {name} from cart"
                    ):

                        del st.session_state.cart[pid]

                        st.rerun()

            # -----------------------------------
            # Discount
            # -----------------------------------
            discount_pct = st.slider(
                "Discount % (applied to whole cart)",
                0,
                50,
                0
            )

            # -----------------------------------
            # Calculate discounted amount
            # -----------------------------------
            discounted_total = total * (
                1 - discount_pct / 100
            )

            # GST after discount
            gst_after_discount = total_gst_embedded * (
                1 - discount_pct / 100
            )

            # Taxable amount after discount
            taxable_after_discount = (
                discounted_total - gst_after_discount
            )

            # -----------------------------------
            # Cart summary
            # -----------------------------------
            st.markdown("---")

            st.markdown(
                f"Taxable value: "
                f"₹{taxable_after_discount:,.2f}"
            )

            st.markdown(
                f"GST (included in price): "
                f"₹{gst_after_discount:,.2f}"
            )

            if discount_pct:
                st.markdown(
                    f"Subtotal: ~~₹{total:,.0f}~~"
                )

            st.markdown(
                f"### Total: ₹{discounted_total:,.2f}"
            )

            # -----------------------------------
            # Clear Cart
            # -----------------------------------
            if st.button(
                "🧹 Clear Cart",
                use_container_width=True
            ):

                st.session_state.cart = {}

                st.rerun()

            # -----------------------------------
            # Payment Method
            # -----------------------------------
            payment_method = st.radio(
                "Payment Method",
                ["Cash", "UPI", "Card", "Split"],
                horizontal=True
            )

            # -----------------------------------
            # UPI confirmation
            # -----------------------------------
            upi_confirmed = True

            if payment_method == "UPI":

                if not SHOP_UPI_ID:

                    st.warning(
                        "No UPI ID configured for this shop — "
                        "set SMARTPOS_SHOP_UPI_ID to enable this."
                    )

                    upi_confirmed = False

                else:

                    preview_ref = (
                        f"PREVIEW{len(st.session_state.cart)}"
                    )

                    uri = upi_qr.build_upi_uri(
                        SHOP_UPI_ID,
                        SHOP_NAME,
                        discounted_total,
                        "SmartPOS Sale",
                        preview_ref
                    )

                    qr_png = upi_qr.generate_qr_png(uri)

                    st.image(
                        qr_png,
                        caption=(
                            f"Scan to pay "
                            f"₹{discounted_total:,.2f}"
                        ),
                        width=220
                    )

                    upi_confirmed = st.checkbox(
                        "✅ Payment received — confirmed on my phone"
                    )

            # -----------------------------------
            # Split Payment
            # -----------------------------------
            split_cash = 0

            if payment_method == "Split":

                split_cash = st.number_input(
                    "Cash portion (₹)",
                    min_value=0,
                    max_value=int(discounted_total),
                    value=int(discounted_total // 2)
                )

                split_other = max(
                    0,
                    discounted_total - split_cash
                )

                st.caption(
                    f"UPI/Card portion (auto): "
                    f"₹{split_other:,.2f}"
                )

                st.caption(
                    "Note: the backend records one payment "
                    "method per checkout — split payments "
                    "are logged as Cash for now."
                )

            # -----------------------------------
            # Checkout
            # -----------------------------------
            if st.button(
                "✅ Checkout",
                type="primary",
                use_container_width=True,
                disabled=(
                    payment_method == "UPI"
                    and not upi_confirmed
                )
            ):

                # -----------------------------------
                # Prepare items for backend
                # -----------------------------------
                items = [
                    {
                        "product_id": pid,
                        "qty": qty,
                        "discount_pct": discount_pct
                    }
                    for pid, _, _, qty, _ in cart_rows
                ]

                # -----------------------------------
                # Payment method sent to backend
                # -----------------------------------
                pm_to_send = (
                    "Cash"
                    if payment_method == "Split"
                    else payment_method
                )

                # -----------------------------------
                # Call backend checkout
                # -----------------------------------
                result = call_authed(
                    api.checkout,
                    items,
                    pm_to_send,
                    token=token
                )

                # -----------------------------------
                # Successful checkout
                # -----------------------------------
                if result is not None:

                    # Clear cart
                    st.session_state.cart = {}

                    # Refresh products/transactions
                    refresh_all()

                    # Success message
                    st.success(
                        f"Transaction {result['txn_id']} "
                        f"completed — "
                        f"₹{result['total']:,.2f} "
                        f"via {payment_method}"
                    )

                    # -----------------------------------
                    # GST breakdown
                    # -----------------------------------
                    if result.get("total_tax"):

                        st.caption(
                            f"GST breakdown: "
                            f"taxable value "
                            f"₹{result['taxable_value']:,.2f} · "
                            f"CGST "
                            f"₹{result['cgst']:,.2f} · "
                            f"SGST "
                            f"₹{result['sgst']:,.2f} · "
                            f"total tax "
                            f"₹{result['total_tax']:,.2f}"
                        )

                    # Celebration
                    st.balloons()

                    # Refresh page
                    st.rerun()
    st.markdown("---")
    st.subheader("Today's Transactions")
    try:
        tx_df = load_todays_transactions()
    except api.APIError as e:
        st.error(f"Couldn't load today's transactions: {e}")
        tx_df = pd.DataFrame()

    if not tx_df.empty:
        summary_tbl = tx_df.groupby(["txn_id", "user", "payment_method"]).agg(
            items=("qty", "sum"), total=("revenue", "sum")
        ).reset_index()
        st.dataframe(summary_tbl, width='stretch', hide_index=True)

        with st.expander("🔄 Process a refund"):
            sale_txns = tx_df[tx_df["is_refund"] == False]
            if sale_txns.empty:
                st.caption("No sales today to refund against.")
            else:
                txn_choice = st.selectbox("Original transaction", sale_txns["txn_id"].unique())
                lines_for_txn = sale_txns[sale_txns["txn_id"] == txn_choice]
                product_choice = st.selectbox(
                    "Product", lines_for_txn["product_id"],
                    format_func=lambda pid: lines_for_txn.set_index("product_id").loc[pid, "name"],
                )
                max_qty = int(lines_for_txn.set_index("product_id").loc[product_choice, "qty"])
                refund_qty = st.number_input("Quantity to refund", min_value=1, max_value=max_qty, value=1)
                if st.button("Process refund"):
                    result = call_authed(api.refund, txn_choice, product_choice, refund_qty, token=token)
                    if result is not None:
                        refresh_all()
                        st.success(f"Refunded {refund_qty} × {result['name']} — ₹{abs(result['revenue']):,.2f}")
                        st.rerun()
    else:
        st.caption("No transactions yet today.")

# ----------------------------------------------------------------------------
# PAGE: INVENTORY
# ----------------------------------------------------------------------------
elif page == "📦 Inventory":
    st.title("Inventory Intelligence")
    st.caption("Live stock, smart reorder suggestions, and expiry tracking.")

    inv = products_df.copy()
    inv["status"] = np.where(inv.stock <= inv.reorder_level, "🔴 Low Stock", "🟢 Healthy")

    c1, c2, c3, c4 = st.columns(4)
    with c1: metric_card("Total SKUs", f"{len(inv)}")
    with c2: metric_card("Low Stock Items", f"{(inv.stock <= inv.reorder_level).sum()}")
    with c3:
        exp = inv[inv.expiry_date.notna()]
        near_exp = exp[pd.to_datetime(exp.expiry_date) <= pd.Timestamp.now() + pd.Timedelta(days=5)]
        metric_card("Expiring ≤5 Days", f"{len(near_exp)}")
    with c4: metric_card("Avg Margin", f"{inv.margin_pct.mean():.1f}%")

    st.markdown("#### ")
    tab1, tab2, tab3 = st.tabs(["📋 Full Inventory", "🔁 Smart Reorder Suggestions", "⏳ Expiry Watch"])

    with tab1:
        cat_filter = st.selectbox("Filter category", ["All"] + sorted(inv.category.unique().tolist()), key="inv_cat")
        show = inv if cat_filter == "All" else inv[inv.category == cat_filter]
        st.dataframe(
            show[["product_id", "name", "category", "stock", "reorder_level", "price", "gst_rate", "margin_pct", "status"]],
            width='stretch', hide_index=True,
        )

    with tab2:
        st.markdown("Reorder quantities computed **server-side** from real sales velocity "
                     "over the last 30 days of actual transactions.")
        try:
            sugg = load_reorder_suggestions()
        except api.APIError as e:
            st.error(f"Couldn't load reorder suggestions: {e}")
        else:
            if sugg.empty:
                st.success("Nothing to reorder — all stock levels are healthy.")
            else:
                st.dataframe(
                    sugg.rename(columns={"est_cost": "Est. Reorder Cost (₹)"}),
                    width='stretch', hide_index=True,
                )
                st.info(f"💡 Reordering these {len(sugg)} items now would cost approximately "
                        f"₹{sugg['est_cost'].sum():,.0f} and cover ~14 days of demand.")

    with tab3:
        exp = inv[inv.expiry_date.notna()].sort_values("expiry_date")
        exp["days_left"] = (pd.to_datetime(exp.expiry_date) - pd.Timestamp.now()).dt.days
        exp["urgency"] = pd.cut(exp.days_left, bins=[-1, 3, 7, 10000], labels=["🔴 Urgent", "🟠 Soon", "🟢 OK"])
        st.dataframe(
            exp[["name", "category", "stock", "expiry_date", "days_left", "urgency"]],
            width='stretch', hide_index=True,
        )

# ----------------------------------------------------------------------------
# PAGE: AI BUSINESS ASSISTANT
# ----------------------------------------------------------------------------
elif page == "🤖 AI Business Assistant":
    st.title("AI Business Assistant")
    st.caption("Ask questions about your store in plain language — answered by a real LLM with live access to your data.")

    st.markdown("**Quick questions:**")
    qcols = st.columns(3)
    quick_qs = [
        "How much cash did we collect today?",
        "Which product generated the highest profit this month?",
        "Are there any fraud alerts right now?",
        "What should I reorder soon?",
        "Why might sales be lower this week?",
        "Anything expiring soon?",
    ]

    def ask(question):
        st.session_state.chat_history.append(("user", question))
        with st.spinner("Thinking..."):
            answer = call_authed(api.ask_assistant, question, token=token)
        if answer is not None:
            st.session_state.chat_history.append(("assistant", answer))

    for i, q in enumerate(quick_qs):
        if qcols[i % 3].button(q, use_container_width=True):
            try:
                ask(q)
            except api.APIError as e:
                st.error(f"Assistant error: {e}")

    user_q = st.chat_input("Ask about sales, inventory, fraud, or forecasts...")
    if user_q:
        try:
            ask(user_q)
        except api.APIError as e:
            st.error(f"Assistant error: {e}")

    st.markdown("---")
    for role_, msg in st.session_state.chat_history[-20:]:
        with st.chat_message(role_):
            st.markdown(msg)

    if not st.session_state.chat_history:
        st.info("👋 Try a quick question above, or type your own — e.g. *\"What should I reorder soon?\"*")
        st.caption("Requires ANTHROPIC_API_KEY set on the backend — if you see an error, that's usually why.")

# ----------------------------------------------------------------------------
# PAGE: FRAUD & ALERTS
# ----------------------------------------------------------------------------
elif page == "🚨 Fraud & Alerts":
    st.title("Fraud Detection & Anomaly Alerts")
    st.caption("Computed live from real transaction patterns — refund spikes and discount misuse.")

    try:
        alerts = load_fraud_alerts()
    except api.APIError as e:
        st.error(f"Couldn't load fraud alerts: {e}")
        alerts = pd.DataFrame()

    c1, c2, c3 = st.columns(3)
    with c1: metric_card("Alerts Today", f"{len(alerts)}")
    with c2:
        high = (alerts["severity"] == "High").sum() if not alerts.empty else 0
        metric_card("High Severity", f"{high}")
    with c3:
        cashiers = alerts["cashier"].nunique() if not alerts.empty else 0
        metric_card("Cashiers Flagged", f"{cashiers}")

    st.markdown("#### ")
    if alerts.empty:
        st.success("No fraud or anomaly alerts right now.")
    else:
        for _, a in alerts.iterrows():
            pill_class = {"High": "pill-high", "Medium": "pill-medium", "Low": "pill-low"}.get(a.severity, "pill-low")
            with st.container(border=True):
                top = st.columns([2, 4, 2])
                top[0].markdown(f"**{pd.to_datetime(a.timestamp).strftime('%H:%M:%S')}**")
                top[1].markdown(f"**{a.type}** — {a.detail}")
                top[2].markdown(f'<span class="pill {pill_class}">{a.severity} · {a.cashier}</span>', unsafe_allow_html=True)

    st.caption(
        "Detection rules: 3+ refunds by the same cashier within 60 minutes, or 3+ discounts "
        "of 20%+ by the same cashier in a day. Thresholds are set in backend/services/transactions.py."
    )

# ----------------------------------------------------------------------------
# PAGE: DATA SOURCE (owner only)
# ----------------------------------------------------------------------------
elif page == "🔌 Data Source":
    st.title("Data Source & Users")
    st.caption("Owner-only: reset/replace the product catalog, and manage cashier logins.")
    st.info(f"Backend: `{api.API_BASE_URL}` · **{len(products_df)}** products currently loaded")

    tab_sample, tab_excel, tab_users, tab_backend = st.tabs(
        ["🧪 Sample Data", "📥 Upload Excel", "👤 Manage Users", "🗄️ Backend Info"]
    )

    with tab_sample:
        st.markdown("Reset to the built-in demo catalog (25 SKUs) and regenerate 30 days of sample sales history.")
        st.caption("This clears existing transaction history, since it would otherwise reference the old catalog.")
        if st.button("Use sample data"):
            ok = call_authed(api.seed_sample_products, token=token)
            if ok is not None:
                reseed_ok = call_authed(api.reseed_sample_history, token=token)
                if reseed_ok is not None:
                    refresh_all()
                    st.success("Reset to sample data and regenerated sales history.")
                    st.rerun()

    with tab_excel:
        st.markdown("Upload a spreadsheet with your own product catalog.")
        st.caption(f"Required columns: `{'`, `'.join(ds.REQUIRED_COLUMNS)}` · "
                   f"Optional: `{'`, `'.join(ds.OPTIONAL_COLUMNS)}`")

        template_bytes = ds.generate_excel_template()
        st.download_button(
            "⬇️ Download Excel template", data=template_bytes,
            file_name="smartpos_product_template.xlsx",
            mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        )

        excel_file = st.file_uploader("Upload .xlsx file", type=["xlsx", "xls"])
        if excel_file is not None:
            preview_df = call_authed(api.upload_excel, excel_file, token=token)
            if preview_df is not None:
                st.success(f"Uploaded and saved {len(preview_df)} products to the backend.")
                st.dataframe(preview_df, width='stretch', hide_index=True)
                st.caption("Existing transaction history was cleared (it referenced the old catalog).")
                if st.button("🔁 Generate sample sales history for this catalog"):
                    ok = call_authed(api.reseed_sample_history, token=token)
                    if ok is not None:
                        refresh_all()
                        st.success("Sample history generated.")
                        st.rerun()

    with tab_users:
        st.markdown("Create a login for a cashier (or another owner). Sales made under that login "
                     "are automatically attributed to it — no manual cashier selection needed at checkout.")
        with st.form("create_user_form"):
            new_username = st.text_input("Username")
            new_password = st.text_input("Password", type="password")
            new_role = st.selectbox("Role", ["user", "owner"])
            create_submitted = st.form_submit_button("Create user")
        if create_submitted:
            if not new_username or not new_password:
                st.error("Username and password are both required.")
            else:
                result = call_authed(api.register, new_username, new_password, new_role, token=token)
                if result is not None:
                    st.success(f"Created {result['role']} account: {result['username']}")

    with tab_backend:
        st.markdown("The frontend no longer connects to a database directly — the backend does, "
                     "and this app talks to it over HTTP with a bearer token.")
        st.code(f"SMARTPOS_API_URL = {api.API_BASE_URL}", language="text")
        st.markdown(
            "- To point this app at a different backend (e.g. a deployed one), set the "
            "`SMARTPOS_API_URL` environment variable before running `streamlit run app.py`.\n"
            "- To change **which database the backend itself uses** (SQLite → Postgres), "
            "edit `backend/database.py`.\n"
            "- The AI Assistant needs `ANTHROPIC_API_KEY` set on the **backend**, not here."
        )
        if st.button("🔄 Check backend connection"):
            st.success("Connected.") if api.is_healthy() else st.error("Unreachable.")
