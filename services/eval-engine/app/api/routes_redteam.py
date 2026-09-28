from fastapi import APIRouter

from app.config import settings
from app.evaluators.redteam.prompt_injection import run_promptfoo_redteam

router = APIRouter(prefix="/redteam", tags=["redteam"])


@router.post("/run")
def run_redteam() -> dict:
    findings = run_promptfoo_redteam(settings.redteam_promptfoo_config)
    return {
        "total": len(findings),
        "flagged": sum(1 for f in findings if f.flagged),
        "findings": [f.model_dump(mode="json") for f in findings],
    }
