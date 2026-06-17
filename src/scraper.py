import os
import re
import time
import requests
from typing import List, Dict
from bs4 import BeautifulSoup

from models import Project
from utils import setup_logger, retry, days_ago

logger = setup_logger(__name__)

GITHUB_API = "https://api.github.com"
GITHUB_TRENDING = "https://github.com/trending"
README_MAX_LEN = int(os.getenv("README_MAX_LEN", "2000"))
TOP_N = int(os.getenv("TOP_N", "15"))

_HEADERS_BROWSER = {
    "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36",
    "Accept-Language": "en-US,en;q=0.9",
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
}


def _api_headers() -> dict:
    token = os.getenv("GITHUB_TOKEN", "")
    h = {"Accept": "application/vnd.github+json", "X-GitHub-Api-Version": "2022-11-28"}
    if token:
        h["Authorization"] = f"Bearer {token}"
    return h


@retry(max_attempts=3, delay=3.0, exceptions=(requests.RequestException,))
def _get_json(url: str, params: dict = None) -> dict:
    resp = requests.get(url, headers=_api_headers(), params=params, timeout=15)
    resp.raise_for_status()
    return resp.json()


def _parse_stars(text: str) -> int:
    cleaned = re.sub(r"[,\s]", "", text.strip())
    try:
        return int(cleaned)
    except ValueError:
        return 0


def fetch_trending(since: str = "daily") -> List[Project]:
    """Scrape github.com/trending for daily / weekly / monthly."""
    url = GITHUB_TRENDING if since == "daily" else f"{GITHUB_TRENDING}?since={since}"
    try:
        resp = requests.get(url, headers=_HEADERS_BROWSER, timeout=20)
        resp.raise_for_status()
    except Exception as e:
        logger.warning("Trending fetch failed (%s): %s", since, e)
        return []

    soup = BeautifulSoup(resp.text, "html.parser")
    articles = soup.select("article.Box-row")
    projects: List[Project] = []

    for article in articles:
        try:
            # repo path: /owner/repo
            link = article.select_one("h2 a")
            if not link:
                continue
            path = link["href"].strip("/")
            parts = path.split("/")
            if len(parts) != 2:
                continue
            owner, repo_name = parts
            full_name = f"{owner}/{repo_name}"

            desc_el = article.select_one("p")
            description = desc_el.get_text(strip=True) if desc_el else ""

            lang_el = article.select_one("[itemprop='programmingLanguage']")
            language = lang_el.get_text(strip=True) if lang_el else None

            # total stars
            star_el = article.select_one(f"a[href='/{full_name}/stargazers']")
            stars = _parse_stars(star_el.get_text()) if star_el else 0

            projects.append(Project(
                full_name=full_name,
                html_url=f"https://github.com/{full_name}",
                description=description,
                language=language,
                stargazers_count=stars,
                owner_login=owner,
                created_at="",
            ))
        except Exception as e:
            logger.warning("Failed to parse trending article: %s", e)

    logger.info("Trending (%s): %d projects", since, len(projects))
    return projects


def fetch_projects(since_days: int = 3) -> List[Project]:
    """GitHub Search API — recent fast-growing repos."""
    since = days_ago(since_days)
    data = _get_json(
        f"{GITHUB_API}/search/repositories",
        params={"q": f"created:>{since}", "sort": "stars", "order": "desc", "per_page": TOP_N},
    )
    items = data.get("items", [])
    projects = []
    for item in items:
        try:
            projects.append(Project(
                full_name=item["full_name"],
                html_url=item["html_url"],
                description=item.get("description") or "",
                language=item.get("language"),
                stargazers_count=item["stargazers_count"],
                owner_login=item["owner"]["login"],
                created_at=item["created_at"],
            ))
        except Exception as e:
            logger.warning("Skipping search result: %s", e)
    logger.info("Search API (past %dd): %d projects", since_days, len(projects))
    return projects


def fetch_all(since_days: int = 3) -> List[Project]:
    """Aggregate all sources, deduplicate, return sorted by stars."""
    seen: Dict[str, Project] = {}

    for p in fetch_projects(since_days):
        seen[p.full_name] = p

    for period in ("daily", "weekly", "monthly"):
        for p in fetch_trending(period):
            if p.full_name not in seen:
                seen[p.full_name] = p
        time.sleep(1)

    combined = sorted(seen.values(), key=lambda p: p.stargazers_count, reverse=True)
    logger.info("Aggregated total: %d unique projects", len(combined))
    return combined


def enrich_readme(project: Project) -> Project:
    """Fetch and attach README excerpt. Mutates project in-place."""
    owner = project.owner_login
    repo = project.full_name.split("/", 1)[1]
    try:
        headers = {**_api_headers(), "Accept": "application/vnd.github.raw+json"}
        resp = requests.get(
            f"{GITHUB_API}/repos/{owner}/{repo}/readme",
            headers=headers,
            timeout=15,
        )
        if resp.status_code == 200:
            project.readme_excerpt = resp.text[:README_MAX_LEN]
    except Exception as e:
        logger.warning("README fetch failed for %s: %s", project.full_name, e)
    time.sleep(2)
    return project
