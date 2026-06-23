import json
import os
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Dict, List, Optional, Tuple

import requests

from models import AppProject
from utils import setup_logger, retry

logger = setup_logger(__name__)

SNAPSHOTS_PATH = Path(__file__).parent.parent / "app_snapshots.json"

# iTunes legacy RSS — supports newapplications + genre filtering
RSS_URL = "https://itunes.apple.com/{region}/rss/newapplications/limit={limit}/genre={genre_id}/json"
REVIEWS_URL = "https://itunes.apple.com/{region}/rss/customerreviews/id={app_id}/sortby=mostrecent/json"
LOOKUP_URL = "https://itunes.apple.com/lookup?id={app_id}&country={region}"

# region → [(genre_id, category_label), ...]
TARGETS = {
    "us": [
        ("7012", "Puzzle"),
        ("7014", "Casual"),
        ("6002", "Utilities"),
        ("6007", "Productivity"),
    ],
    "jp": [
        ("7012", "Puzzle"),
        ("7014", "Casual"),
        ("6002", "Utilities"),
        ("6007", "Productivity"),
    ],
}

RSS_LIMIT = int(os.getenv("APP_RSS_LIMIT", "100"))
NEW_LISTING_MAX = int(os.getenv("APP_NEW_LISTING_MAX", "0"))  # 0 = no cap on pool size
TRACKING_MAX_DAYS = int(os.getenv("APP_TRACKING_DAYS", "14"))
REVISIT_MIN_HOURS = float(os.getenv("APP_REVISIT_MIN_HOURS", "6"))

# Black-horse thresholds (PRD §五)
THRESHOLD_A_DAYS = 7
THRESHOLD_A_MIN_REVIEWS = 10
THRESHOLD_A_MAX_REVIEWS = int(os.getenv("APP_MAX_REVIEWS", "150"))
THRESHOLD_A_STAR_RATIO = 0.90
THRESHOLD_B_MIN_DELTA = 15
THRESHOLD_B_MAX_HOURS = 12

# Comma-separated developer name keywords to exclude (big publishers / chart staples)
EXCLUDE_PUBLISHERS = [
    k.strip().lower()
    for k in os.getenv(
        "APP_EXCLUDE_PUBLISHERS",
        "nintendo,warner,hbo,disney,activision,ea sports,electronic arts,"
        "supercell,king,zynga,roblox,spotify,netflix,amazon,google,meta,apple",
    ).split(",")
    if k.strip()
]


def load_snapshots() -> Dict:
    if SNAPSHOTS_PATH.exists():
        try:
            return json.loads(SNAPSHOTS_PATH.read_text(encoding="utf-8"))
        except Exception as e:
            logger.warning("Failed to load snapshots, starting fresh: %s", e)
    return {}


def save_snapshots(snapshots: Dict) -> None:
    try:
        SNAPSHOTS_PATH.write_text(
            json.dumps(snapshots, ensure_ascii=False, indent=2),
            encoding="utf-8",
        )
        logger.info("Snapshots saved to %s", SNAPSHOTS_PATH)
    except Exception as e:
        logger.error("Failed to save snapshots: %s", e)


@retry(max_attempts=3, delay=3.0, exceptions=(requests.RequestException,))
def _get(url: str, timeout: int = 10) -> dict:
    resp = requests.get(url, timeout=timeout, headers={"User-Agent": "BlackHorseRadar/1.0"})
    resp.raise_for_status()
    return resp.json()


def _now_iso() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def _hours_since(iso: str) -> float:
    if not iso:
        return 999.0
    for fmt, clip in [("%Y-%m-%dT%H:%M:%SZ", 20), ("%Y-%m-%dT%H:%M:%S", 19), ("%Y-%m-%d", 10)]:
        try:
            dt = datetime.strptime(iso[:clip], fmt).replace(tzinfo=timezone.utc)
            return (datetime.now(timezone.utc) - dt).total_seconds() / 3600
        except Exception:
            continue
    return 999.0


def _is_excluded(app: AppProject) -> bool:
    dev = (app.developer or "").lower()
    return any(kw in dev for kw in EXCLUDE_PUBLISHERS)


def fetch_new_apps(region: str, genre_id: str, category_label: str) -> List[AppProject]:
    url = RSS_URL.format(region=region, limit=RSS_LIMIT, genre_id=genre_id)
    try:
        data = _get(url)
    except Exception as e:
        logger.error("RSS fetch failed for %s/%s: %s", region, category_label, e)
        return []

    # Legacy iTunes RSS uses feed.entry (list of dicts with nested labels)
    # Apple ignores the limit param; enforce our own cap (newest-first order)
    entries = data.get("feed", {}).get("entry", [])[:RSS_LIMIT]
    apps = []
    for entry in entries:
        app_id = entry.get("id", {}).get("attributes", {}).get("im:id", "")
        if not app_id:
            continue
        title = entry.get("im:name", {}).get("label", "")
        price_label = entry.get("im:price", {}).get("label", "Free")
        price_amount = entry.get("im:price", {}).get("attributes", {}).get("amount", "0")
        price = "Free" if price_amount in ("0", "0.0", "") else price_label
        artist = entry.get("im:artist", {}).get("label", "")
        html_url = entry.get("link", {}).get("attributes", {}).get("href", "")
        if not html_url:
            html_url = f"https://apps.apple.com/{region}/app/id{app_id}"
        release_date = entry.get("im:releaseDate", {}).get("label", "")

        apps.append(AppProject(
            app_id=app_id,
            title=title,
            region=region,
            category=category_label,
            description="",
            price=price,
            developer=artist,
            html_url=html_url,
            filter_trigger="",
            release_date=release_date,
        ))

    logger.info("Fetched %d apps from %s/%s (newapplications RSS)", len(apps), region, category_label)
    return apps


def fetch_reviews(region: str, app_id: str) -> Tuple[int, int, List[str]]:
    """Returns (total_reviews, five_star_count, review_texts)."""
    url = REVIEWS_URL.format(region=region, app_id=app_id)
    try:
        time.sleep(2.0)
        data = _get(url)
    except Exception as e:
        logger.warning("Reviews fetch failed for app %s: %s", app_id, e)
        return 0, 0, []

    entries = data.get("feed", {}).get("entry", [])
    if not entries:
        return 0, 0, []

    # First entry is the app info, not a review
    if isinstance(entries[0], dict) and "im:name" in entries[0]:
        entries = entries[1:]

    total = len(entries)
    five_star = 0
    texts = []
    for e in entries:
        rating_raw = e.get("im:rating", {})
        rating = int(rating_raw.get("label", 0)) if isinstance(rating_raw, dict) else 0
        if rating == 5:
            five_star += 1
            content = e.get("content", {})
            text = content.get("label", "") if isinstance(content, dict) else ""
            if text:
                texts.append(text[:300])
        if len(texts) >= 30:
            break

    return total, five_star, texts


def _is_recent_release(release_date: str, days: int = THRESHOLD_A_DAYS) -> bool:
    """True if release_date is within `days` days from now."""
    if not release_date:
        return True  # unknown — allow first check
    try:
        dt_str = release_date[:19]
        dt = datetime.strptime(dt_str, "%Y-%m-%dT%H:%M:%S").replace(tzinfo=timezone.utc)
        return (datetime.now(timezone.utc) - dt).days <= days
    except Exception:
        return True


def _snapshot_to_app(app_id: str, snap: dict) -> AppProject:
    region = snap.get("region", "us")
    return AppProject(
        app_id=app_id,
        title=snap.get("title", ""),
        region=region,
        category=snap.get("category", ""),
        description="",
        price=snap.get("price", "Free"),
        developer=snap.get("developer", ""),
        html_url=snap.get("html_url", f"https://apps.apple.com/{region}/app/id{app_id}"),
        filter_trigger="",
        release_date=snap.get("release_date", ""),
    )


def filter_black_horses(
    apps: List[AppProject],
    snapshots: Dict,
    now_iso: Optional[str] = None,
) -> List[AppProject]:
    if now_iso is None:
        now_iso = _now_iso()

    black_horses = []
    seen_ids: set = set()

    for app in apps:
        if app.app_id in seen_ids:
            continue
        seen_ids.add(app.app_id)

        if _is_excluded(app):
            logger.debug("Excluded publisher: %s (%s)", app.title, app.developer)
            continue

        snap = snapshots.get(app.app_id, {})
        in_snapshot = bool(snap)

        # Brand-new old apps: record for tracking, skip expensive review fetch
        if not in_snapshot and not _is_recent_release(app.release_date):
            snapshots[app.app_id] = {
                "title": app.title,
                "region": app.region,
                "category": app.category,
                "developer": app.developer,
                "html_url": app.html_url,
                "price": app.price,
                "first_seen": now_iso,
                "last_checked": now_iso,
                "total_reviews": 0,
                "five_star_reviews": 0,
                "release_date": app.release_date,
            }
            continue

        # Save previous values BEFORE updating snapshot (Indicator B needs these)
        prev_total = snap.get("total_reviews", 0) if snap else 0
        prev_last_checked = (
            snap.get("last_checked") or snap.get("first_seen", "")
            if snap else ""
        )

        if snap and _hours_since(snap.get("last_checked", "")) < REVISIT_MIN_HOURS:
            total = snap.get("total_reviews", 0)
            five_star = snap.get("five_star_reviews", 0)
            texts = []
        else:
            total, five_star, texts = fetch_reviews(app.region, app.app_id)

        if not snap:
            snap = {
                "title": app.title,
                "region": app.region,
                "category": app.category,
                "developer": app.developer,
                "html_url": app.html_url,
                "price": app.price,
                "first_seen": now_iso,
                "last_checked": now_iso,
                "total_reviews": total,
                "five_star_reviews": five_star,
                "release_date": app.release_date,
            }
        else:
            snap["title"] = app.title
            snap["developer"] = app.developer

        trigger = _check_trigger(app, snap, total, five_star, prev_total, prev_last_checked)

        # Always update snapshot counts after trigger check
        snap["last_checked"] = now_iso
        snap["total_reviews"] = total
        snap["five_star_reviews"] = five_star
        snapshots[app.app_id] = snap

        if trigger:
            app.filter_trigger = trigger
            app.reviews = texts
            black_horses.append(app)
            logger.info(
                "Black horse [%s]: %s (%s/%s) trigger=%s",
                app.region, app.title, five_star, total, trigger,
            )

    return black_horses


def _check_trigger(
    app: AppProject,
    snap: dict,
    total: int,
    five_star: int,
    prev_total: int,
    prev_last_checked: str,
) -> Optional[str]:
    # Indicator A — new launch burst (PRD: first_seen ≤ 7d, reviews > 10, 90% five-star)
    first_seen = snap.get("first_seen", _now_iso())
    age_days = _hours_since(first_seen) / 24
    if (
        age_days <= THRESHOLD_A_DAYS
        and THRESHOLD_A_MIN_REVIEWS < total <= THRESHOLD_A_MAX_REVIEWS
        and total > 0
        and (five_star / total) >= THRESHOLD_A_STAR_RATIO
    ):
        return "A"

    # Indicator B — review velocity spike (compare against pre-update snapshot)
    delta_reviews = total - prev_total
    delta_hours = _hours_since(prev_last_checked) if prev_last_checked else 999.0
    if delta_reviews >= THRESHOLD_B_MIN_DELTA and 0 < delta_hours <= THRESHOLD_B_MAX_HOURS:
        return "B"

    return None


def _should_revisit_snapshot(snap: dict) -> bool:
    """Skip stale/zero-signal snapshots to avoid hundreds of review fetches."""
    first_seen = snap.get("first_seen", "")
    last_checked = snap.get("last_checked") or first_seen
    if _hours_since(first_seen) / 24 > TRACKING_MAX_DAYS:
        return False
    if last_checked and _hours_since(last_checked) < REVISIT_MIN_HOURS:
        return False
    total = snap.get("total_reviews", 0)
    age_days = _hours_since(first_seen) / 24
    # Keep watching young apps; revisit older ones only if they already had reviews
    return total > 0 or age_days <= THRESHOLD_A_DAYS


def batch_enrich_descriptions(apps: List[AppProject]) -> None:
    """Batch iTunes Lookup by region (up to 50 ids per request)."""
    by_region: Dict[str, List[AppProject]] = {}
    for app in apps:
        if app.description:
            continue
        by_region.setdefault(app.region, []).append(app)

    for region, group in by_region.items():
        for i in range(0, len(group), 50):
            chunk = group[i : i + 50]
            ids = ",".join(a.app_id for a in chunk)
            try:
                time.sleep(0.5)
                data = _get(LOOKUP_URL.format(app_id=ids, region=region))
                by_id = {str(r.get("trackId", "")): r for r in data.get("results", [])}
                for app in chunk:
                    r = by_id.get(app.app_id)
                    if not r:
                        continue
                    app.description = (r.get("description") or "")[:2000]
                    if not app.developer:
                        app.developer = r.get("artistName", "")
            except Exception as e:
                logger.warning("Batch lookup failed for %s: %s", region, e)


def enrich_app_for_analysis(app: AppProject) -> None:
    """Fetch description via iTunes Lookup; pull reviews if the app already has some."""
    if not app.description:
        try:
            time.sleep(0.5)
            data = _get(LOOKUP_URL.format(app_id=app.app_id, region=app.region))
            results = data.get("results", [])
            if results:
                r = results[0]
                app.description = (r.get("description") or "")[:2000]
                if not app.developer:
                    app.developer = r.get("artistName", "")
        except Exception as e:
            logger.warning("Lookup failed for %s: %s", app.app_id, e)

    if not app.reviews and app.total_reviews > 0:
        total, five_star, texts = fetch_reviews(app.region, app.app_id)
        app.reviews = texts
        app.total_reviews = total
        app.five_star_reviews = five_star


def _enrich_from_snapshot(app: AppProject, snap: dict) -> None:
    app.total_reviews = snap.get("total_reviews", 0)
    app.five_star_reviews = snap.get("five_star_reviews", 0)
    app.first_seen = snap.get("first_seen", "")


def fetch_app_store_data() -> Tuple[List[AppProject], List[AppProject], Dict]:
    """Returns (new_listings, black_horses, snapshots).

    new_listings — apps from newapplications RSS with recent release (上新监控)
    black_horses — apps passing Indicator A or B (黑马雷达)
    """
    regions = [r.strip() for r in os.getenv("APP_STORE_REGIONS", "us,jp").split(",")]
    snapshots = load_snapshots()
    all_candidates: List[AppProject] = []
    new_listings: List[AppProject] = []
    seen_ids: set = set()

    for region in regions:
        for genre_id, category_label in TARGETS.get(region, []):
            rss_apps = fetch_new_apps(region, genre_id, category_label)
            for app in rss_apps:
                if app.app_id not in seen_ids:
                    seen_ids.add(app.app_id)
                    all_candidates.append(app)
                    new_listings.append(app)
            time.sleep(2.0)

    # Re-check tracked snapshots eligible for Indicator B (skip bulk stale revisits)
    revisit_count = 0
    for app_id, snap in list(snapshots.items()):
        if app_id in seen_ids:
            continue
        if not _should_revisit_snapshot(snap):
            continue
        app = _snapshot_to_app(app_id, snap)
        if _is_excluded(app):
            continue
        seen_ids.add(app_id)
        all_candidates.append(app)
        revisit_count += 1

    # Newest first, cap listing + analysis pool
    new_listings.sort(key=lambda a: (a.release_date or "", a.app_id), reverse=True)
    rss_unique = len(new_listings)
    if NEW_LISTING_MAX > 0:
        new_listings = new_listings[:NEW_LISTING_MAX]

    logger.info(
        "Total candidates: %d (RSS pool: %d, snapshot revisit: %d)",
        len(all_candidates), rss_unique, revisit_count,
    )
    black_horses = filter_black_horses(all_candidates, snapshots)

    for app in new_listings:
        _enrich_from_snapshot(app, snapshots.get(app.app_id, {}))
    for app in black_horses:
        _enrich_from_snapshot(app, snapshots.get(app.app_id, {}))

    # Sort new listings: newest release first, then by review count
    new_listings.sort(
        key=lambda a: (a.release_date or "", a.total_reviews),
        reverse=True,
    )

    return new_listings, black_horses, snapshots


def fetch_all_black_horses() -> Tuple[List[AppProject], Dict]:
    """Backward-compatible wrapper."""
    _, black_horses, snapshots = fetch_app_store_data()
    return black_horses, snapshots
