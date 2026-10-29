from room_options import room_options


def test_takes_no_typed_turns() -> None:
    # without text input options the session registers no lk.chat handler
    assert room_options().get_text_input_options() is None


def test_keeps_voice_and_the_pre_connect_buffer() -> None:
    options = room_options()
    audio_input = options.get_audio_input_options()

    assert audio_input is not None
    assert audio_input.pre_connect_audio is True
    assert options.get_audio_output_options() is not None
    assert options.get_text_output_options() is not None
