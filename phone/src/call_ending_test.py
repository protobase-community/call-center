from call_ending import CallEnding


async def test_reports_the_end_once_whichever_comes_first():
    ended: list[str] = []

    async def end() -> None:
        ended.append("ended")

    ending = CallEnding(end)
    await ending.start()
    await ending.wait()
    await ending.start()

    assert ended == ["ended"]
