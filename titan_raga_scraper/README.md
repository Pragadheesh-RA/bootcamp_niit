# Titan Raga Live Web Scraper

Target:
https://www.titan.co.in/shop/collections-raga

## What was fixed

The earlier version depended on generic product-card CSS selectors.
That is why it could return zero products even though the Titan page
was loading correctly.

This version:

1. Finds product links by their visible Raga/watch text and price.
2. Does not depend on one Titan CSS class.
3. Uses Requests first.
4. Falls back to a rendered Chromium browser using Playwright when
   the normal HTTP response does not expose product cards.
5. Extracts:
   - product name
   - product URL
   - image
   - selling price
   - original price when present
   - discount
   - rating
   - review count
   - Best Seller / stock badge
   - scrape timestamp
6. Removes duplicate product URLs.
7. Saves the latest successful scrape to:
   data/titan_raga_latest.csv
8. Includes search, price, rating and discount filters.
9. Includes CSV and Excel export.
10. Includes optional periodic refresh.

## Windows setup

Open PowerShell in this folder.

### 1. Check Python

py --version

If Python is installed, continue.

### 2. Create virtual environment

py -m venv venv

### 3. Activate

.\venv\Scripts\Activate.ps1

If PowerShell blocks the script:

Set-ExecutionPolicy -ExecutionPolicy RemoteSigned -Scope CurrentUser

Then activate again.

### 4. Install packages

python -m pip install --upgrade pip
python -m pip install -r requirements.txt

### 5. Install Chromium for Playwright

python -m playwright install chromium

### 6. Run

python -m streamlit run app.py

Open:

http://localhost:8501

## First test

Start with:

Pages = 1
Delay = 2 seconds

Then click:

FETCH LIVE DATA

If it works, you can increase Pages to 2-5.

## Troubleshooting

### No products extracted

Run:

python -m playwright install chromium

Then restart Streamlit.

If the browser still cannot reach Titan, open the Titan Raga URL
normally in Chrome on the same computer and check whether the site
itself is available.

### Python is not recognized

Try:

py --version

If that works, use `py` to create the environment:

py -m venv venv

After activation, use `python`.

### Port already in use

Run:

python -m streamlit run app.py --server.port 8502

Then open:

http://localhost:8502

## Responsible scraping

Keep request rates reasonable and comply with Titan's terms,
robots rules, rate limits and access controls. This project does not
attempt to bypass CAPTCHA, authentication or anti-bot controls.

Because the site's HTML can change, selectors may need future updates.
