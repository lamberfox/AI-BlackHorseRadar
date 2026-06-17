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


@dataclass
class AnalysisResult:
    project: Project
    productivity_replacement: str = ""
    architecture_core: str = ""
    glue_cement_grade: str = ""
    tpd_potential: str = ""
    backstab_risk: str = ""
    dark_horse_score: int = 0
    error: Optional[str] = None

    @property
    def success(self) -> bool:
        return self.error is None
