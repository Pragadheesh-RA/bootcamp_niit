from __future__ import annotations

import io
from pathlib import Path

import pandas as pd
import plotly.express as px
import streamlit as st

from config import TARGET_URL
from scraper import TitanRagaScraper


# ============================================================
# PAGE
# ============================================================

st.set_page_config(
    page_title="Titan Raga Live Scraper",
    page_icon="⌚",
    layout="wide",
    initial_sidebar_state="expanded",
)


# ============================================================
# CSS
# ============================================================

st.markdown(
    """
    <style>
        .block-container {
            max-width: 1450px;
            padding-top: 1.5rem;
        }

        .hero-card {
            padding: 2rem;
            border-radius: 22px;
            background: linear-gradient(135deg, #111111, #303030);
            color: white;
            margin-bottom: 1rem;
        }

        .hero-card h1 {
            margin: 0;
            font-size: 2.5rem;
        }

        .hero-card p {
            margin-top: .6rem;
            color: #dddddd;
        }

        .source-card {
            padding: 1rem 1.25rem;
            border: 1px solid #e5e7eb;
            border-radius: 14px;
            background: white;
            margin-bottom: 1.25rem;
        }

        .source-card a {
            font-weight: 700;
            text-decoration: none;
        }

        .product-card {
            border: 1px solid #e5e7eb;
            border-radius: 16px;
            padding: 12px;
            background: white;
            margin-bottom: 20px;
            box-shadow: 0 4px 15px rgba(0,0,0,.05);
        }

        .product-name {
            font-size: 15px;
            font-weight: 700;
            min-height: 68px;
            margin-top: 8px;
        }

        .product-price {
            font-size: 20px;
            font-weight: 800;
        }

        .old-price {
            color: #888;
            text-decoration: line-through;
            margin-left: 8px;
            font-size: 13px;
        }

        .badge {
            display: inline-block;
            padding: 4px 8px;
            border-radius: 5px;
            background: #111;
            color: white;
            font-size: 11px;
            font-weight: 700;
        }

        .live-dot {
            display: inline-block;
            width: 9px;
            height: 9px;
            background: #16a34a;
            border-radius: 50%;
            margin-right: 7px;
        }

        .footer {
            text-align: center;
            color: #777;
            padding: 30px 0;
        }
    </style>
    """,
    unsafe_allow_html=True,
)


# ============================================================
# STATE
# ============================================================

if "products" not in st.session_state:
    st.session_state.products = pd.DataFrame()

if "last_refresh" not in st.session_state:
    st.session_state.last_refresh = None

if "scrape_error" not in st.session_state:
    st.session_state.scrape_error = None


# ============================================================
# AUTO REFRESH
# ============================================================

with st.sidebar:
    st.header("⚙️ Scraper")

    pages = st.slider(
        "Pages to fetch",
        min_value=1,
        max_value=5,
        value=1,
        help="Start with 1 page. Increase after confirming the scraper works.",
    )

    delay = st.slider(
        "Delay between pages",
        min_value=1,
        max_value=10,
        value=2,
        help="Use a reasonable delay to avoid sending rapid requests.",
    )

    auto_refresh = st.checkbox(
        "Enable live auto-refresh",
        value=False,
    )

    refresh_minutes = st.number_input(
        "Refresh interval (minutes)",
        min_value=1,
        max_value=60,
        value=10,
        disabled=not auto_refresh,
    )

    st.divider()

    manual_fetch = st.button(
        "🔄 FETCH LIVE DATA",
        type="primary",
        use_container_width=True,
    )


if auto_refresh:
    try:
        from streamlit_autorefresh import st_autorefresh

        refresh_count = st_autorefresh(
            interval=int(refresh_minutes) * 60 * 1000,
            key="titan_raga_auto_refresh",
        )

        automatic_fetch = (
            refresh_count > 0
            or st.session_state.products.empty
        )

    except ImportError:
        st.warning(
            "Auto-refresh package is missing. Run "
            "`pip install streamlit-autorefresh`."
        )
        automatic_fetch = st.session_state.products.empty
else:
    automatic_fetch = False


fetch_requested = manual_fetch or automatic_fetch


# ============================================================
# HEADER
# ============================================================

st.markdown(
    """
    <div class="hero-card">
        <h1>⌚ Titan Raga Live Scraper</h1>
        <p>
            Live product collection, price intelligence, ratings,
            discounts and export dashboard.
        </p>
    </div>
    """,
    unsafe_allow_html=True,
)

st.markdown(
    f"""
    <div class="source-card">
        <b>Live source:</b>
        <a href="{TARGET_URL}" target="_blank">
            Titan Raga Collection ↗
        </a>
    </div>
    """,
    unsafe_allow_html=True,
)


# ============================================================
# SCRAPE
# ============================================================

if fetch_requested:

    progress = st.progress(0)
    status = st.empty()

    def update_progress(page, total, message):
        progress.progress(
            min(int(page / total * 100), 100)
        )
        status.info(message)

    try:
        scraper = TitanRagaScraper()

        with st.spinner("Fetching Titan Raga data..."):
            data = scraper.scrape(
                max_pages=pages,
                delay=delay,
                progress_callback=update_progress,
            )

        if data.empty:
            raise RuntimeError(
                "No Raga products were extracted."
            )

        st.session_state.products = data
        st.session_state.last_refresh = pd.Timestamp.now()
        st.session_state.scrape_error = None

        # Persist a local copy.
        Path("data").mkdir(exist_ok=True)
        data.to_csv(
            "data/titan_raga_latest.csv",
            index=False,
        )

        progress.progress(100)
        status.success(
            f"Live scrape complete: {len(data)} products."
        )

    except Exception as exc:
        st.session_state.scrape_error = str(exc)
        status.error(
            "Scraping failed. See the diagnostic section below."
        )


# ============================================================
# ERROR DIAGNOSTIC
# ============================================================

if st.session_state.scrape_error:

    with st.expander(
        "⚠️ Scraping diagnostic",
        expanded=True,
    ):
        st.error(
            st.session_state.scrape_error
        )

        st.markdown(
            """
            **Most common causes**

            1. Titan changed its page markup.
            2. The site temporarily restricted automated requests.
            3. Playwright Chromium has not been installed.
            4. Your network/proxy/VPN cannot reach Titan.

            If Playwright is missing, run:

            ```text
            python -m pip install playwright
            python -m playwright install chromium
            ```
            """
        )


# ============================================================
# EMPTY STATE
# ============================================================

df = st.session_state.products.copy()

if df.empty:
    st.info(
        "Click **FETCH LIVE DATA** in the left sidebar to start."
    )

    st.markdown(
        "### What this version fixes"
    )

    st.markdown(
        """
        - Uses semantic product-link detection instead of fragile CSS
          class names.
        - Falls back to a real Chromium browser when the normal HTTP
          response does not contain rendered products.
        - Extracts product name, URL, price, MRP, discount, rating,
          reviews, image and badges.
        - Removes duplicate product URLs.
        - Saves the latest successful scrape under `data/`.
        """
    )

    st.stop()


# ============================================================
# FILTER SIDEBAR
# ============================================================

with st.sidebar:
    st.divider()
    st.header("🔎 Filters")

    search = st.text_input(
        "Search product",
        placeholder="e.g. Showstopper, Opalesque...",
    )

    valid_prices = df["price"].dropna()

    if not valid_prices.empty:
        minimum = int(valid_prices.min())
        maximum = int(valid_prices.max())

        if minimum < maximum:
            selected_range = st.slider(
                "Price range",
                minimum,
                maximum,
                (minimum, maximum),
            )
        else:
            selected_range = (minimum, maximum)
    else:
        selected_range = None

    min_rating = st.slider(
        "Minimum rating",
        min_value=0.0,
        max_value=5.0,
        value=0.0,
        step=0.1,
    )

    min_discount = st.slider(
        "Minimum discount %",
        min_value=0,
        max_value=60,
        value=0,
        step=5,
    )

    sort_by = st.selectbox(
        "Sort by",
        [
            "Default",
            "Price: Low to High",
            "Price: High to Low",
            "Rating: High to Low",
            "Discount: High to Low",
            "Most Reviewed",
        ],
    )


# ============================================================
# FILTER DATA
# ============================================================

filtered = df.copy()

if search:
    filtered = filtered[
        filtered["product_name"].str.contains(
            search,
            case=False,
            na=False,
        )
    ]

if selected_range:
    filtered = filtered[
        filtered["price"].isna()
        | filtered["price"].between(
            selected_range[0],
            selected_range[1],
        )
    ]

filtered = filtered[
    filtered["rating"].isna()
    | (filtered["rating"] >= min_rating)
]

filtered = filtered[
    filtered["discount_percent"].isna()
    | (
        filtered["discount_percent"]
        >= min_discount
    )
]


if sort_by == "Price: Low to High":
    filtered = filtered.sort_values(
        "price",
        ascending=True,
        na_position="last",
    )

elif sort_by == "Price: High to Low":
    filtered = filtered.sort_values(
        "price",
        ascending=False,
        na_position="last",
    )

elif sort_by == "Rating: High to Low":
    filtered = filtered.sort_values(
        "rating",
        ascending=False,
        na_position="last",
    )

elif sort_by == "Discount: High to Low":
    filtered = filtered.sort_values(
        "discount_percent",
        ascending=False,
        na_position="last",
    )

elif sort_by == "Most Reviewed":
    filtered = filtered.sort_values(
        "review_count",
        ascending=False,
        na_position="last",
    )


# ============================================================
# STATUS
# ============================================================

if st.session_state.last_refresh:
    timestamp = st.session_state.last_refresh.strftime(
        "%d %b %Y, %I:%M:%S %p"
    )

    st.success(
        f"🟢 Live data loaded • Last updated: {timestamp}"
    )


# ============================================================
# METRICS
# ============================================================

st.subheader("📊 Live Overview")

m1, m2, m3, m4 = st.columns(4)

prices = filtered["price"].dropna()
ratings = filtered["rating"].dropna()
discounts = filtered["discount_percent"].dropna()

m1.metric(
    "Products",
    f"{len(filtered):,}",
)

m2.metric(
    "Average Price",
    f"₹{prices.mean():,.0f}" if not prices.empty else "—",
)

m3.metric(
    "Average Rating",
    f"{ratings.mean():.1f} ⭐" if not ratings.empty else "—",
)

m4.metric(
    "Average Discount",
    (
        f"{discounts.mean():.0f}%"
        if not discounts.empty
        else "—"
    ),
)


# ============================================================
# ANALYTICS
# ============================================================

st.subheader("📈 Analytics")

left, right = st.columns(2)

with left:
    if not prices.empty:
        fig = px.histogram(
            filtered.dropna(subset=["price"]),
            x="price",
            nbins=20,
            title="Price Distribution",
        )
        st.plotly_chart(
            fig,
            use_container_width=True,
        )

with right:
    if not ratings.empty:
        fig = px.histogram(
            filtered.dropna(subset=["rating"]),
            x="rating",
            nbins=10,
            title="Rating Distribution",
        )
        st.plotly_chart(
            fig,
            use_container_width=True,
        )


# ============================================================
# PRODUCT GRID
# ============================================================

st.subheader(
    f"⌚ Raga Products ({len(filtered)})"
)

records = filtered.to_dict("records")

for start in range(0, len(records), 3):

    cols = st.columns(3)

    for col, product in zip(
        cols,
        records[start:start + 3],
    ):
        with col:
            with st.container(border=True):

                image_url = product.get("image_url")

                if image_url:
                    try:
                        st.image(
                            image_url,
                            use_container_width=True,
                        )
                    except Exception:
                        st.caption(
                            "Product image unavailable."
                        )

                badge = product.get("badge")

                if pd.notna(badge) if badge is not None else False:
                    st.caption(f"🏷️ {badge}")

                st.markdown(
                    f"**{product.get('product_name', 'Raga Watch')}**"
                )

                price = product.get("price")
                original = product.get("original_price")

                if pd.notna(price):
                    price_text = f"₹{price:,.0f}"
                else:
                    price_text = "Price unavailable"

                if (
                    pd.notna(original)
                    and pd.notna(price)
                    and original > price
                ):
                    price_text += (
                        f"  ~~₹{original:,.0f}~~"
                    )

                st.markdown(
                    f"### {price_text}"
                )

                rating = product.get("rating")
                reviews = product.get("review_count")

                details = []

                if pd.notna(rating):
                    details.append(
                        f"⭐ {rating:.1f}"
                    )

                if pd.notna(reviews):
                    details.append(
                        f"{int(reviews)} reviews"
                    )

                if details:
                    st.caption(
                        " • ".join(details)
                    )

                discount = product.get(
                    "discount_percent"
                )

                if pd.notna(discount):
                    st.success(
                        f"{int(discount)}% OFF"
                    )

                url = product.get(
                    "product_url"
                )

                if url:
                    st.link_button(
                        "View on Titan ↗",
                        url,
                        use_container_width=True,
                    )


# ============================================================
# EXPORT
# ============================================================

st.subheader("📥 Export")

c1, c2 = st.columns(2)

with c1:
    st.download_button(
        "Download CSV",
        data=filtered.to_csv(index=False),
        file_name="titan_raga_products.csv",
        mime="text/csv",
        use_container_width=True,
    )

with c2:
    buffer = io.BytesIO()

    with pd.ExcelWriter(
        buffer,
        engine="openpyxl",
    ) as writer:
        filtered.to_excel(
            writer,
            index=False,
            sheet_name="Titan Raga",
        )

    st.download_button(
        "Download Excel",
        data=buffer.getvalue(),
        file_name="titan_raga_products.xlsx",
        mime=(
            "application/vnd.openxmlformats-"
            "officedocument.spreadsheetml.sheet"
        ),
        use_container_width=True,
    )


# ============================================================
# TABLE
# ============================================================

st.subheader("📋 Scraped Data")

table_columns = [
    "product_name",
    "price",
    "original_price",
    "discount_percent",
    "rating",
    "review_count",
    "badge",
    "product_url",
    "scraped_at",
]

table_columns = [
    column
    for column in table_columns
    if column in filtered.columns
]

st.dataframe(
    filtered[table_columns],
    use_container_width=True,
    hide_index=True,
)


# ============================================================
# FOOTER
# ============================================================

st.markdown(
    """
    <div class="footer">
        Titan Raga Live Product Intelligence Dashboard
        <br>
        Python • Requests • BeautifulSoup • Playwright • Pandas • Streamlit
    </div>
    """,
    unsafe_allow_html=True,
)
