import os
import sys
import time
from typing import List

try:
    from dotenv import load_dotenv
    load_dotenv()
except ImportError:
    pass

from scraper import fetch_all, enrich_readme
from analyzer import analyze_project
from app_store_client import (
    fetch_app_store_data,
    save_snapshots,
    batch_enrich_descriptions,
    mark_new_listing_reported,
)
from app_analyzer import analyze_app, rank_apps_for_push
from notifier import send_report
from reporter import write_report
from models import Project, AnalysisResult, AppAnalysisResult
from utils import setup_logger

logger = setup_logger("main")

ANALYZE_TRENDING = int(os.getenv("ANALYZE_TRENDING", "12"))
ANALYZE_SEARCH   = int(os.getenv("ANALYZE_SEARCH",   "8"))
APP_ANALYZE_N    = int(os.getenv("APP_ANALYZE_N",    "10"))
APP_PUSH_N       = int(os.getenv("APP_PUSH_N",       "100"))
SKIP_GITHUB      = os.getenv("SKIP_GITHUB", "").lower() in ("1", "true", "yes")
SKIP_APPSTORE    = os.getenv("SKIP_APPSTORE", "").lower() in ("1", "true", "yes")


def _pages_url() -> str:
    explicit = os.getenv("PAGES_URL", "")
    if explicit:
        return explicit
    repo = os.getenv("GITHUB_REPOSITORY", "")
    if repo and "/" in repo:
        owner, name = repo.split("/", 1)
        return f"https://{owner}.github.io/{name}/"
    return ""


def _pick(projects: List[Project]) -> List[Project]:
    trending = [p for p in projects if p.source.startswith("trending")][:ANALYZE_TRENDING]
    search   = [p for p in projects if p.source == "search"][:ANALYZE_SEARCH]
    return trending + search


def _run_github_pipeline() -> List[AnalysisResult]:
    start = time.time()
    logger.info("=== GitHub 黑马雷达 启动 ===")

    try:
        projects = fetch_all(since_days=3)
    except Exception as e:
        logger.error("Aggregation failed: %s", e)
        projects = []

    if not projects:
        logger.warning("No GitHub projects fetched")
        return []

    to_analyze = _pick(projects)
    logger.info(
        "Selected %d for analysis: %d trending + %d search",
        len(to_analyze),
        sum(1 for p in to_analyze if p.source.startswith("trending")),
        sum(1 for p in to_analyze if p.source == "search"),
    )

    logger.info("Enriching %d projects with README...", len(to_analyze))
    for p in to_analyze:
        enrich_readme(p)

    results: List[AnalysisResult] = []
    for project in to_analyze:
        logger.info("Analyzing: %s", project.full_name)
        results.append(analyze_project(project))

    success_count = sum(1 for r in results if r.success)
    logger.info(
        "=== GitHub 完成: 采集 %d 个，分析 %d/%d 成功，耗时 %.1fs ===",
        len(projects), success_count, len(results), time.time() - start,
    )
    return results


def _run_appstore_pipeline():
    """Returns (picked, new_listing_results, app_results, pool_size, hits, snapshots)."""
    logger.info("=== App Store 雷达 启动 ===")
    new_pool, black_horses, snapshots = fetch_app_store_data()
    pool_size = len(new_pool)
    hits = len(black_horses)
    black_horse_ids = {a.app_id for a in black_horses}

    pool_for_rank = [a for a in new_pool if a.app_id not in black_horse_ids]
    picked = rank_apps_for_push(pool_for_rank, top_n=APP_PUSH_N)
    to_analyze_horses = black_horses[:APP_ANALYZE_N]

    logger.info(
        "App Store: 上新候选 %d → 顾问筛选 %d；黑马命中 %d（分析 %d）",
        pool_size, len(picked), hits, len(to_analyze_horses),
    )

    batch_enrich_descriptions(picked + to_analyze_horses)

    new_listing_results: List[AppAnalysisResult] = []
    for app in picked:
        app.filter_trigger = "上新"
        logger.info("上新 Analyzing: %s (%s)", app.title, app.region)
        result = analyze_app(app)
        new_listing_results.append(result)
        # 1B: only mark after successful analysis
        if result.success:
            mark_new_listing_reported(snapshots, [app.app_id])

    app_results: List[AppAnalysisResult] = []
    for app in to_analyze_horses:
        logger.info("黑马 Analyzing: %s (%s)", app.title, app.region)
        app_results.append(analyze_app(app))

    new_ok = sum(1 for r in new_listing_results if r.success)
    horse_ok = sum(1 for r in app_results if r.success)
    logger.info(
        "=== App Store 完成: 上新分析 %d/%d，黑马分析 %d/%d 成功 ===",
        new_ok, len(new_listing_results), horse_ok, len(app_results),
    )
    return picked, new_listing_results, app_results, pool_size, hits, snapshots


def main() -> int:
    if SKIP_GITHUB and SKIP_APPSTORE:
        logger.error("SKIP_GITHUB and SKIP_APPSTORE both set — nothing to run")
        return 1

    results: List[AnalysisResult] = []
    github_pipeline_ok = True
    if SKIP_GITHUB:
        logger.info("SKIP_GITHUB=1 — 跳过 GitHub 管道")
    else:
        try:
            results = _run_github_pipeline()
        except Exception as e:
            github_pipeline_ok = False
            logger.error("GitHub pipeline failed: %s: %s", type(e).__name__, e, exc_info=True)

    app_results: List[AppAnalysisResult] = []
    new_listing_results: List[AppAnalysisResult] = []
    # None = App Store skipped this run (preserve previous Pages/archive app sections)
    new_listings = None
    app_pool_size = 0
    app_snapshots = {}
    app_hits_total = 0
    app_pipeline_ok = True

    if SKIP_APPSTORE:
        logger.info("SKIP_APPSTORE=1 — 跳过 App Store 管道")
    else:
        try:
            (
                new_listings,
                new_listing_results,
                app_results,
                app_pool_size,
                app_hits_total,
                app_snapshots,
            ) = _run_appstore_pipeline()
        except Exception as e:
            app_pipeline_ok = False
            new_listings = []
            logger.warning(
                "App Store pipeline failed (non-fatal): %s: %s",
                type(e).__name__, e, exc_info=True,
            )
        finally:
            if app_snapshots:
                save_snapshots(app_snapshots)

    ran_github = not SKIP_GITHUB
    ran_app = not SKIP_APPSTORE

    if ran_github and not github_pipeline_ok and not (ran_app and app_pipeline_ok):
        logger.warning("Required pipelines failed; skip report + WeCom")
        return 1
    if ran_app and not app_pipeline_ok and not (ran_github and github_pipeline_ok):
        logger.warning("Required pipelines failed; skip report + WeCom")
        return 1

    app_only = SKIP_GITHUB
    github_only = SKIP_APPSTORE

    # Always write Pages/archive when at least one pipeline produced output or ran cleanly
    should_write = False
    if ran_github and github_pipeline_ok:
        should_write = True
    if ran_app and app_pipeline_ok:
        should_write = True

    if not should_write:
        logger.warning("Nothing to write; skip report + WeCom")
        return 1

    write_report(
        results,
        app_results=app_results,
        new_listings=new_listings,
        new_listing_results=new_listing_results,
        app_pool_size=app_pool_size,
        preserve_github=app_only,
        preserve_app=github_only,
    )

    # 7C: app-only — skip WeCom when no successful 上新 and no black-horse hits
    if app_only:
        new_ok = sum(1 for r in new_listing_results if r.success)
        if new_ok == 0 and app_hits_total == 0:
            logger.info("App Store: 无新上架成功分析且无黑马命中 — 跳过企微推送")
            return 0

    if github_only and not results:
        logger.info("GitHub: 无结果 — 跳过企微推送")
        return 0

    if not results and not new_listing_results and not app_results and app_hits_total == 0:
        logger.info("无推送内容 — 跳过企微")
        return 0

    send_report(
        results,
        pages_url=_pages_url(),
        app_results=app_results,
        app_hits_total=app_hits_total,
        new_listings=new_listings or [],
        new_listing_results=new_listing_results,
        app_pool_size=app_pool_size,
        app_only=app_only,
        github_only=github_only,
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())
