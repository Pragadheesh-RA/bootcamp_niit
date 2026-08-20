TARGET_URL = "https://www.titan.co.in/shop/collections-raga"
SITE_NAME = "Titan Raga"

REQUEST_TIMEOUT = 30
REQUEST_DELAY_SECONDS = 2

# Keep this modest. Increase only if you have confirmed that the site
# permits the request rate.
MAX_PAGES = 5

HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/151.0.0.0 Safari/537.36"
    ),
    "Accept": (
        "text/html,application/xhtml+xml,application/xml;q=0.9,"
        "image/avif,image/webp,*/*;q=0.8"
    ),
    "Accept-Language": "en-IN,en;q=0.9",
    "Cache-Control": "no-cache",
    "Pragma": "no-cache",
}
