"""The agent stepping back while staff are in the Protobase call, and taking over when they leave.

The bridge marks in its participant's attributes whether staff are in the call (see
staff_attribute.py). When the first arrives, the hold music stops, the assistant stops hearing the
caller and breaks off what it was saying. When the last leaves, or the bridge does, while the
caller is still there, the assistant hears the caller again and learns so as {"staff": "left"}.
"""

from collections.abc import Callable

from livekit import rtc

from staff_attribute import staff_present
from tool_result import tool_result


class StaffPresence:
    def __init__(
        self,
        end_wait: Callable[[], None],
        listen: Callable[[bool], None],
        interrupt: Callable[[], object],
        report: Callable[[str], object],
    ) -> None:
        self._end_wait = end_wait
        self._listen = listen
        self._interrupt = interrupt
        self._report = report
        self.present = False

    def update(self, present: bool) -> None:
        if present == self.present:
            return
        self.present = present
        if present:
            self._end_wait()
            self._listen(False)
            self._interrupt()
            return
        self._listen(True)
        self._report(tool_result(staff="left"))


def watch_staff(room: rtc.Room, presence: StaffPresence) -> Callable[[], None]:
    """Follows the bridge's attributes in the room; returns a function that stops."""

    def on_attributes(_: dict[str, str], participant: rtc.Participant) -> None:
        if participant.kind != rtc.ParticipantKind.PARTICIPANT_KIND_AGENT:
            return
        present = staff_present(participant.attributes)
        if present is not None:
            presence.update(present)

    def on_disconnected(participant: rtc.RemoteParticipant) -> None:
        if staff_present(participant.attributes) is not None:
            presence.update(False)

    room.on("participant_attributes_changed", on_attributes)
    room.on("participant_disconnected", on_disconnected)

    def stop() -> None:
        room.off("participant_attributes_changed", on_attributes)
        room.off("participant_disconnected", on_disconnected)

    return stop
