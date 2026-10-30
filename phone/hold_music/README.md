# Hold music

`hold-music.ogg` is self-made for this repository: `make_hold_music.py` synthesizes every note, an arpeggio over
eight bars that loops without a click, and Opus encodes it:

```sh
python3 hold_music/make_hold_music.py /tmp/hold-music.wav
ffmpeg -i /tmp/hold-music.wav -c:a libopus -b:a 32k hold_music/hold-music.ogg
```

Its authors dedicate the recording and the script to the public domain under
[CC0 1.0](https://creativecommons.org/publicdomain/zero/1.0/). `HOLD_MUSIC_FILE` names another file to play instead.
