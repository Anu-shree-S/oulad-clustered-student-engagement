"""Central, fail-closed permissions for the historical-data demonstration.

These checks separate demo personas; they are not production authentication.
Raw dataset keys stay on the server and remain unchanged for analytical joins.
"""

from collections.abc import Mapping

STUDENT = "student"
INSTRUCTOR = "instructor"
ADMIN = "admin"
ROLES = {STUDENT, INSTRUCTOR, ADMIN}


def _student_key(value):
    """Normalise integer dataset keys without accepting missing or boolean IDs."""
    if value is None or isinstance(value, bool):
        return None
    try:
        key = int(value)
        return key if str(value).strip() == str(key) and key >= 0 else None
    except (TypeError, ValueError, OverflowError):
        return None


def assigned_modules(user) -> list[tuple[str, str]]:
    """Read well-formed assignments from a persona, never from widget state."""
    if not isinstance(user, Mapping):
        return []
    assignments = user.get("modules", [])
    if not isinstance(assignments, (list, tuple)):
        return []
    return sorted({tuple(pair) for pair in assignments
                   if isinstance(pair, (tuple, list)) and len(pair) == 2
                   and all(isinstance(value, str) and value for value in pair)})


def can_access_module(user, module, presentation) -> bool:
    """Allow own enrolment, assigned teaching cohorts, or admin aggregates."""
    if not isinstance(user, Mapping) or not module or not presentation:
        return False
    role = user.get("role")
    if role == STUDENT:
        return (module, presentation) == (user.get("module"), user.get("presentation"))
    if role == INSTRUCTOR:
        return (module, presentation) in assigned_modules(user)
    return role == ADMIN


def can_access_student(user, student_id, module=None, presentation=None,
                       *, student_info=None) -> bool:
    """Check learner identity and actual enrolment, including instructor scope.

    Callers may pass the server-loaded studentInfo frame to avoid a repeated read.
    Instructor access requires BOTH an assignment and a matching enrolment row.
    Administrators cannot inspect individual learners in this conference version.
    """
    if not isinstance(user, Mapping) or user.get("role") not in {STUDENT, INSTRUCTOR}:
        return False
    key = _student_key(student_id)
    if key is None:
        return False
    if user.get("role") == STUDENT:
        if key != _student_key(user.get("student_id")):
            return False
        module = user.get("module") if module is None else module
        presentation = user.get("presentation") if presentation is None else presentation
    if not can_access_module(user, module, presentation):
        return False
    if student_info is None:
        from services.data_service import DataUnavailable, load_student_info
        try:
            student_info = load_student_info()
        except DataUnavailable:
            return False
    required = {"id_student", "code_module", "code_presentation"}
    if student_info is None or not required.issubset(student_info.columns):
        return False
    return bool(((student_info["id_student"] == key)
                 & (student_info["code_module"] == module)
                 & (student_info["code_presentation"] == presentation)).any())


def require_role(user, expected_role: str) -> bool:
    """Stop gracefully unless the render argument matches the active session."""
    import streamlit as st

    current = st.session_state.get("user")
    if not isinstance(current, Mapping):
        st.info("Please sign in from the TrackWise demo login to continue.")
        st.stop()
    if (expected_role not in ROLES or current.get("role") != expected_role
            or not isinstance(user, Mapping) or dict(user) != dict(current)):
        st.error("This page is not available to your signed-in role.")
        st.stop()
    return True
