# Sounds

Drop 16-bit PCM WAV files here, named to match what you play them as:
`denied.wav` here is played by `play_sound("denied")` in code, by requesting
`GET /play?name=denied`, and automatically whenever the lid slams on a throw
(`THROWN_SOUND` in `python/main.py`).

Mono or stereo both work; sample rate can be anything (each stream tells the
ESP32 its own rate). Files are not committed to the repo (gitignored) since
they can be large and are specific to your deployment - copy them onto the
UNO Q's own storage directly.

Any size works here - unlike the ESP32's own onboard flash, this just needs
to fit on the UNO Q's storage, which is orders of magnitude larger.

If the ESP32's mDNS name (`trashcan.local`) is unreliable on your network,
set `ESP32_AUDIO_HOST` (and `ESP32_HOST`) as environment variables to the
board's raw IP instead - see the boot log over serial for what it picked up.
