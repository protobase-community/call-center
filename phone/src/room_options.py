from livekit.agents import room_io


def room_options() -> room_io.RoomOptions:
    """How the agent hears the room: through the caller's voice only, never typed `lk.chat` turns.

    A tool may therefore treat every turn as spoken; turning typed turns back on needs a check of
    where each turn came from.
    """
    return room_io.RoomOptions(text_input=False)
