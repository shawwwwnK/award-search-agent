"""Deterministic conflict detection for parsed requests."""

from award_agent.domain import Conflict, DateWindow, DurationConstraint


def detect_conflicts(
    departure: DateWindow | None,
    return_window: DateWindow | None,
    duration: DurationConstraint | None,
) -> list[Conflict]:
    conflicts: list[Conflict] = []
    if departure is not None and return_window is not None:
        if return_window.end < departure.start:
            conflicts.append(
                Conflict(
                    code="return_before_departure",
                    fields=["departure", "return_date"],
                    detail="The return-date constraint ends before the departure window begins.",
                )
            )
        if (
            duration is not None
            and departure.start == departure.end
            and return_window.start == return_window.end
        ):
            actual_days = (return_window.start - departure.start).days
            tolerance = 1 if duration.approximate else 0
            if abs(actual_days - duration.days) > tolerance:
                conflicts.append(
                    Conflict(
                        code="duration_date_mismatch",
                        fields=["departure", "return_date", "duration"],
                        detail=(
                            f"The dates imply {actual_days} days, which conflicts with "
                            f"the stated {duration.days}-day duration."
                        ),
                    )
                )
    return conflicts
