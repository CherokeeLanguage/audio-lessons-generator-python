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
    minutes = int((position // 60) % 60)
    hours = int(position // (60 * 60))
    return f"{hours:02d}:{minutes:02d}:{seconds:02d},{ms:03d}"

def ts_srt(serialized: str) -> float:
    hours, minutes, seconds_msec = serialized.split(':')
    seconds, msec = seconds_msec.split(',')
    position = (
        int(hours) * 60 * 60
      + int(minutes) * 60
      + int(seconds)
      + int(msec) / 1000
    )

    return position

@dataclasses.dataclass
class SrtEntry:
    seq: int = 0
    start: float = 0.0
    end: float = 0.0
    text: str = ""

    def __str__(self) -> str:
        return f"{self.seq}\n{srt_ts(self.start)} --> {srt_ts(self.end)}\n{self.text}\n\n"
    
    @staticmethod
    def deserialize(serialized: str) -> "SrtEntry":
        lines = serialized.strip('\n').split('\n')
        seq = int(lines[0].strip())
        start_ts, end_ts = lines[1].split(' --> ')
        start, end = ts_srt(start_ts), ts_srt(end_ts)
        text = lines[2]
        return SrtEntry(
            seq=seq,
            start=start,
            end=end,
            text=text
        )

