from dataclasses import dataclass
from typing import Optional


@dataclass
class Project:
    full_name: str
    html_url: str
    description: str
    language: Optional[str]
    stargazers_count: int
    owner_login: str
    created_at: str
    readme_excerpt: str = ""
    source: str = "search"   # "search" | "trending_daily" | "trending_weekly" | "trending_monthly"


@dataclass
class AnalysisResult:
    project: Project
    productivity_replacement: str = ""
    architecture_core: str = ""
    glue_cement_grade: str = ""
    tpd_potential: str = ""
    backstab_risk: str = ""
    monetization_angle: str = ""
    product_form: str = ""
    dark_horse_score: int = 0
    error: Optional[str] = None

    @property
    def success(self) -> bool:
        return self.error is None


# ── App Store models ──────────────────────────────────────────────────────────

@dataclass
class AppProject:
    app_id: str
    title: str
    region: str          # "us" | "jp"
    category: str        # e.g. "Puzzle", "Utilities"
    description: str
    price: str           # "Free" or "$X.XX"
    developer: str
    html_url: str
    filter_trigger: str  # "A" | "B"
    release_date: str = ""  # ISO date from RSS, e.g. "2026-06-20T00:00:00-07:00"
    reviews: list = None  # raw review texts (up to 30), populated by client
    total_reviews: int = 0       # from snapshot / review fetch
    five_star_reviews: int = 0
    first_seen: str = ""         # when we first tracked this app
    roi_score: int = 0           # advisor pick: 性价比
    novelty_score: int = 0       # advisor pick: 新颖性
    pick_reason: str = ""        # advisor pick: 入选理由

    def __post_init__(self):
        if self.reviews is None:
            self.reviews = []


@dataclass
class AppAnalysisResult:
    app: AppProject
    product_what: str = ""
    go_no_go: str = ""
    dark_horse_score: int = 0
    clone_score: int = 0
    signal_validity: str = ""
    intercept_window: str = ""
    pain_point: str = ""
    commercial_critique: str = ""
    figma_create_brief: str = ""
    flutter_arch: str = ""
    clone_edge: str = ""
    art_cost: str = ""
    flutter_feasibility: int = 0
    # legacy alias — old reports / model output
    v0_prompt: str = ""
    error: Optional[str] = None

    @property
    def success(self) -> bool:
        return self.error is None
