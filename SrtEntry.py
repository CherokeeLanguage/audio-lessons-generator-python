import dataclasses


@dataclasses.dataclass
class SrtEntry:
    seq: int = 0
    start: str = ""
    end: str = ""
    text: str = ""

    def __str__(self) -> str:
        return f"{self.seq}\n{self.start} --> {self.end}\n{self.text}\n\n"
