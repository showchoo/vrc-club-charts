"""Bounded, locally observed OSC camera sweep inside a *manually opened* World.

This is a narrow building block for a future authorized inspection system.
It neither joins Worlds nor verifies room coverage, collision avoidance,
absence of people, DJ equipment, playback, or in-world permissions.
"""
from __future__ import annotations

from typing import Callable

try:
    from scripts.inspection_navigation_guard import signature, distance, DISTANCE_THRESHOLD
except ModuleNotFoundError:
    from inspection_navigation_guard import signature, distance, DISTANCE_THRESHOLD

MAX_TURNS = 4
TURN_SECONDS = 0.48
OBSERVE_SECONDS = 0.35
MIN_TIME_LEFT = 1.2


def sweep_plan(turns: int = MAX_TURNS) -> tuple[str, ...]:
    if type(turns) is not int or not 1 <= turns <= MAX_TURNS:
        raise ValueError("Sweep supports between 1 and 4 short turns")
    return tuple(
        action
        for _ in range(turns)
        for action in ("observe", "turn_right")
    ) + ("observe",)


def run_sweep(*, controller, capture_png: Callable[[], bytes],
              still_safe: Callable[[], bool],
              seconds_left: Callable[[], float],
              log_action: Callable[[dict], None],
              turns: int = MAX_TURNS) -> dict:
    """Observe between strictly time-bounded local OSC turns.

    Runtime validation is deliberately conservative: missing/unchanged
    screenshots lead to early stop; brief screen changes cannot prove motion.
    Neutral axes are owned by controller.act/close in all exit paths.
    """
    actions = sweep_plan(turns)
    previous = None
    stale_turns = 0
    visible_changes = 0
    executed_turns = 0
    observation_count = 0

    def summary(status: str, reason: str) -> dict:
        return {
            "status": status, "reason": reason,
            "plannedTurns": turns, "executedTurns": executed_turns,
            "observations": observation_count,
            "viewChangesObserved": visible_changes,
            "reliablePositionOrCoverageVerified": False,
            "peopleAbsentIndependentlyVerified": False,
            "djEquipmentFunctionalityVerified": False,
        }

    for action in actions:
        if not still_safe():
            return summary("stopped", "window_unfocused_or_capture_stopped")
        if seconds_left() < MIN_TIME_LEFT:
            return summary("incomplete", "recording_time_exhausted")

        if action == "observe":
            current = signature(capture_png())
            observation_count += 1
            changed = None if previous is None else (
                distance(previous, current) > DISTANCE_THRESHOLD
            )
            if changed is not None:
                if changed:
                    visible_changes += 1
                    stale_turns = 0
                else:
                    stale_turns += 1
            previous = current
            # After two camera turns with no *visible* change, do not
            # continue rotating on a blank/stale/occluded window.
            if stale_turns >= 2:
                log_action({"action": "stop", "safetyDecision": "no_visible_change",
                            "observation": observation_count})
                return summary("stopped", "no_visible_change_after_two_turns")
            duration = OBSERVE_SECONDS
        else:
            duration = TURN_SECONDS

        # The underlying controller verifies foreground focus while an axis
        # is held, and neutralizes every movement axis after each action.
        controller.act(action, still_safe, duration=duration)
        if action == "turn_right":
            executed_turns += 1
        log_action({
            "action": action,
            "safetyDecision": "bounded_local_sweep",
            "observation": observation_count,
            "requestedSeconds": duration,
            "viewChangedSinceLastTurn": changed if action == "observe" else None,
        })
    return summary("completed", "bounded_sequence_finished")
