from __future__ import annotations

import re
import time
from datetime import datetime
from typing import Optional
from urllib.parse import parse_qs, urlencode, urljoin, urlparse, urlunparse

import pandas as pd
import requests
from bs4 import BeautifulSoup

from config import (
    HEADERS,
    MAX_PAGES,
    REQUEST_DELAY_SECONDS,
    REQUEST_TIMEOUT,
    TARGET_URL,
)


PRICE_RE = re.compile(
    r"(?:₹|Rs\.?|INR)\s*([\d,]+(?:\.\d+)?)",
    re.IGNORECASE,
)

RATING_RE = re.compile(
    r"\b([0-5](?:\.[0-9])?)\s*\|\s*(\d+)\b"
)

DISCOUNT_RE = re.compile(
    r"(\d+)\s*%\s*off",
    re.IGNORECASE,
)

WATCH_TEXT_RE = re.compile(
    r"\b(?:Raga|Titan)\b.*\bWatch\b",
    re.IGNORECASE,
)


class TitanRagaScraper:
    """
    Scraper for Titan's Raga collection page.

    Strategy:
    1. Request the page with a normal browser-like user agent.
    2. Instead of relying on fragile CSS class names, locate product links
       whose visible text contains Raga/Watch and a rupee price.
    3. If requests returns no product cards (for example, because the page
       is client-rendered), fall back to Playwright and parse the rendered DOM.
    """

    def __init__(self):
        self.session = requests.Session()
        self.session.headers.update(HEADERS)

    @staticmethod
    def clean_text(value: str | None) -> str:
        if not value:
            return ""
        return re.sub(r"\s+", " ", value).strip()

    @staticmethod
    def parse_prices(text: str) -> list[float]:
        prices = []
        for match in PRICE_RE.findall(text or ""):
            try:
                prices.append(float(match.replace(",", "")))
            except ValueError:
                pass
        return prices

    @staticmethod
    def parse_rating_and_reviews(text: str):
        match = RATING_RE.search(text or "")
        if not match:
            return None, None
        try:
            return float(match.group(1)), int(match.group(2))
        except ValueError:
            return None, None

    @staticmethod
    def parse_discount(text: str) -> Optional[int]:
        match = DISCOUNT_RE.search(text or "")
        if not match:
            return None
        return int(match.group(1))

    @staticmethod
    def page_url(url: str, page: int) -> str:
        parsed = urlparse(url)
        query = parse_qs(parsed.query)
        query["page"] = [str(page)]
        return urlunparse(
            (
                parsed.scheme,
                parsed.netloc,
                parsed.path,
                parsed.params,
                urlencode(query, doseq=True),
                parsed.fragment,
            )
        )

    def fetch_requests(self, url: str) -> str:
        response = self.session.get(
            url,
            timeout=REQUEST_TIMEOUT,
            allow_redirects=True,
        )
        response.raise_for_status()

        if len(response.text) < 5000:
            raise RuntimeError(
                f"Titan returned an unexpectedly small response "
                f"({len(response.text)} characters)."
            )

        return response.text

    def fetch_playwright(self, url: str) -> str:
        """
        Render the page in Chromium when normal requests do not expose
        the product cards. This does not bypass CAPTCHA or other access
        controls; it simply renders the public page like a normal browser.
        """
        try:
            from playwright.sync_api import sync_playwright
        except ImportError as exc:
            raise RuntimeError(
                "Playwright is not installed. Run:\n"
                "pip install playwright\n"
                "playwright install chromium"
            ) from exc

        with sync_playwright() as p:
            browser = p.chromium.launch(
                headless=True
            )
            page = browser.new_page(
                viewport={"width": 1440, "height": 1000},
                user_agent=HEADERS["User-Agent"],
                locale="en-IN",
            )

            page.goto(
                url,
                wait_until="domcontentloaded",
                timeout=60000,
            )

            # Allow client-side product data to render.
            page.wait_for_timeout(5000)

            # Trigger lazy loading of product images/cards.
            for _ in range(5):
                page.mouse.wheel(0, 2500)
                page.wait_for_timeout(1200)

            html = page.content()
            browser.close()

        return html

    @staticmethod
    def _candidate_product_links(soup: BeautifulSoup):
        """
        Titan's visible product text is present on anchor elements in the
        current collection page. We use semantic text + price instead of
        hard-coded CSS classes because those classes can change.
        """
        candidates = []

        for anchor in soup.select("a[href]"):
            text = TitanRagaScraper.clean_text(
                anchor.get_text(" ", strip=True)
            )

            if not text:
                continue

            if "₹" not in text and "Rs" not in text:
                continue

            if not WATCH_TEXT_RE.search(text):
                continue

            href = anchor.get("href")
            if not href:
                continue

            candidates.append(anchor)

        return candidates

    @staticmethod
    def _find_container(anchor):
        """
        Move up the DOM to locate a useful product-card-like parent.
        We intentionally avoid depending on Titan's internal class names.
        """
        best = anchor

        for parent in anchor.parents:
            if parent.name not in {"div", "li", "article", "section"}:
                continue

            text = TitanRagaScraper.clean_text(
                parent.get_text(" ", strip=True)
            )

            # A product card normally has product text, a price, and
            # an image or a reasonably small amount of text.
            if (
                "₹" in text
                and "Watch" in text
                and len(text) < 1500
            ):
                best = parent

                if parent.select_one("img"):
                    return parent

        return best

    @staticmethod
    def _image_from_container(container):
        for image in container.select("img"):
            for attr in (
                "src",
                "data-src",
                "data-original",
                "data-lazy-src",
                "data-image",
            ):
                value = image.get(attr)
                if value and not value.startswith("data:"):
                    return urljoin(TARGET_URL, value)

            srcset = image.get("srcset")
            if srcset:
                first = srcset.split(",")[0].strip().split(" ")[0]
                if first:
                    return urljoin(TARGET_URL, first)

        return None

    def _parse_anchor(self, anchor):
        container = self._find_container(anchor)

        # Prefer the complete card text because rating/stock/badge may be
        # siblings of the product-name link.
        text = self.clean_text(
            container.get_text(" ", strip=True)
        )

        anchor_text = self.clean_text(
            anchor.get_text(" ", strip=True)
        )

        if len(text) < len(anchor_text):
            text = anchor_text

        prices = self.parse_prices(text)

        if not prices:
            prices = self.parse_prices(anchor_text)

        if not prices:
            return None

        # The live page generally puts the selling price first. If another
        # higher price exists, treat it as MRP/original price.
        price = prices[0]
        original_price = None

        higher_prices = [
            value for value in prices[1:]
            if value > price
        ]

        if higher_prices:
            original_price = max(higher_prices)

        rating, review_count = self.parse_rating_and_reviews(text)
        discount = self.parse_discount(text)

        # The anchor text is normally the cleanest product title because
        # card text can also contain wishlist/compare/marketing labels.
        product_name = anchor_text

        # Remove rating prefix.
        product_name = re.sub(
            r"^[0-5](?:\.[0-9])?\s*\|\s*\d+\s*",
            "",
            product_name,
        ).strip()

        # Remove common marketing suffixes from the title.
        product_name = re.sub(
            r"\s+\d+\s+people bought this week.*$",
            "",
            product_name,
            flags=re.IGNORECASE,
        ).strip()

        product_name = re.sub(
            r"\s+\+\s*[\d,]+k?\s+people viewed this month.*$",
            "",
            product_name,
            flags=re.IGNORECASE,
        ).strip()

        # Keep the title before the first price.
        price_match = PRICE_RE.search(product_name)
        if price_match:
            product_name = product_name[:price_match.start()].strip()

        if not product_name or "Watch" not in product_name:
            return None

        href = anchor.get("href")
        product_url = urljoin(TARGET_URL, href)

        badge = None
        lower = text.lower()

        if "best seller" in lower:
            badge = "Best Seller"
        elif "only 1 left in stock" in lower:
            badge = "Only 1 Left in Stock"

        return {
            "product_name": product_name,
            "price": price,
            "original_price": original_price,
            "discount_percent": discount,
            "rating": rating,
            "review_count": review_count,
            "badge": badge,
            "image_url": self._image_from_container(container),
            "product_url": product_url,
            "scraped_at": datetime.now().strftime(
                "%Y-%m-%d %H:%M:%S"
            ),
        }

    def parse_html(self, html: str) -> pd.DataFrame:
        soup = BeautifulSoup(html, "lxml")

        rows = []
        seen_urls = set()

        for anchor in self._candidate_product_links(soup):
            try:
                row = self._parse_anchor(anchor)
            except Exception:
                continue

            if not row:
                continue

            url = row["product_url"]

            if url in seen_urls:
                continue

            seen_urls.add(url)
            rows.append(row)

        return pd.DataFrame(rows)

    def scrape_page(self, url: str) -> pd.DataFrame:
        # First attempt: lightweight requests.
        try:
            html = self.fetch_requests(url)
            data = self.parse_html(html)

            if not data.empty:
                return data

        except Exception:
            pass

        # Second attempt: real browser rendering.
        html = self.fetch_playwright(url)
        data = self.parse_html(html)

        if data.empty:
            raise RuntimeError(
                "The Titan page was reached, but no Raga product cards "
                "could be extracted. The site may have changed its markup "
                "or may be temporarily restricting automated access."
            )

        return data

    def scrape(
        self,
        max_pages: int = 1,
        delay: int = REQUEST_DELAY_SECONDS,
        progress_callback=None,
    ) -> pd.DataFrame:

        max_pages = max(
            1,
            min(int(max_pages), MAX_PAGES),
        )

        all_rows = []
        seen_urls = set()

        for page_number in range(1, max_pages + 1):
            url = (
                TARGET_URL
                if page_number == 1
                else self.page_url(TARGET_URL, page_number)
            )

            if progress_callback:
                progress_callback(
                    page_number,
                    max_pages,
                    f"Fetching page {page_number}..."
                )

            try:
                page_data = self.scrape_page(url)
            except Exception as exc:
                if page_number == 1:
                    raise
                # A later page can legitimately be unavailable/end of list.
                break

            for row in page_data.to_dict("records"):
                product_url = row.get("product_url")

                if product_url in seen_urls:
                    continue

                seen_urls.add(product_url)
                all_rows.append(row)

            if progress_callback:
                progress_callback(
                    page_number,
                    max_pages,
                    f"Page {page_number}: "
                    f"{len(page_data)} products found"
                )

            if page_number < max_pages:
                time.sleep(max(1, int(delay)))

        if not all_rows:
            return pd.DataFrame()

        result = pd.DataFrame(all_rows)

        # Normalize numeric columns.
        for column in (
            "price",
            "original_price",
            "discount_percent",
            "rating",
            "review_count",
        ):
            result[column] = pd.to_numeric(
                result[column],
                errors="coerce",
            )

        return result.reset_index(drop=True)
