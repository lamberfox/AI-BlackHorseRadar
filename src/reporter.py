import html
import os
from pathlib import Path
from typing import List, Optional

from models import AnalysisResult, AppAnalysisResult, AppProject
from utils import setup_logger, beijing_today

logger = setup_logger(__name__)

DOCS_DIR = Path(__file__).parent.parent / "docs"
ARCHIVE_DIR = Path(__file__).parent.parent / "knowledge"

_SOURCE_LABEL = {
    "search":           ("🚀", "近3天新星", "#1f6feb"),
    "trending_daily":   ("🔥", "今日热榜", "#f85149"),
    "trending_weekly":  ("📈", "本周热榜", "#f0883e"),
    "trending_monthly": ("🌟", "本月热榜", "#ffd700"),
}


def _e(s: str) -> str:
    return html.escape(str(s))


def _score_color(score: int) -> str:
    return {5: "#ffd700", 4: "#f0883e", 3: "#3fb950", 2: "#8b949e", 1: "#6e7681"}.get(score, "#6e7681")


def _stars(score: int) -> str:
    return "★" * score + "☆" * (5 - score)


def _field(label: str, value: str) -> str:
    return f"""<div class="field">
      <span class="fl">{label}</span>
      <span class="fv">{_e(value)}</span>
    </div>"""


def _card(result: AnalysisResult, index: int) -> str:
    p = result.project
    icon, label, color = _SOURCE_LABEL.get(p.source, ("·", p.source, "#8b949e"))
    lang = f'<span class="badge">{_e(p.language)}</span>' if p.language else ""
    created = f'<span class="meta-item">创建: {_e(p.created_at[:10])}</span>' if p.created_at else ""
    sc = _score_color(result.dark_horse_score)

    if not result.success:
        return f"""<div class="card card-error">
      <div class="card-header">
        <span class="idx">#{index}</span>
        <a href="{_e(p.html_url)}" target="_blank" class="repo-link">{_e(p.full_name)}</a>
        <span class="src-badge" style="color:{color};border-color:{color}44">{icon} {label}</span>
      </div>
      <div class="meta">{lang}<span class="meta-item">⭐ {p.stargazers_count:,}</span>{created}</div>
      <p class="err">⚠️ 分析失败: {_e(str(result.error))}</p>
    </div>"""

    return f"""<div class="card">
      <div class="card-header">
        <span class="idx">#{index}</span>
        <a href="{_e(p.html_url)}" target="_blank" class="repo-link">{_e(p.full_name)}</a>
        <span class="src-badge" style="color:{color};border-color:{color}44">{icon} {label}</span>
        <span class="score" style="background:{sc}22;color:{sc};border-color:{sc}55">{_stars(result.dark_horse_score)} {result.dark_horse_score}/5</span>
      </div>
      <div class="meta">{lang}<span class="meta-item">⭐ {p.stargazers_count:,}</span>{created}</div>
      <p class="desc">{_e(p.description)}</p>
      <div class="fields">
        {_field("⚡ 生产力置换", result.productivity_replacement)}
        {_field("🛠️ 技术壁垒", result.architecture_core)}
        {_field("🧬 生态卡位", result.glue_cement_grade)}
        {_field("💰 TPD 变现路径", result.tpd_potential)}
        {_field("💡 变现切入点", result.monetization_angle)}
        {_field("🏗️ 可落地产品形态", result.product_form)}
        {_field("🚨 巨头背刺风险", result.backstab_risk)}
      </div>
    </div>"""


def _section(title: str, subtitle: str, results: List[AnalysisResult], start_index: int) -> str:
    if not results:
        return ""
    cards = "\n".join(_card(r, start_index + i) for i, r in enumerate(results))
    return f"""<section class="section">
    <div class="section-header">
      <h2>{title}</h2>
      <p class="section-sub">{subtitle}</p>
    </div>
    <div class="grid">{cards}</div>
  </section>"""


def generate_html(results: List[AnalysisResult]) -> str:
    today = beijing_today()
    total = len(results)
    success = sum(1 for r in results if r.success)

    trending = [r for r in results if r.project.source.startswith("trending")]
    search   = [r for r in results if r.project.source == "search"]

    sec_trending = _section(
        "🔥 GitHub Trending 热榜分析",
        "来源：GitHub Trending 日榜 / 周榜 / 月榜，综合去重后 AI 研判",
        trending, 1,
    )
    sec_search = _section(
        "🚀 近3天高速崛起",
        "来源：GitHub Search API — 近3天新建项目，按 Star 增速排序",
        search, len(trending) + 1,
    )

    return f"""<!DOCTYPE html>
<html lang="zh-CN">
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width,initial-scale=1.0">
  <title>GitHub 黑马技术雷达 — {today}</title>
  <style>
    *,*::before,*::after{{box-sizing:border-box;margin:0;padding:0}}
    body{{font-family:-apple-system,BlinkMacSystemFont,"Segoe UI",Helvetica,Arial,sans-serif;
         background:#0d1117;color:#c9d1d9;line-height:1.65}}
    a{{color:#58a6ff;text-decoration:none}}
    a:hover{{text-decoration:underline}}

    .site-header{{background:#161b22;border-bottom:1px solid #30363d;padding:28px 32px}}
    .site-header h1{{font-size:1.6rem;font-weight:700;color:#f0f6fc}}
    .site-header h1 em{{color:#f0883e;font-style:normal}}
    .hm{{margin-top:10px;color:#8b949e;font-size:.875rem;display:flex;gap:20px;flex-wrap:wrap}}
    .hm strong{{color:#c9d1d9}}

    .container{{max-width:1500px;margin:0 auto;padding:32px 16px}}

    .section{{margin-bottom:48px}}
    .section-header{{margin-bottom:20px;padding-bottom:12px;border-bottom:1px solid #21262d}}
    .section-header h2{{font-size:1.2rem;font-weight:700;color:#f0f6fc}}
    .section-sub{{color:#8b949e;font-size:.85rem;margin-top:4px}}

    .grid{{display:grid;grid-template-columns:repeat(auto-fill,minmax(440px,1fr));gap:16px}}

    .card{{background:#161b22;border:1px solid #30363d;border-radius:10px;padding:20px;
           transition:border-color .15s,box-shadow .15s}}
    .card:hover{{border-color:#58a6ff55;box-shadow:0 0 0 1px #58a6ff22}}
    .card-error{{border-color:#f8514933}}

    .card-header{{display:flex;align-items:center;gap:7px;flex-wrap:wrap;margin-bottom:10px}}
    .idx{{color:#484f58;font-size:.75rem;font-weight:600;flex-shrink:0}}
    .repo-link{{font-size:.95rem;font-weight:600;color:#58a6ff;flex:1;min-width:0;
                white-space:nowrap;overflow:hidden;text-overflow:ellipsis}}
    .src-badge{{font-size:.7rem;border:1px solid;border-radius:20px;padding:1px 8px;
                white-space:nowrap;flex-shrink:0}}
    .score{{font-size:.72rem;border:1px solid;border-radius:20px;padding:2px 9px;
            white-space:nowrap;flex-shrink:0}}

    .meta{{display:flex;gap:8px;flex-wrap:wrap;margin-bottom:10px;align-items:center}}
    .badge{{background:#21262d;color:#8b949e;border:1px solid #30363d;
            border-radius:4px;padding:1px 7px;font-size:.73rem}}
    .meta-item{{color:#8b949e;font-size:.78rem}}

    .desc{{color:#8b949e;font-size:.83rem;margin-bottom:14px;
           display:-webkit-box;-webkit-line-clamp:2;-webkit-box-orient:vertical;overflow:hidden}}

    .fields{{display:flex;flex-direction:column;gap:9px}}
    .field{{display:grid;grid-template-columns:130px 1fr;gap:8px;font-size:.83rem;
            padding:8px 10px;background:#0d1117;border-radius:6px}}
    .fl{{color:#8b949e;font-weight:500;padding-top:1px}}
    .fv{{color:#c9d1d9}}

    .err{{color:#f85149;font-size:.83rem;margin-top:8px}}

    .site-footer{{text-align:center;padding:32px;color:#484f58;font-size:.78rem;
                  border-top:1px solid #21262d;margin-top:16px}}

    @media(max-width:600px){{
      .grid{{grid-template-columns:1fr}}
      .field{{grid-template-columns:1fr}}
      .fl{{margin-bottom:2px}}
    }}
  </style>
</head>
<body>
  <header class="site-header">
    <h1>🎯 GitHub 黑马技术雷达 <em>{today}</em></h1>
    <div class="hm">
      <span>采样 <strong>{total}</strong> 个项目</span>
      <span>成功分析 <strong>{success}</strong> 个</span>
      <span>Trending 热榜 <strong>{len(trending)}</strong> 个</span>
      <span>近期新星 <strong>{len(search)}</strong> 个</span>
    </div>
  </header>
  <main class="container">
    {sec_trending}
    {sec_search}
  </main>
  <footer class="site-footer">
    ⚠️ 本日报仅供技术研判参考，不构成任何投资建议。每周一北京时间 09:00 自动更新。
  </footer>
</body>
</html>"""


def _new_listing_card(app: AppProject, index: int) -> str:
    region_flag = {"us": "🇺🇸", "jp": "🇯🇵"}.get(app.region, app.region.upper())
    released = app.release_date[:10] if app.release_date else "未知"
    tracked = app.first_seen[:10] if app.first_seen else "今日首次"
    star_pct = (
        f"{app.five_star_reviews}/{app.total_reviews} 五星"
        if app.total_reviews else "暂无评论"
    )

    return f"""<div class="card card-watch">
      <div class="card-header">
        <span class="idx">#{index}</span>
        <a href="{_e(app.html_url)}" target="_blank" class="repo-link">{_e(app.title)}</a>
        <span class="src-badge" style="color:#58a6ff;border-color:#58a6ff44">{region_flag} {_e(app.category)}</span>
      </div>
      <div class="meta">
        <span class="meta-item">上架 {released}</span>
        <span class="meta-item">跟踪自 {tracked}</span>
        <span class="meta-item">{_e(app.price)}</span>
        <span class="meta-item">💬 {star_pct}</span>
      </div>
      <p class="desc">{_e(app.developer)}</p>
    </div>"""


def _new_listings_section(
    results: List[AppAnalysisResult],
    start_index: int,
    pool_size: int = 0,
) -> str:
    if results:
        body = "\n".join(_app_card(r, start_index + i) for i, r in enumerate(results))
    else:
        body = '<p class="section-empty">今日 RSS 未发现新上架 App，快照持续跟踪中。</p>'

    pool_note = f"从 <strong>{pool_size}</strong> 个" if pool_size else "从采集池"
    sub = (
        f"来源：US/JP × 4分类 newapplications RSS（每类最多 {os.getenv('APP_RSS_LIMIT', '100')} 条），"
        f"顾问按性价比+新颖性筛选，{pool_note} 推送 Top <strong>{len(results)}</strong> 并完成深入分析"
    )
    return f"""<section class="section">
    <div class="section-header">
      <h2>🆕 App Store 上新监控</h2>
      <p class="section-sub">{sub}</p>
    </div>
    <div class="grid">{body}</div>
  </section>"""


def _go_no_go_color(verdict: str) -> str:
    return {
        "强烈跟进": "#3fb950",
        "观望":     "#f0883e",
        "放弃":     "#f85149",
    }.get(verdict, "#8b949e")


def _app_card(result: AppAnalysisResult, index: int) -> str:
    a = result.app
    region_flag = {"us": "🇺🇸", "jp": "🇯🇵"}.get(a.region, a.region.upper())
    trigger_label = {
        "A": "冷启动爆发", "B": "斜率飙升", "上新": "新上架",
    }.get(a.filter_trigger, a.filter_trigger or "新上架")

    if not result.success:
        return f"""<div class="card card-error">
      <div class="card-header">
        <span class="idx">#{index}</span>
        <a href="{_e(a.html_url)}" target="_blank" class="repo-link">{_e(a.title)}</a>
        <span class="src-badge" style="color:#f85149;border-color:#f8514944">{region_flag} {_e(a.category)}</span>
      </div>
      <div class="meta">
        <span class="meta-item">{region_flag} {_e(a.region.upper())}</span>
        <span class="meta-item">指标{_e(a.filter_trigger)}: {_e(trigger_label)}</span>
      </div>
      <p class="err">⚠️ 分析失败: {_e(str(result.error))}</p>
    </div>"""

    gnc = _go_no_go_color(result.go_no_go)
    sc = _score_color(min(result.dark_horse_score // 2, 5))
    figma_short = result.figma_create_brief[:120] + "…" if len(result.figma_create_brief) > 120 else result.figma_create_brief

    return f"""<div class="card">
      <div class="card-header">
        <span class="idx">#{index}</span>
        <a href="{_e(a.html_url)}" target="_blank" class="repo-link">{_e(a.title)}</a>
        <span class="src-badge" style="color:{gnc};border-color:{gnc}44">{_e(result.go_no_go)}</span>
        <span class="score" style="background:{sc}22;color:{sc};border-color:{sc}55">🎯 {result.dark_horse_score}/10 · 克隆{result.clone_score}/5</span>
      </div>
      <div class="meta">
        <span class="meta-item">{region_flag} {_e(a.region.upper())}</span>
        <span class="badge">{_e(a.category)}</span>
        <span class="badge">指标{_e(a.filter_trigger)}: {_e(trigger_label)}</span>
        <span class="meta-item">{_e(a.price)}</span>
        {f'<span class="meta-item">性价比 {a.roi_score}/10 · 新颖 {a.novelty_score}/10</span>' if a.roi_score or a.novelty_score else ''}
        <span class="meta-item">🎨 美术: {_e(result.art_cost)}</span>
        <span class="meta-item">Flutter可行性: {result.flutter_feasibility}/5</span>
        {f'<span class="meta-item">置信度: {_e(result.confidence_level)}</span>' if result.confidence_level else ''}
        {f'<span class="meta-item">需人工复核</span>' if result.needs_manual_review else ''}
      </div>
      <p class="desc">{_e(result.product_what)}{f' · 入选：{_e(a.pick_reason)}' if a.pick_reason else ''}</p>
      <div class="fields">
        {_field("⚡ 核心吸金痛点", result.pain_point)}
        {_field("💹 套利空间算账", result.arbitrage_space)}
        {_field("⏱️ 回本周期（周）", result.payback_period_weeks)}
        {_field("🧮 评分拆解", result.scoring_breakdown)}
        {_field("🎯 CAC 估算", result.cac_estimate_range)}
        {_field("🔁 转化率估算", result.conversion_estimate_range)}
        {_field("💳 单价/ARPPU 假设", result.arppu_or_price_assumption)}
        {_field("⛔ 一票否决风险", result.deal_breakers)}
        {_field("📡 信号真伪", result.signal_validity)}
        {_field("✂️ 截流改进点", result.clone_edge)}
        {_field("🎨 Figma Create brief", figma_short)}
        {_field("🦋 Flutter 架构", result.flutter_arch)}
      </div>
    </div>"""


def _app_section(results: List[AppAnalysisResult], start_index: int) -> str:
    cards = "\n".join(_app_card(r, start_index + i) for i, r in enumerate(results))
    empty = """<p class="section-empty">本次未命中黑马阈值（指标A：7天内评论爆发；指标B：12小时内评论斜率飙升）。上新 App 已在上方列表持续跟踪。</p>"""
    body = cards if results else empty
    return f"""<section class="section">
    <div class="section-header">
      <h2>📱 App Store 黑马雷达</h2>
      <p class="section-sub">来源：评论斜率过滤 + DeepSeek 独立开发者视角逆向（仅分析命中指标 A/B 的 App）</p>
    </div>
    <div class="grid">{body}</div>
  </section>"""


def generate_html(
    results: List[AnalysisResult],
    app_results: List[AppAnalysisResult] = None,
    new_listings: List = None,
    new_listing_results: List[AppAnalysisResult] = None,
    app_pool_size: int = 0,
) -> str:
    if app_results is None:
        app_results = []
    if new_listing_results is None:
        new_listing_results = []
    if new_listings is None:
        new_listings = []
    today = beijing_today()
    total = len(results)
    success = sum(1 for r in results if r.success)

    trending = [r for r in results if r.project.source.startswith("trending")]
    search   = [r for r in results if r.project.source == "search"]

    sec_trending = _section(
        "🔥 GitHub Trending 热榜分析",
        "来源：GitHub Trending 日榜 / 周榜 / 月榜，综合去重后 AI 研判",
        trending, 1,
    )
    sec_search = _section(
        "🚀 近3天高速崛起",
        "来源：GitHub Search API — 近3天新建项目，按 Star 增速排序",
        search, len(trending) + 1,
    )
    sec_new = (
        _new_listings_section(new_listing_results, len(results) + 1, pool_size=app_pool_size)
        if new_listings is not None else ""
    )
    sec_app = (
        _app_section(app_results, len(results) + len(new_listing_results) + 1)
        if new_listings is not None else ""
    )

    app_stats = ""
    if new_listings is not None:
        app_new_ok = sum(1 for r in new_listing_results if r.success)
        app_horse_ok = sum(1 for r in app_results if r.success)
        app_stats = (
            f'<span>采集池 <strong>{app_pool_size}</strong> 个</span>'
            f'<span>顾问推送 <strong>{len(new_listing_results)}</strong> 个</span>'
            f'<span>黑马分析 <strong>{app_horse_ok}</strong> 个</span>'
        )

    return f"""<!DOCTYPE html>
<html lang="zh-CN">
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width,initial-scale=1.0">
  <title>GitHub 黑马技术雷达 — {today}</title>
  <style>
    *,*::before,*::after{{box-sizing:border-box;margin:0;padding:0}}
    body{{font-family:-apple-system,BlinkMacSystemFont,"Segoe UI",Helvetica,Arial,sans-serif;
         background:#0d1117;color:#c9d1d9;line-height:1.65}}
    a{{color:#58a6ff;text-decoration:none}}
    a:hover{{text-decoration:underline}}

    .site-header{{background:#161b22;border-bottom:1px solid #30363d;padding:28px 32px}}
    .site-header h1{{font-size:1.6rem;font-weight:700;color:#f0f6fc}}
    .site-header h1 em{{color:#f0883e;font-style:normal}}
    .hm{{margin-top:10px;color:#8b949e;font-size:.875rem;display:flex;gap:20px;flex-wrap:wrap}}
    .hm strong{{color:#c9d1d9}}

    .container{{max-width:1500px;margin:0 auto;padding:32px 16px}}

    .section{{margin-bottom:48px}}
    .section-header{{margin-bottom:20px;padding-bottom:12px;border-bottom:1px solid #21262d}}
    .section-header h2{{font-size:1.2rem;font-weight:700;color:#f0f6fc}}
    .section-sub{{color:#8b949e;font-size:.85rem;margin-top:4px}}

    .grid{{display:grid;grid-template-columns:repeat(auto-fill,minmax(440px,1fr));gap:16px}}

    .card{{background:#161b22;border:1px solid #30363d;border-radius:10px;padding:20px;
           transition:border-color .15s,box-shadow .15s}}
    .card:hover{{border-color:#58a6ff55;box-shadow:0 0 0 1px #58a6ff22}}
    .card-error{{border-color:#f8514933}}

    .card-header{{display:flex;align-items:center;gap:7px;flex-wrap:wrap;margin-bottom:10px}}
    .idx{{color:#484f58;font-size:.75rem;font-weight:600;flex-shrink:0}}
    .repo-link{{font-size:.95rem;font-weight:600;color:#58a6ff;flex:1;min-width:0;
                white-space:nowrap;overflow:hidden;text-overflow:ellipsis}}
    .src-badge{{font-size:.7rem;border:1px solid;border-radius:20px;padding:1px 8px;
                white-space:nowrap;flex-shrink:0}}
    .score{{font-size:.72rem;border:1px solid;border-radius:20px;padding:2px 9px;
            white-space:nowrap;flex-shrink:0}}

    .meta{{display:flex;gap:8px;flex-wrap:wrap;margin-bottom:10px;align-items:center}}
    .badge{{background:#21262d;color:#8b949e;border:1px solid #30363d;
            border-radius:4px;padding:1px 7px;font-size:.73rem}}
    .meta-item{{color:#8b949e;font-size:.78rem}}

    .desc{{color:#8b949e;font-size:.83rem;margin-bottom:14px;
           display:-webkit-box;-webkit-line-clamp:2;-webkit-box-orient:vertical;overflow:hidden}}

    .fields{{display:flex;flex-direction:column;gap:9px}}
    .field{{display:grid;grid-template-columns:130px 1fr;gap:8px;font-size:.83rem;
            padding:8px 10px;background:#0d1117;border-radius:6px}}
    .fl{{color:#8b949e;font-weight:500;padding-top:1px}}
    .fv{{color:#c9d1d9}}

    .err{{color:#f85149;font-size:.83rem;margin-top:8px}}
    .section-empty{{color:#8b949e;font-size:.9rem;padding:16px 20px;background:#161b22;
                    border:1px dashed #30363d;border-radius:10px}}
    .card-watch{{border-color:#21262d}}

    .site-footer{{text-align:center;padding:32px;color:#484f58;font-size:.78rem;
                  border-top:1px solid #21262d;margin-top:16px}}

    @media(max-width:600px){{
      .grid{{grid-template-columns:1fr}}
      .field{{grid-template-columns:1fr}}
      .fl{{margin-bottom:2px}}
    }}
  </style>
</head>
<body>
  <header class="site-header">
    <h1>🎯 GitHub 黑马技术雷达 <em>{today}</em></h1>
    <div class="hm">
      <span>采样 <strong>{total}</strong> 个项目</span>
      <span>成功分析 <strong>{success}</strong> 个</span>
      <span>Trending 热榜 <strong>{len(trending)}</strong> 个</span>
      <span>近期新星 <strong>{len(search)}</strong> 个</span>
      {app_stats}
    </div>
  </header>
  <main class="container">
    {sec_trending}
    {sec_search}
    {sec_new}
    {sec_app}
  </main>
  <footer class="site-footer">
    ⚠️ 本日报仅供技术研判参考，不构成任何投资建议。每周一北京时间 09:00 自动更新。
  </footer>
</body>
</html>"""


def _md_one_line(text: str) -> str:
    return str(text).replace("\r\n", "\n").replace("\n", " ").strip()


def _md_field(label: str, value: str) -> str:
    v = _md_one_line(value)
    if not v or v == "推测依据不足":
        return ""
    return f"- **{label}**：{v}\n"


def _md_github_card(result: AnalysisResult, index: int) -> str:
    p = result.project
    icon, label, _ = _SOURCE_LABEL.get(p.source, ("·", p.source, "#8b949e"))
    lang = f" · {p.language}" if p.language else ""
    created = f" · 创建 {p.created_at[:10]}" if p.created_at else ""

    if not result.success:
        return (
            f"### #{index} [{p.full_name}]({p.html_url})\n\n"
            f"{icon} {label}{lang} · ⭐ {p.stargazers_count:,}{created}\n\n"
            f"> ⚠️ 分析失败: {result.error}\n"
        )

    fields = "".join(
        _md_field(k, v)
        for k, v in [
            ("生产力置换", result.productivity_replacement),
            ("技术壁垒", result.architecture_core),
            ("生态卡位", result.glue_cement_grade),
            ("TPD 变现路径", result.tpd_potential),
            ("变现切入点", result.monetization_angle),
            ("可落地产品形态", result.product_form),
            ("巨头背刺风险", result.backstab_risk),
        ]
    )
    return (
        f"### #{index} [{p.full_name}]({p.html_url})\n\n"
        f"{icon} {label}{lang} · ⭐ {p.stargazers_count:,}{created} · "
        f"{'★' * result.dark_horse_score}{'☆' * (5 - result.dark_horse_score)} {result.dark_horse_score}/5\n\n"
        f"{_md_one_line(p.description)}\n\n"
        f"{fields}\n"
    )


def _md_app_card(result: AppAnalysisResult, index: int) -> str:
    a = result.app
    region_flag = {"us": "🇺🇸", "jp": "🇯🇵"}.get(a.region, a.region.upper())
    trigger_label = {
        "A": "冷启动爆发", "B": "斜率飙升", "上新": "新上架",
    }.get(a.filter_trigger, a.filter_trigger or "新上架")

    if not result.success:
        return (
            f"### #{index} [{a.title}]({a.html_url})\n\n"
            f"{region_flag} {a.category} · 指标{a.filter_trigger}: {trigger_label}\n\n"
            f"> ⚠️ 分析失败: {result.error}\n"
        )

    pick = f" · 入选：{_md_one_line(a.pick_reason)}" if a.pick_reason else ""
    roi = (
        f" · 性价比 {a.roi_score}/10 · 新颖 {a.novelty_score}/10"
        if a.roi_score or a.novelty_score else ""
    )
    fields = "".join(
        _md_field(k, v)
        for k, v in [
            ("核心吸金痛点", result.pain_point),
            ("套利空间算账", result.arbitrage_space),
            ("回本周期（周）", result.payback_period_weeks),
            ("评分拆解", result.scoring_breakdown),
            ("CAC 估算", result.cac_estimate_range),
            ("转化率估算", result.conversion_estimate_range),
            ("单价/ARPPU 假设", result.arppu_or_price_assumption),
            ("一票否决风险", result.deal_breakers),
            ("信号真伪", result.signal_validity),
            ("截流改进点", result.clone_edge),
            ("Figma Create brief", result.figma_create_brief),
            ("Flutter 架构", result.flutter_arch),
        ]
    )
    return (
        f"### #{index} [{a.title}]({a.html_url})\n\n"
        f"**{result.go_no_go}** · 🎯 {result.dark_horse_score}/10 · 克隆 {result.clone_score}/5\n\n"
        f"{region_flag} {a.region.upper()} · {a.category} · 指标{a.filter_trigger}: {trigger_label}"
        f" · {a.price}{roi} · 美术 {result.art_cost} · Flutter {result.flutter_feasibility}/5"
        f"{f' · 置信度 {result.confidence_level}' if result.confidence_level else ''}"
        f"{' · ⚠️ 需人工复核' if result.needs_manual_review else ''}\n\n"
        f"{_md_one_line(result.product_what)}{pick}\n\n"
        f"{fields}\n"
    )


def generate_markdown(
    results: List[AnalysisResult],
    app_results: Optional[List[AppAnalysisResult]] = None,
    new_listings: Optional[List] = None,
    new_listing_results: Optional[List[AppAnalysisResult]] = None,
    app_pool_size: int = 0,
    date: Optional[str] = None,
) -> str:
    if app_results is None:
        app_results = []
    if new_listing_results is None:
        new_listing_results = []
    include_app = new_listings is not None
    if new_listings is None:
        new_listings = []

    today = date or beijing_today()
    total = len(results)
    success = sum(1 for r in results if r.success)
    trending = [r for r in results if r.project.source.startswith("trending")]
    search = [r for r in results if r.project.source == "search"]
    app_horse_ok = sum(1 for r in app_results if r.success)

    fm = [
        "---",
        f"date: {today}",
        "tags:",
        "  - 黑马雷达",
        "  - 日报",
        "type: daily-report",
        f"github_total: {total}",
        f"github_success: {success}",
        f"github_trending: {len(trending)}",
        f"github_search: {len(search)}",
    ]
    if include_app:
        fm.extend([
            f"app_pool: {app_pool_size}",
            f"app_pushed: {len(new_listing_results)}",
            f"app_black_horse: {app_horse_ok}",
        ])
    fm.append("---")

    lines = [
        "\n".join(fm) + "\n",
        f"# 黑马雷达日报 — {today}\n",
        f"> 采样 **{total}** 个项目，成功分析 **{success}** 个"
        f" · Trending **{len(trending)}** · 近期新星 **{len(search)}**",
    ]
    if include_app:
        lines[-1] += (
            f" · App 采集池 **{app_pool_size}**"
            f" · 顾问推送 **{len(new_listing_results)}**"
            f" · 黑马分析 **{app_horse_ok}**"
        )
    lines.append("\n---\n")

    if trending:
        lines.append("\n## 🔥 GitHub Trending 热榜分析\n")
        lines.append("*来源：GitHub Trending 日榜 / 周榜 / 月榜，综合去重后 AI 研判*\n")
        for i, r in enumerate(trending, 1):
            lines.append(_md_github_card(r, i))

    if search:
        lines.append("\n## 🚀 近3天高速崛起\n")
        lines.append("*来源：GitHub Search API — 近3天新建项目，按 Star 增速排序*\n")
        for i, r in enumerate(search, len(trending) + 1):
            lines.append(_md_github_card(r, i))

    if include_app:
        pool_note = f"从 **{app_pool_size}** 个" if app_pool_size else "从采集池"
        rss_limit = os.getenv("APP_RSS_LIMIT", "100")
        lines.append("\n## 🆕 App Store 上新监控\n")
        lines.append(
            f"*来源：US/JP × 4分类 newapplications RSS（每类最多 {rss_limit} 条），"
            f"顾问按性价比+新颖性筛选，{pool_note} 推送 Top **{len(new_listing_results)}** 并完成深入分析*\n"
        )
        if new_listing_results:
            base = len(results) + 1
            for i, r in enumerate(new_listing_results, base):
                lines.append(_md_app_card(r, i))
        else:
            lines.append("> 今日 RSS 未发现新上架 App，快照持续跟踪中。\n")

        lines.append("\n## 📱 App Store 黑马雷达\n")
        lines.append(
            "*来源：评论斜率过滤 + DeepSeek 独立开发者视角逆向（仅分析命中指标 A/B 的 App）*\n"
        )
        if app_results:
            base = len(results) + len(new_listing_results) + 1
            for i, r in enumerate(app_results, base):
                lines.append(_md_app_card(r, i))
        else:
            lines.append(
                "> 本次未命中黑马阈值（指标A：7天内评论爆发；指标B：12小时内评论斜率飙升）。"
                "上新 App 已在上方列表持续跟踪。\n"
            )

    lines.append("\n---\n\n*⚠️ 本日报仅供技术研判参考，不构成任何投资建议。*\n")
    return "".join(lines)


_INDEX_START = "<!-- radar-index -->"
_INDEX_END = "<!-- /radar-index -->"
_VAULT_HOME = "首页.md"


def _ensure_vault_scaffold() -> None:
    """Create Obsidian vault scaffold once (safe to re-run)."""
    ARCHIVE_DIR.mkdir(parents=True, exist_ok=True)
    gitignore = ARCHIVE_DIR / ".gitignore"
    if not gitignore.exists():
        gitignore.write_text(
            "# Obsidian — 仅忽略本机状态，配置可入库\n"
            ".obsidian/workspace.json\n"
            ".obsidian/workspace-mobile.json\n"
            ".obsidian/plugins/\n"
            ".obsidian/themes/\n"
            ".trash/\n",
            encoding="utf-8",
        )

    obsidian = ARCHIVE_DIR / ".obsidian"
    obsidian.mkdir(parents=True, exist_ok=True)
    daily = obsidian / "daily-notes.json"
    if not daily.exists():
        daily.write_text(
            '{\n  "format": "YYYY-MM-DD",\n  "folder": "",\n  "template": ""\n}\n',
            encoding="utf-8",
        )
    app_json = obsidian / "app.json"
    if not app_json.exists():
        app_json.write_text(
            '{\n  "readableLineLength": 120,\n  "showFrontmatter": true\n}\n',
            encoding="utf-8",
        )

    home = ARCHIVE_DIR / _VAULT_HOME
    if not home.exists():
        home.write_text(
            "# 黑马雷达知识库\n\n"
            "在 Obsidian 中 **打开本文件夹**（`knowledge/`）作为仓库即可。\n\n"
            "雷达每次跑完会自动写入 `YYYY-MM-DD.md` 日报，并更新下方索引。\n\n"
            "## 日报索引\n\n"
            f"{_INDEX_START}\n"
            f"{_INDEX_END}\n",
            encoding="utf-8",
        )


def _update_vault_index(day: str) -> None:
    """Prepend today's note link to 首页.md (Obsidian wikilink)."""
    home = ARCHIVE_DIR / _VAULT_HOME
    if not home.exists():
        _ensure_vault_scaffold()
    text = home.read_text(encoding="utf-8")
    link = f"- [[{day}]]"
    if _INDEX_START not in text or _INDEX_END not in text:
        text += f"\n## 日报索引\n\n{_INDEX_START}\n{_INDEX_END}\n"
    start = text.index(_INDEX_START) + len(_INDEX_START)
    end = text.index(_INDEX_END)
    block = text[start:end]
    if f"[[{day}]]" in block:
        return
    insertion = f"\n{link}" if block.strip() else f"\n{link}\n"
    text = text[:start] + insertion + block + text[end:]
    home.write_text(text, encoding="utf-8")


def archive_report(
    results: List[AnalysisResult],
    app_results: Optional[List[AppAnalysisResult]] = None,
    new_listings: Optional[List] = None,
    new_listing_results: Optional[List[AppAnalysisResult]] = None,
    app_pool_size: int = 0,
    date: Optional[str] = None,
) -> Path:
    """Write daily Markdown archive to knowledge/YYYY-MM-DD.md (Obsidian vault)."""
    if app_results is None:
        app_results = []
    if new_listing_results is None:
        new_listing_results = []
    day = date or beijing_today()
    _ensure_vault_scaffold()
    out = ARCHIVE_DIR / f"{day}.md"
    out.write_text(
        generate_markdown(
            results, app_results, new_listings, new_listing_results, app_pool_size,
            date=day,
        ),
        encoding="utf-8",
    )
    _update_vault_index(day)
    logger.info("Markdown archive written to %s (%d bytes)", out, out.stat().st_size)
    return out


def write_report(
    results: List[AnalysisResult],
    app_results: List[AppAnalysisResult] = None,
    new_listings: List = None,
    new_listing_results: List[AppAnalysisResult] = None,
    app_pool_size: int = 0,
) -> Path:
    if app_results is None:
        app_results = []
    if new_listings is None:
        new_listings = None
    if new_listing_results is None:
        new_listing_results = []
    DOCS_DIR.mkdir(exist_ok=True)
    out = DOCS_DIR / "index.html"
    out.write_text(
        generate_html(
            results, app_results, new_listings, new_listing_results, app_pool_size,
        ),
        encoding="utf-8",
    )
    logger.info("HTML report written to %s (%d bytes)", out, out.stat().st_size)
    archive_report(
        results, app_results, new_listings, new_listing_results, app_pool_size,
    )
    return out
