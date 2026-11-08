"""Optional local AI coach powered by Ollama, with a deterministic free fallback."""
from __future__ import annotations
import os
import requests

SYSTEM_GUIDANCE = (
    "You are FitTrack's supportive fitness education assistant. Give practical, general, "
    "non-medical guidance. Never diagnose, prescribe treatment, recommend extreme dieting, "
    "or promise specific weight-loss results. Be cautious with missing data. Encourage users "
    "with medical conditions, injuries, pregnancy, eating-disorder history, or persistent "
    "symptoms to consult a qualified healthcare professional. Keep the response concise."
)

def _fallback(context: str, question: str) -> str:
    q = question.lower()
    notes = []
    if "sleep" in q:
        notes.append("Track sleep consistently and keep a regular sleep and wake time. Most adults need around 7–9 hours, though individual needs vary.")
    if any(term in q for term in ("steps", "walk", "walking")):
        notes.append("Build walking volume gradually and choose a weekly target you can repeat. Consistency matters more than chasing one very high step count.")
    if any(term in q for term in ("weight", "fat", "calorie")):
        notes.append("Use calorie estimates as starting points, not exact measurements. Review trends over several weeks rather than reacting to daily weight changes.")
    if any(term in q for term in ("water", "hydration")):
        notes.append("Track your fluid intake and consider heat, activity and thirst. Hydration needs vary, so avoid treating one fixed number as right for everyone.")
    if not notes:
        notes.append("Set one realistic weekly target, record your activity consistently, and adjust based on how you feel and the trend in your records.")
    return "\n\n".join(notes) + "\n\nThis is general educational information, not medical advice.\n\nContext used:\n" + context[:1200]

def ask_fittrack_ai(question: str, context: str) -> tuple[str, str]:
    """Return answer and provider. Ollama runs locally; fallback needs no API key."""
    base_url = os.getenv("OLLAMA_HOST", "http://localhost:11434").rstrip("/")
    model = os.getenv("OLLAMA_MODEL", "llama3.2:3b")
    prompt = (
        f"{SYSTEM_GUIDANCE}\n\nUser fitness context (unverified self-reported data):\n{context}"
        f"\n\nUser question: {question}\n\nGive practical, cautious suggestions."
    )
    try:
        response = requests.post(
            f"{base_url}/api/generate",
            json={"model": model, "prompt": prompt, "stream": False},
            timeout=90,
        )
        response.raise_for_status()
        answer = response.json().get("response", "").strip()
        if answer:
            return answer, f"Local Ollama model: {model}"
    except (requests.RequestException, ValueError, KeyError):
        pass
    return _fallback(context, question), "Built-in offline guidance (Ollama unavailable)"
