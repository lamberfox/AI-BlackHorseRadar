import os
import requests
from typing import List

from models import AnalysisResult
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


def send_report(results: List[AnalysisResult], pages_url: str = "") -> bool:
    today = beijing_today()
    total = len(results)
    success = sum(1 for r in results if r.success)

    top3 = [r for r in results if r.success][:3]
    top3_lines = "\n".join(
        f"> **{i+1}.** [{r.project.full_name}]({r.project.html_url}) "
        f"{'★' * r.dark_horse_score}{'☆' * (5 - r.dark_horse_score)}"
        for i, r in enumerate(top3)
    )

    link_line = f"\n**[📊 点击查看完整日报 →]({pages_url})**\n" if pages_url else ""

    msg = (
        f"# 🎯 GitHub 黑马技术雷达（{today}）\n\n"
        f"> 采样 **{total}** 个项目，成功分析 **{success}** 个\n\n"
        f"{top3_lines}\n"
        f"{link_line}\n"
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
