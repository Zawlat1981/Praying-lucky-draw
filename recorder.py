from pathlib import Path

import streamlit.components.v1 as components

_component = components.declare_component(
    "worship_recorder", path=str(Path(__file__).parent / "recorder_frontend")
)

FORMATS = {
    "audio/webm": "webm",
    "audio/ogg": "ogg",
    "audio/mp4": "m4a",
    "audio/wav": "wav",
}


def audio_input(key, max_bytes):
    value = _component(key=key, max_bytes=max_bytes, default=None)
    if value is None:
        return None
    if not isinstance(value, (bytes, bytearray)):
        raise ValueError("Invalid recording data")
    header, separator, data = bytes(value).partition(b"\n")
    try:
        mime_type = header.decode("ascii")
    except UnicodeDecodeError as error:
        raise ValueError("Invalid recording format") from error
    if not separator or mime_type not in FORMATS or not data or len(data) > max_bytes:
        raise ValueError("Invalid or oversized recording")
    return {"data": data, "mime_type": mime_type}
