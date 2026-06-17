import os
import json
import requests

from models import Project, AnalysisResult
from utils import setup_logger, retry
from prompts import get as get_prompt

logger = setup_logger(__name__)

DEEPSEEK_API = "https://api.deepseek.com/v1/chat/completions"


@retry(max_attempts=2, delay=5.0, exceptions=(requests.RequestException,))
def _call_deepseek(prompt: str) -> str:
    api_key = os.getenv("DEEPSEEK_API_KEY", "")
    if not api_key:
        raise ValueError("DEEPSEEK_API_KEY not set")

    resp = requests.post(
        DEEPSEEK_API,
        headers={"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"},
        json={
            "model": "deepseek-chat",
            "messages": [
                {"role": "system", "content": get_prompt("SYSTEM_PROMPT")},
                {"role": "user", "content": prompt},
            ],
            "temperature": 0.3,
            "max_tokens": 600,
            "response_format": {"type": "json_object"},
        },
        timeout=30,
    )
    resp.raise_for_status()
    return resp.json()["choices"][0]["message"]["content"]


def analyze_project(project: Project) -> AnalysisResult:
    prompt = get_prompt("USER_PROMPT").format(
        full_name=project.full_name,
        description=project.description or "（无描述）",
        language=project.language or "未知",
        stars=project.stargazers_count,
        created_at=project.created_at,
        html_url=project.html_url,
        readme=project.readme_excerpt or "（无 README）",
    )

    try:
        raw = _call_deepseek(prompt)
        data = json.loads(raw)
        return AnalysisResult(
            project=project,
            productivity_replacement=data.get("productivity_replacement", "推测依据不足"),
            architecture_core=data.get("architecture_core", "推测依据不足"),
            glue_cement_grade=data.get("glue_cement_grade", "推测依据不足"),
            tpd_potential=data.get("tpd_potential", "推测依据不足"),
            backstab_risk=data.get("backstab_risk", "推测依据不足"),
            dark_horse_score=int(data.get("dark_horse_score", 0)),
        )
    except Exception as e:
        logger.error("Analysis failed for %s: %s", project.full_name, e)
        return AnalysisResult(project=project, error=str(e))
