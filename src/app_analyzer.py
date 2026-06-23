import json
import os
import re
from functools import lru_cache
from typing import Dict, List, Tuple

import requests

from models import AppProject, AppAnalysisResult
from utils import setup_logger, retry

logger = setup_logger(__name__)

DEEPSEEK_API = "https://api.deepseek.com/v1/chat/completions"
_PROMPTS_FILE = os.path.join(os.path.dirname(__file__), "..", "appStore顾问.md")


@lru_cache(maxsize=1)
def _load_prompts() -> Dict[str, str]:
    with open(_PROMPTS_FILE, encoding="utf-8") as f:
        content = f.read()
    sections: Dict[str, str] = {}
    parts = re.split(r"^## (.+)$", content, flags=re.MULTILINE)
    for i in range(1, len(parts) - 1, 2):
        key = parts[i].strip()
        body = parts[i + 1].strip()
        sections[key] = body
    return sections


def _get_prompt(key: str) -> str:
    return _load_prompts()[key]


@retry(max_attempts=2, delay=5.0, exceptions=(requests.RequestException,))
def _call_deepseek(
    system_prompt: str,
    user_prompt: str,
    max_tokens: int = 1800,
    temperature: float = 0.35,
) -> str:
    api_key = os.getenv("DEEPSEEK_API_KEY", "")
    if not api_key:
        raise ValueError("DEEPSEEK_API_KEY not set")

    resp = requests.post(
        DEEPSEEK_API,
        headers={"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"},
        json={
            "model": "deepseek-chat",
            "messages": [
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt},
            ],
            "temperature": temperature,
            "max_tokens": max_tokens,
            "response_format": {"type": "json_object"},
        },
        timeout=45,
    )
    resp.raise_for_status()
    return resp.json()["choices"][0]["message"]["content"]


def _fmt_reviews(reviews: list) -> str:
    if not reviews:
        return "（无评论数据）"
    lines = [f"{i+1}. {r}" for i, r in enumerate(reviews[:30])]
    return "\n".join(lines)


def analyze_app(app: AppProject) -> AppAnalysisResult:
    reviews_text = _fmt_reviews(app.reviews)

    user_prompt = _get_prompt("APP_USER_PROMPT").format(
        title=app.title,
        region=app.region,
        category=app.category,
        price=app.price,
        developer=app.developer,
        description=app.description or "（无描述）",
        filter_trigger=app.filter_trigger,
        reviews=reviews_text,
    )

    try:
        raw = _call_deepseek(_get_prompt("APP_SYSTEM_PROMPT"), user_prompt)
        data = json.loads(raw)

        def _s(key: str) -> str:
            return str(data.get(key, "推测依据不足")) or "推测依据不足"

        def _i(key: str, default: int = 0) -> int:
            try:
                return int(data.get(key, default))
            except (ValueError, TypeError):
                return default

        def _f(key: str, default: float = 0.0) -> float:
            try:
                return float(data.get(key, default))
            except (ValueError, TypeError):
                return default

        def _b(key: str, default: bool = False) -> bool:
            v = data.get(key, default)
            if isinstance(v, bool):
                return v
            if isinstance(v, str):
                return v.strip().lower() in ("true", "1", "yes", "y")
            return bool(v)

        def _extract_payback_weeks() -> float:
            direct = data.get("payback_period_weeks", 0)
            try:
                return float(direct)
            except (TypeError, ValueError):
                m = re.search(r"(\d+(?:\.\d+)?)", str(direct))
                return float(m.group(1)) if m else 99.0

        def _extract_total_score() -> float:
            # Priority: explicit total_score field, else parse scoring_breakdown text
            if "total_score" in data:
                return _f("total_score", 0.0)
            text = str(data.get("scoring_breakdown", ""))
            m = re.search(r"total[_\s-]*score\s*=\s*(\d+(?:\.\d+)?)", text, re.I)
            if m:
                return float(m.group(1))
            # fallback from dark_horse_score -> rough proxy
            return _i("dark_horse_score", 0) * 10.0

        def _rule_based_verdict(total_score: float, payback_weeks: float) -> str:
            if total_score >= 75.0 and payback_weeks <= 6.0:
                return "强烈跟进"
            if total_score < 55.0 or payback_weeks > 12.0:
                return "放弃"
            return "观望"

        figma_brief = _s("figma_create_brief")
        if figma_brief == "推测依据不足":
            figma_brief = _s("v0_prompt")  # backward compat

        payback_weeks = _extract_payback_weeks()
        total_score = _extract_total_score()
        model_verdict = _s("go_no_go")
        rule_verdict = _rule_based_verdict(total_score, payback_weeks)
        needs_review = _b("needs_manual_review", False) or (model_verdict != rule_verdict)

        return AppAnalysisResult(
            app=app,
            product_what=_s("product_what"),
            go_no_go=rule_verdict,
            dark_horse_score=_i("dark_horse_score"),
            clone_score=_i("clone_score"),
            signal_validity=_s("signal_validity"),
            arbitrage_space=_s("arbitrage_space"),
            payback_period_weeks=str(data.get("payback_period_weeks", "推测依据不足")),
            intercept_window=_s("payback_period_weeks") if _s("payback_period_weeks") != "推测依据不足" else _s("intercept_window"),
            pain_point=_s("pain_point"),
            commercial_critique=_s("arbitrage_space") if _s("arbitrage_space") != "推测依据不足" else _s("commercial_critique"),
            figma_create_brief=figma_brief,
            flutter_arch=_s("flutter_arch"),
            clone_edge=_s("clone_edge"),
            art_cost=_s("art_cost"),
            flutter_feasibility=_i("flutter_feasibility"),
            scoring_breakdown=_s("scoring_breakdown"),
            cac_estimate_range=_s("cac_estimate_range"),
            conversion_estimate_range=_s("conversion_estimate_range"),
            arppu_or_price_assumption=_s("arppu_or_price_assumption"),
            confidence_level=_s("confidence_level"),
            needs_manual_review=needs_review,
            deal_breakers=_s("deal_breakers"),
            v0_prompt=figma_brief,
        )
    except Exception as e:
        logger.error("App analysis failed for %s: %s", app.title, e)
        return AppAnalysisResult(app=app, error=str(e))


def _fmt_rank_line(app: AppProject) -> str:
    desc = (app.description or "").replace("\n", " ")[:120]
    return (
        f"- [{app.app_id}] {app.title} | {app.region} | {app.category} | "
        f"{app.price} | {app.developer} | {desc or '（无描述）'}"
    )


def _combined_score(scores: dict) -> float:
    try:
        roi = int(scores.get("roi_score", 0))
        novelty = int(scores.get("novelty_score", 0))
    except (TypeError, ValueError):
        return 0.0
    return roi * 0.6 + novelty * 0.4


def _score_batch(batch: List[AppProject], top_n: int) -> Dict[str, dict]:
    app_lines = "\n".join(_fmt_rank_line(a) for a in batch)
    user_prompt = _get_prompt("APP_RANK_USER_PROMPT").format(
        pool_size=len(batch),
        top_n=min(top_n, len(batch)),
        app_lines=app_lines,
    )
    raw = _call_deepseek(
        _get_prompt("APP_RANK_SYSTEM_PROMPT"),
        user_prompt,
        max_tokens=3500,
        temperature=0.25,
    )
    data = json.loads(raw)
    out: Dict[str, dict] = {}
    for item in data.get("scores", []):
        aid = str(item.get("app_id", ""))
        if not aid:
            continue
        out[aid] = {
            "roi_score": int(item.get("roi_score", 0) or 0),
            "novelty_score": int(item.get("novelty_score", 0) or 0),
            "pick_reason": str(item.get("pick_reason", "") or ""),
        }
    return out


def rank_apps_for_push(apps: List[AppProject], top_n: int = 100) -> List[AppProject]:
    """Advisor pre-screen: pick top_n by ROI + novelty from the full pool."""
    if not apps:
        return []
    if len(apps) <= top_n:
        logger.info("Pool size %d <= push limit %d, skip ranking", len(apps), top_n)
        return list(apps)

    all_scores: Dict[str, dict] = {}
    batch_size = 45
    for i in range(0, len(apps), batch_size):
        batch = apps[i : i + batch_size]
        logger.info("Ranking batch %d-%d / %d", i + 1, i + len(batch), len(apps))
        try:
            all_scores.update(_score_batch(batch, top_n))
        except Exception as e:
            logger.warning("Rank batch %d failed: %s", i // batch_size + 1, e)

    by_id = {a.app_id: a for a in apps}
    ranked_ids = sorted(all_scores.keys(), key=lambda k: _combined_score(all_scores[k]), reverse=True)

    picked: List[AppProject] = []
    for aid in ranked_ids:
        if aid not in by_id:
            continue
        app = by_id[aid]
        s = all_scores[aid]
        app.roi_score = s.get("roi_score", 0)
        app.novelty_score = s.get("novelty_score", 0)
        app.pick_reason = s.get("pick_reason", "")
        picked.append(app)
        if len(picked) >= top_n:
            break

    # Fallback: fill remaining slots in RSS order if model missed ids
    if len(picked) < top_n:
        picked_ids = {a.app_id for a in picked}
        for app in apps:
            if app.app_id in picked_ids:
                continue
            picked.append(app)
            if len(picked) >= top_n:
                break

    logger.info("Advisor picked %d / %d from pool", len(picked), len(apps))
    return picked

