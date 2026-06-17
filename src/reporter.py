import html
from pathlib import Path
from typing import List

from models import AnalysisResult
from utils import setup_logger, beijing_today

logger = setup_logger(__name__)

DOCS_DIR = Path(__file__).parent.parent / "docs"

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
    ⚠️ 本日报仅供技术研判参考，不构成任何投资建议。每日北京时间 09:00 自动更新。
  </footer>
</body>
</html>"""


def write_report(results: List[AnalysisResult]) -> Path:
    DOCS_DIR.mkdir(exist_ok=True)
    out = DOCS_DIR / "index.html"
    out.write_text(generate_html(results), encoding="utf-8")
    logger.info("HTML report written to %s (%d bytes)", out, out.stat().st_size)
    return out
