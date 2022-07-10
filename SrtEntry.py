"""
An SRT file is one of the most common file formats used in the process of subtitling and/or captioning. 'SRT' refers to a 'SubRip Subtitle' file, which originated from the DVD-ripping software by the same name.

FORMAT:

sequence_number [int] [nl]
start [str] '-->' end [str]
multi-line text ... [nl]
[nl]
"""
import dataclasses


def srt_ts(position: float) -> str:
    """Returns SRT formatted timestamp string where position is in seconds."""
    ms = int(position * 1000) % 1000
    seconds = int(position) % 60
    minutes = (position // 60) % 60
    hours = position // (60 * 60)
    return f"{hours:02d}:{minutes:02d}:{seconds:02d},{ms:03d}"


@dataclasses.dataclass
class SrtEntry:
    seq: int = 0
    start: float = 0.0
    end: float = 0.0
    text: str = ""

    def __str__(self) -> str:
        return f"{self.seq}\n{srt_ts(self.start)} --> {srt_ts(self.end)}\n{self.text}\n\n"
