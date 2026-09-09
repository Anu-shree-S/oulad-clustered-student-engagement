"""Display-only pseudonyms; source data and analytical keys stay untouched."""


def build_student_display_map(student_ids) -> dict[int, str]:
    """Assign stable sequential aliases from sorted, distinct dataset IDs."""
    return {int(raw_id): f"TW-S{1001 + index}"
            for index, raw_id in enumerate(sorted(set(int(value) for value in student_ids)))}


def pseudonymise_student_frame(frame, mapping):
    """Copy a display/export frame and replace its raw key with a Learner label."""
    display = frame.copy()
    if "id_student" in display.columns:
        display["id_student"] = display["id_student"].map(mapping).fillna("Unavailable learner")
        display = display.rename(columns={"id_student": "Learner"})
    return display
