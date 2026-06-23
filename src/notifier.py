import os
import requests
from typing import List

from models import AnalysisResult, AppAnalysisResult, AppProject
from utils import setup_logger, retry, beijing_today

logger = setup_logger(__name__)


@retry(max_attempts=3, delay=3.0, exceptions=(requests.RequestException,))
def _post(markdown: str) -> None:
    url = os.getenv("WECOM_WEBHOOK_URL", "")
    if not url:
        raise ValueError("WECOM_WEBHOOK_URL not set")

    resp = requests.post(
        url,
        json={"msgtype": "markdown", "markdown": {"content": markdown}},
        timeout=15,
    )
    resp.raise_for_status()
    body = resp.json()
    if body.get("errcode", 0) != 0:
        raise RuntimeError(f"WeCom error: {body}")


def _new_listings_summary(
    new_listing_results: List[AppAnalysisResult],
    app_pool_size: int = 0,
    limit: int = 5,
) -> str:
    if not new_listing_results and app_pool_size == 0:
        return ""
    region_flag = {"us": "🇺🇸", "jp": "🇯🇵"}
    success = [r for r in new_listing_results if r.success]
    lines = []
    for i, r in enumerate(success[:limit]):
        app = r.app
        flag = region_flag.get(app.region, app.region.upper())
        released = app.release_date[:10] if app.release_date else "?"
        lines.append(
            f"> **{i+1}.** [{app.title}]({app.html_url}) "
            f"{flag} {app.category} · 上架{released} · {r.go_no_go} · 克隆{r.clone_score}/5"
        )
        if r.commercial_critique and r.commercial_critique != "推测依据不足":
            critique = r.commercial_critique.replace("\n", " ")[:80]
            lines.append(f">    ⚠️ {critique}{'…' if len(r.commercial_critique) > 80 else ''}")
        elif app.roi_score or app.novelty_score:
            pr = app.pick_reason[:50] + ("…" if len(app.pick_reason) > 50 else "")
            lines.append(
                f">    📊 性价比{app.roi_score}/10 · 新颖{app.novelty_score}/10"
                + (f" · {pr}" if pr else "")
            )
    pool = app_pool_size or len(success)
    more = ""
    if app_pool_size > len(success):
        more = f"\n> 从 **{app_pool_size}** 个采集池中筛选推送 **{len(success)}** 个（见完整报告）"
    elif len(success) > limit:
        more = f"\n> … 另有 **{len(success) - limit}** 个（见完整报告）"

    if not lines and app_pool_size > 0:
        return (
            f"\n\n---\n**🆕 App Store 上新监控**\n"
            f"> 采集池 **{app_pool_size}** 个，顾问筛选后 AI 分析失败，请查看日志。"
        )
    return (
        f"\n\n---\n**🆕 App Store 顾问推送**\n"
        f"> 采集 **{pool}** 个 → 筛选推送 **{len(success)}** 个（性价比+新颖性）\n"
        + "\n".join(lines)
        + more
    )


def _black_horse_summary(
    app_results: List[AppAnalysisResult],
    app_hits_total: int = 0,
    pages_url: str = "",
) -> str:
    hits = app_hits_total
    success = [r for r in app_results if r.success]

    if hits == 0:
        return (
            "\n\n---\n**📱 App Store 黑马雷达**\n"
            "> 本次未命中黑马阈值，上新 App 已在持续跟踪，下次对比评论斜率。"
        )
    if not success:
        return f"\n\n---\n**📱 App Store 黑马雷达**\n> 命中 {hits} 个，分析均失败，请查看日志。"

    region_flag = {"us": "🇺🇸", "jp": "🇯🇵"}
    lines = []
    for i, r in enumerate(success):
        flag = region_flag.get(r.app.region, r.app.region.upper())
        trigger = r.app.filter_trigger or "?"
        lines.append(
            f"> **{i+1}.** [{r.app.title}]({r.app.html_url}) "
            f"{flag} {r.app.category} · 指标{trigger} · {r.go_no_go} · 克隆{r.clone_score}/5"
        )
        if r.commercial_critique and r.commercial_critique != "推测依据不足":
            critique = r.commercial_critique.replace("\n", " ")[:80]
            lines.append(f">    ⚠️ {critique}{'…' if len(r.commercial_critique) > 80 else ''}")

    more = ""
    if hits > len(success):
        more = f"\n> 另有 **{hits - len(success)}** 个命中未分析（见完整报告）"
    link = f"\n> [查看完整分析 →]({pages_url})" if pages_url else ""

    return (
        f"\n\n---\n**📱 App Store 黑马雷达**\n"
        f"> 命中 **{hits}** 个，成功分析 **{len(success)}** 个{more}\n"
        + "\n".join(lines)
        + link
    )


def send_report(
    results: List[AnalysisResult],
    pages_url: str = "",
    app_results: List[AppAnalysisResult] = None,
    app_hits_total: int = 0,
    new_listings: List[AppProject] = None,
    new_listing_results: List[AppAnalysisResult] = None,
    app_pool_size: int = 0,
    app_only: bool = False,
) -> bool:
    if app_results is None:
        app_results = []
    if new_listings is None:
        new_listings = []
    if new_listing_results is None:
        new_listing_results = []
    today = beijing_today()
    total = len(results)
    success = sum(1 for r in results if r.success)

    app_block = _new_listings_summary(
        new_listing_results,
        app_pool_size=app_pool_size,
    ) + _black_horse_summary(
        app_results, app_hits_total=app_hits_total, pages_url=pages_url,
    )
    link_line = f"\n**[📊 点击查看完整日报 →]({pages_url})**\n" if pages_url else ""

    if app_only:
        msg = (
            f"# 📱 App Store 雷达（{today}）\n"
            f"{link_line}"
            f"{app_block}\n\n"
            f"> ⚠️ 本日报仅供技术研判参考，不构成任何投资建议。"
        )
    else:
        top3 = [r for r in results if r.success][:3]
        top3_lines = "\n".join(
            f"> **{i+1}.** [{r.project.full_name}]({r.project.html_url}) "
            f"{'★' * r.dark_horse_score}{'☆' * (5 - r.dark_horse_score)}"
            for i, r in enumerate(top3)
        )
        msg = (
            f"# 🎯 GitHub 黑马技术雷达（{today}）\n\n"
            f"> 采样 **{total}** 个项目，成功分析 **{success}** 个\n\n"
            f"{top3_lines}\n"
            f"{link_line}"
            f"{app_block}\n\n"
            f"> ⚠️ 本日报仅供技术研判参考，不构成任何投资建议。"
        )

    try:
        _post(msg)
        logger.info("WeCom notification sent")
        return True
    except Exception as e:
        logger.error("Failed to send WeCom notification: %s", e)
        try:
            _post(f"# GitHub 黑马雷达（{today}）\n\n⚠️ 通知发送失败，请查看 Actions 日志。")
        except Exception:
            pass
        return False
