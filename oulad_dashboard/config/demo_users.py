"""Local TrackWise authentication and role configuration.

This module provides prototype authentication for the local/conference
application. It is NOT production authentication and should later be
replaced by university SSO/OAuth or another managed identity provider.
"""

from copy import deepcopy
import hashlib
import hmac

import pandas as pd

from config.paths import RECOMMENDATION_DIR


DEFAULT_MODULE = "BBB"
DEFAULT_PRESENTATION = "2014J"
DEFAULT_INSTRUCTOR_COHORT_COUNT = 1


# ---------------------------------------------------------------------
# LOCAL PROTOTYPE ACCOUNTS
# ---------------------------------------------------------------------
#
# Passwords are stored as SHA-256 hashes rather than plain text.
#
# Default credentials:
#
# Student:
#   any valid OULAD student ID can be used as both username and password
#   example: username 6516 / password 6516
#   fallback generic account: student / TrackWiseStudent@2026
#
# Instructor:
#   username: instructor
#   password: TrackWiseInstructor@2026
#
# Administrator:
#   username: admin
#   password: TrackWiseAdmin@2026
#
# IMPORTANT:
# This is suitable only for a local MSc prototype / conference demo.
# Do not use this authentication approach for production deployment.
# ---------------------------------------------------------------------

USER_ACCOUNTS = {
    "student": {
        "username": "student",
        "password_hash": (
            "233c18be5efb7ce200d707435c13431fa"
            "9c3d548269bba0763097ef4fe1ed045"
        ),
        "display_name": "TrackWise Student",
        "role": "student",
        "student_id": None,
        "module": None,
        "presentation": None,
    },

    "instructor": {
        "username": "instructor",
        "password_hash": (
            "a3f6ef70f84060f7fdecfcd12e5d8d"
            "3b8ed452e97f732ec3fc6fc9646df8a022"
        ),
        "display_name": "Dr Sarah Ahmed",
        "role": "instructor",
        "modules": [],
    },

    "admin": {
        "username": "admin",
        "password_hash": (
            "832f5c8d2e13124978121f762e47cb"
            "2ca29ce48d6cdfb4a6b8a0b690c7e982d9"
        ),
        "display_name": "Programme Administrator",
        "role": "admin",
    },
}


class UserConfigurationError(ValueError):
    """Raised when an authenticated user has no valid OULAD assignment."""


def _hash_password(password: str) -> str:
    """Return a SHA-256 hash for local prototype authentication."""
    return hashlib.sha256(password.encode("utf-8")).hexdigest()


def _verify_password(password: str, expected_hash: str) -> bool:
    """Safely compare the supplied password with the configured hash."""
    actual_hash = _hash_password(password)

    return hmac.compare_digest(
        actual_hash,
        expected_hash,
    )

def authenticate_user(
    username: str,
    password: str,
    student_info,
    expected_role: str | None = None,
) -> dict | None:
    """Authenticate a local TrackWise account.

    Student demo login
    ------------------
    Any valid OULAD student can sign in to the Student portal using the
    student ID as both username and password, for example ``6516 / 6516``.

    The existing named prototype accounts (``student``, ``instructor``,
    ``admin``) remain available.  Student-ID authentication is deliberately
    restricted to the Student portal and is suitable only for this local
    research/conference demonstration.
    """

    username_raw = str(username or "").strip()
    password_raw = str(password or "").strip()
    role = str(expected_role).strip().lower() if expected_role is not None else None

    if not username_raw or not password_raw:
        return None

    # ------------------------------------------------------------------
    # STUDENT-ID DEMO LOGIN
    # ------------------------------------------------------------------
    # Allow this route only when the Student portal is selected (or when
    # no expected role was supplied by an older caller).
    if username_raw.isdigit() and role in {None, "student"}:
        if password_raw != username_raw:
            return None

        if student_info is None or student_info.empty:
            raise UserConfigurationError(
                "No learner enrolments are available."
            )

        required = {
            "id_student",
            "code_module",
            "code_presentation",
        }
        if not required.issubset(student_info.columns):
            raise UserConfigurationError(
                "Student enrolment data are missing required fields."
            )

        records = student_info.dropna(
            subset=[
                "id_student",
                "code_module",
                "code_presentation",
            ]
        ).copy()
        records["id_student"] = pd.to_numeric(
            records["id_student"],
            errors="coerce",
        )

        student_id = int(username_raw)
        eligible = records[records["id_student"].eq(student_id)].copy()
        if eligible.empty:
            return None

        # Prefer this student's enrolment that already has recommendation
        # output, so the Student page is useful immediately when possible.
        selected = _preferred_recommendation_demo_row(eligible)

        if selected is None:
            preferred_rows = eligible[
                eligible["code_module"].astype(str).eq(DEFAULT_MODULE)
                & eligible["code_presentation"].astype(str).eq(
                    DEFAULT_PRESENTATION
                )
            ]
            if not preferred_rows.empty:
                selected = preferred_rows.iloc[0]
            else:
                # If a student has multiple enrolments, choose the most
                # recent presentation deterministically.  A later UI can
                # expose a switcher restricted to this student's courses.
                selected = (
                    eligible.assign(
                        _module=eligible["code_module"].astype(str),
                        _presentation=eligible["code_presentation"].astype(str),
                    )
                    .sort_values(
                        ["_presentation", "_module"],
                        ascending=[False, True],
                    )
                    .iloc[0]
                )

        enrolments = [
            {
                "module": str(row.code_module),
                "presentation": str(row.code_presentation),
            }
            for row in eligible[["code_module", "code_presentation"]]
            .drop_duplicates()
            .sort_values(["code_presentation", "code_module"])
            .itertuples(index=False)
        ]

        return {
            "username": username_raw,
            "display_name": f"Student {student_id}",
            "role": "student",
            "student_id": student_id,
            "module": str(selected["code_module"]),
            "presentation": str(selected["code_presentation"]),
            "enrolments": enrolments,
            "demo_student_id_login": True,
        }

    # Numeric credentials must never authenticate into Instructor/Admin.
    if username_raw.isdigit():
        return None

    # ------------------------------------------------------------------
    # EXISTING NAMED DEMO ACCOUNTS
    # ------------------------------------------------------------------
    username_key = username_raw.lower()
    account = USER_ACCOUNTS.get(username_key)

    if account is None:
        return None

    if not _verify_password(
        password_raw,
        account["password_hash"],
    ):
        return None

    # The role selector is only a portal choice. Credentials still determine
    # the authenticated role. Normalise case so callers may pass Student/student.
    if role is not None and str(account.get("role", "")).lower() != role:
        return None

    return resolve_user(
        username_key,
        student_info,
    )


def _preferred_recommendation_demo_row(eligible):
    """Prefer a learner with precomputed recommendation output for the demo.

    This is used only when the account has no explicitly configured student_id.
    It keeps the demo private (one fixed learner) while ensuring the conference
    Student view has recommendation/behaviour data when those exports exist.
    """
    candidates = [RECOMMENDATION_DIR / "recommendation_summary_Q2.parquet"]
    for path in candidates:
        if not path.is_file():
            continue
        try:
            import pandas as pd
            rec = pd.read_parquet(path)
        except Exception:
            continue
        required = {"id_student", "code_module", "code_presentation"}
        if rec.empty or not required.issubset(rec.columns):
            continue
        valid = rec.merge(
            eligible[["id_student", "code_module", "code_presentation"]],
            on=["id_student", "code_module", "code_presentation"],
            how="inner",
        )
        if valid.empty:
            continue
        # Prefer a useful but not alarmist demo profile.
        if "intervention_level" in valid.columns:
            rank = {"Targeted Support": 0, "Self-Guided Support": 1, "No Additional Action": 2, "Instructor Follow-up": 3}
            valid = valid.assign(_rank=valid["intervention_level"].map(rank).fillna(4))
            sort_cols = ["_rank"] + (["max_gap_severity"] if "max_gap_severity" in valid.columns else [])
            valid = valid.sort_values(sort_cols, ascending=[True] + ([False] if len(sort_cols) > 1 else []))
        row = valid.iloc[0]
        return eligible[
            (eligible["id_student"] == row["id_student"])
            & (eligible["code_module"] == row["code_module"])
            & (eligible["code_presentation"] == row["code_presentation"])
        ].iloc[0]
    return None


def resolve_user(
    username: str,
    student_info,
) -> dict:
    """Resolve authenticated account to valid OULAD access scope."""

    if username not in USER_ACCOUNTS:
        raise UserConfigurationError(
            "That TrackWise account is unavailable."
        )

    user = deepcopy(USER_ACCOUNTS[username])

    # Password hash must never be placed in Streamlit session state.
    user.pop("password_hash", None)

    # Administrator works from institution-level analytics.
    if user["role"] == "admin":
        return user

    if student_info is None or student_info.empty:
        raise UserConfigurationError(
            "No learner enrolments are available."
        )

    records = student_info.dropna(
        subset=[
            "id_student",
            "code_module",
            "code_presentation",
        ]
    ).copy()

    pairs = sorted(
        set(
            zip(
                records["code_module"],
                records["code_presentation"],
            )
        )
    )

    if not pairs:
        raise UserConfigurationError(
            "No valid module/presentation combinations "
            "are available."
        )

    preferred = (
        DEFAULT_MODULE,
        DEFAULT_PRESENTATION,
    )

    ordered_pairs = (
        ([preferred] if preferred in pairs else [])
        + [
            pair
            for pair in pairs
            if pair != preferred
        ]
    )

    # --------------------------------------------------------------
    # INSTRUCTOR
    # --------------------------------------------------------------

    if user["role"] == "instructor":

        configured = user.get(
            "modules",
            [],
        )

        if configured:

            invalid = any(
                not isinstance(
                    pair,
                    (tuple, list),
                )
                or len(pair) != 2
                or tuple(pair) not in pairs
                for pair in configured
            )

            if invalid:
                raise UserConfigurationError(
                    "An assigned instructor course is unavailable. "
                    "Check demo_users.py."
                )

            user["modules"] = sorted(
                set(
                    tuple(pair)
                    for pair in configured
                )
            )

        else:

            user["modules"] = ordered_pairs[
                :max(
                    0,
                    DEFAULT_INSTRUCTOR_COHORT_COUNT,
                )
            ]

        if not user["modules"]:
            raise UserConfigurationError(
                "This instructor has no authorised courses."
            )

        return user

    # --------------------------------------------------------------
    # STUDENT
    # --------------------------------------------------------------

    if user["role"] != "student":
        raise UserConfigurationError(
            "The configured TrackWise role is unavailable."
        )

    eligible = records

    mapping = [
        (
            "id_student",
            "student_id",
        ),
        (
            "code_module",
            "module",
        ),
        (
            "code_presentation",
            "presentation",
        ),
    ]

    for column, field in mapping:

        configured_value = user.get(field)

        if configured_value is not None:

            eligible = eligible[
                eligible[column]
                == configured_value
            ]

    if eligible.empty:
        raise UserConfigurationError(
            "The configured student or course "
            "is unavailable."
        )

    if user.get("student_id") is None:
        analytics_row = _preferred_recommendation_demo_row(eligible)
        if analytics_row is not None:
            eligible = eligible[
                (eligible["id_student"] == analytics_row["id_student"])
                & (eligible["code_module"] == analytics_row["code_module"])
                & (eligible["code_presentation"] == analytics_row["code_presentation"])
            ]

    preferred_rows = eligible[
        (
            eligible["code_module"]
            == DEFAULT_MODULE
        )
        &
        (
            eligible["code_presentation"]
            == DEFAULT_PRESENTATION
        )
    ]

    if not preferred_rows.empty:
        eligible = preferred_rows

    row = (
        eligible
        .sort_values(
            [
                "code_module",
                "code_presentation",
                "id_student",
            ]
        )
        .iloc[0]
    )

    user.update(
        student_id=int(
            row["id_student"]
        ),
        module=str(
            row["code_module"]
        ),
        presentation=str(
            row["code_presentation"]
        ),
    )

    return user


# ---------------------------------------------------------------------
# Compatibility alias
# ---------------------------------------------------------------------
# Keep temporarily in case another project module still imports the
# old resolver name.

resolve_demo_user = resolve_user
DemoConfigurationError = UserConfigurationError