import os
from pathlib import Path
from typing import List

from models import AnalysisResult
from utils import setup_logger, beijing_today

logger = setup_logger(__name__)

DOCS_DIR = Path(__file__).parent.parent / "docs"


def _score_color(score: int) -> str:
    return {5: "#ffd700", 4: "#f0883e", 3: "#3fb950", 2: "#8b949e", 1: "#6e7681"}.get(score, "#6e7681")


def _score_stars(score: int) -> str:
    return "★" * score + "☆" * (5 - score)


def _card_html(result: AnalysisResult, index: int) -> str:
    p = result.project
    score_color = _score_color(result.dark_horse_score)
    lang_badge = f'<span class="badge">{p.language}</span>' if p.language else ""
    created = f'<span class="meta-item">创建: {p.created_at[:10]}</span>' if p.created_at else ""

    if not result.success:
        return f"""
        <div class="card card-error">
          <div class="card-header">
            <span class="card-index">#{index}</span>
            <a href="{p.html_url}" target="_blank" class="card-title">{p.full_name}</a>
          </div>
          <div class="card-meta">{lang_badge}<span class="meta-item">⭐ {p.stargazers_count:,}</span>{created}</div>
          <p class="error-msg">⚠️ 分析失败: {result.error}</p>
        </div>"""

    return f"""
        <div class="card">
          <div class="card-header">
            <span class="card-index">#{index}</span>
            <a href="{p.html_url}" target="_blank" class="card-title">{p.full_name}</a>
            <span class="score-badge" style="background:{score_color}22;color:{score_color};border-color:{score_color}44">
              {_score_stars(result.dark_horse_score)} {result.dark_horse_score}/5
            </span>
          </div>
          <div class="card-meta">
            {lang_badge}
            <span class="meta-item">⭐ {p.stargazers_count:,}</span>
            {created}
          </div>
          <p class="description">{p.description}</p>
          <div class="fields">
            <div class="field"><span class="field-label">⚡ 生产力置换</span><span class="field-value">{result.productivity_replacement}</span></div>
            <div class="field"><span class="field-label">🛠️ 底层工程解密</span><span class="field-value">{result.architecture_core}</span></div>
            <div class="field"><span class="field-label">🧬 生态位定级</span><span class="field-value">{result.glue_cement_grade}</span></div>
            <div class="field"><span class="field-label">💰 TPD 变现潜力</span><span class="field-value">{result.tpd_potential}</span></div>
            <div class="field"><span class="field-label">🚨 巨头背刺风险</span><span class="field-value">{result.backstab_risk}</span></div>
          </div>
        </div>"""


def generate_html(results: List[AnalysisResult]) -> str:
    today = beijing_today()
    total = len(results)
    success = sum(1 for r in results if r.success)
    cards = "\n".join(_card_html(r, i + 1) for i, r in enumerate(results))

    return f"""<!DOCTYPE html>
<html lang="zh-CN">
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width,initial-scale=1.0">
  <title>GitHub 黑马技术雷达 — {today}</title>
  <style>
    *, *::before, *::after {{ box-sizing: border-box; margin: 0; padding: 0; }}
    body {{ font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Helvetica, Arial, sans-serif;
            background: #0d1117; color: #c9d1d9; line-height: 1.6; }}
    a {{ color: #58a6ff; text-decoration: none; }}
    a:hover {{ text-decoration: underline; }}

    .site-header {{ background: #161b22; border-bottom: 1px solid #30363d; padding: 24px 32px; }}
    .site-header h1 {{ font-size: 1.5rem; font-weight: 700; color: #f0f6fc; }}
    .site-header h1 span {{ color: #f0883e; }}
    .header-meta {{ margin-top: 8px; color: #8b949e; font-size: 0.875rem; }}
    .stat {{ display: inline-block; margin-right: 20px; }}
    .stat strong {{ color: #c9d1d9; }}

    .container {{ max-width: 1400px; margin: 0 auto; padding: 24px 16px; }}
    .grid {{ display: grid; grid-template-columns: repeat(auto-fill, minmax(420px, 1fr)); gap: 16px; }}

    .card {{ background: #161b22; border: 1px solid #30363d; border-radius: 8px;
             padding: 20px; transition: border-color .15s; }}
    .card:hover {{ border-color: #58a6ff44; }}
    .card-error {{ border-color: #f8514944; }}

    .card-header {{ display: flex; align-items: baseline; gap: 8px; flex-wrap: wrap; margin-bottom: 10px; }}
    .card-index {{ color: #8b949e; font-size: 0.8rem; font-weight: 600; flex-shrink: 0; }}
    .card-title {{ font-size: 1rem; font-weight: 600; color: #58a6ff; flex: 1; min-width: 0;
                   white-space: nowrap; overflow: hidden; text-overflow: ellipsis; }}
    .score-badge {{ font-size: 0.75rem; border: 1px solid; border-radius: 20px;
                    padding: 2px 10px; white-space: nowrap; flex-shrink: 0; }}

    .card-meta {{ display: flex; gap: 8px; flex-wrap: wrap; margin-bottom: 10px; align-items: center; }}
    .badge {{ background: #21262d; color: #8b949e; border: 1px solid #30363d;
              border-radius: 4px; padding: 1px 8px; font-size: 0.75rem; }}
    .meta-item {{ color: #8b949e; font-size: 0.8rem; }}

    .description {{ color: #8b949e; font-size: 0.85rem; margin-bottom: 14px;
                    display: -webkit-box; -webkit-line-clamp: 2; -webkit-box-orient: vertical; overflow: hidden; }}

    .fields {{ display: flex; flex-direction: column; gap: 10px; }}
    .field {{ display: grid; grid-template-columns: 140px 1fr; gap: 8px; font-size: 0.85rem; }}
    .field-label {{ color: #8b949e; font-weight: 500; flex-shrink: 0; }}
    .field-value {{ color: #c9d1d9; }}

    .error-msg {{ color: #f85149; font-size: 0.85rem; margin-top: 8px; }}

    .site-footer {{ text-align: center; padding: 32px; color: #484f58; font-size: 0.8rem; border-top: 1px solid #21262d; margin-top: 32px; }}

    @media (max-width: 600px) {{
      .grid {{ grid-template-columns: 1fr; }}
      .field {{ grid-template-columns: 1fr; }}
      .field-label {{ margin-bottom: 2px; }}
    }}
  </style>
</head>
<body>
  <header class="site-header">
    <h1>🎯 GitHub 黑马技术雷达 <span>{today}</span></h1>
    <div class="header-meta">
      <span class="stat">采样 <strong>{total}</strong> 个项目</span>
      <span class="stat">成功分析 <strong>{success}</strong> 个</span>
      <span class="stat">来源: GitHub Search + Trending 日/周/月榜</span>
    </div>
  </header>
  <main class="container">
    <div class="grid">
{cards}
    </div>
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
    logger.info("HTML report written to %s", out)
    return out
