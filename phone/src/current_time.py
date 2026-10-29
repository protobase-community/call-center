"""The current date and time in the caller's zone, which never goes into the instructions."""

from collections.abc import Callable
from datetime import UTC, datetime
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from livekit.agents import RunContext, ToolError, function_tool, llm

from caller_info import CallerInfo
from tool_result import tool_result

Clock = Callable[[], datetime]

_DESCRIPTION = """Get the current date and time. Call it whenever the date, the day of the week or
the time matters; never guess them.
time_zone: an IANA zone such as Europe/Madrid, when the user names a place whose time they want;
leave it out for the user's own time."""


def _now() -> datetime:
    return datetime.now(UTC)


def current_time_tool(clock: Clock = _now) -> llm.FunctionTool:
    async def current_date_and_time(
        context: RunContext[CallerInfo], time_zone: str | None = None
    ) -> str:
        zone_name = time_zone or context.userdata.time_zone
        if zone_name is None:
            # the caller's zone is unknown: report UTC and say so, rather than pass off the
            # server's zone as theirs
            return tool_result(now=clock().isoformat(timespec="minutes"), time_zone=None)

        try:
            zone = ZoneInfo(zone_name)
        except (ZoneInfoNotFoundError, ValueError) as error:
            raise ToolError(f"{zone_name!r} is not an IANA time zone") from error

        now = clock().astimezone(zone)
        return tool_result(
            now=now.isoformat(timespec="minutes"),
            weekday=now.strftime("%A"),
            time_zone=zone_name,
        )

    return function_tool(current_date_and_time, description=_DESCRIPTION)
