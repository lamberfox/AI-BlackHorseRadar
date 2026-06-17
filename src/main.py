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
from notifier import send_report
from reporter import write_report
from models import AnalysisResult
from utils import setup_logger, beijing_today

logger = setup_logger("main")

ANALYZE_N = int(os.getenv("ANALYZE_N", "20"))


def _pages_url() -> str:
    explicit = os.getenv("PAGES_URL", "")
    if explicit:
        return explicit
    repo = os.getenv("GITHUB_REPOSITORY", "")
    if repo and "/" in repo:
        owner, name = repo.split("/", 1)
        return f"https://{owner}.github.io/{name}/"
    return ""


def main() -> int:
    start = time.time()
    logger.info("=== GitHub 黑马雷达 启动 ===")

    try:
        projects = fetch_all(since_days=3)
    except Exception as e:
        logger.error("Aggregation failed: %s", e)
        projects = []

    if not projects:
        logger.warning("No projects fetched; sending fallback notification")
        try:
            from notifier import _post
            _post(f"# GitHub 黑马雷达（{beijing_today()}）\n\n⚠️ 采集阶段失败，请检查 Actions 日志。")
        except Exception:
            pass
        return 1

    logger.info("Enriching top %d projects with README...", ANALYZE_N)
    to_analyze = projects[:ANALYZE_N]
    for p in to_analyze:
        enrich_readme(p)

    results: List[AnalysisResult] = []
    for project in to_analyze:
        logger.info("Analyzing: %s", project.full_name)
        results.append(analyze_project(project))

    success_count = sum(1 for r in results if r.success)
    elapsed = time.time() - start
    logger.info(
        "=== 完成: 采集 %d 个，分析 %d/%d 成功，耗时 %.1fs ===",
        len(projects), success_count, len(results), elapsed,
    )

    write_report(results)
    send_report(results, pages_url=_pages_url())
    return 0


if __name__ == "__main__":
    sys.exit(main())
