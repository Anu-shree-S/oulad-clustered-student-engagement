"""Small in-session intervention workflow for the conference prototype."""

from __future__ import annotations

from datetime import datetime, timezone
import uuid
import streamlit as st

KEY = "trackwise_interventions"


def _store() -> list[dict]:
    if KEY not in st.session_state:
        st.session_state[KEY] = []
    return st.session_state[KEY]


def create_intervention(*, student_id: int, learner: str, module: str, presentation: str,
                        quarter: str, action: str, note: str = "", owner: str = "Instructor") -> dict:
    item = {
        "id": str(uuid.uuid4())[:8],
        "student_id": int(student_id),
        "learner": learner,
        "module": module,
        "presentation": presentation,
        "quarter": quarter,
        "action": action,
        "note": note,
        "owner": owner,
        "status": "Planned",
        "created_at": datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC"),
    }
    _store().append(item)
    return item


def update_status(intervention_id: str, status: str) -> None:
    for item in _store():
        if item["id"] == intervention_id:
            item["status"] = status
            return


def list_interventions(*, module: str | None = None, presentation: str | None = None,
                       student_id: int | None = None) -> list[dict]:
    items = list(_store())
    if module is not None:
        items = [i for i in items if i["module"] == module]
    if presentation is not None:
        items = [i for i in items if i["presentation"] == presentation]
    if student_id is not None:
        items = [i for i in items if i["student_id"] == int(student_id)]
    return list(reversed(items))
