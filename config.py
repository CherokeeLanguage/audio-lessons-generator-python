#!/usr/bin/env python3
import pathlib
from dataclasses import dataclass
from typing import Optional
from typing import TextIO

from dataclasses_json import dataclass_json


@dataclass_json
@dataclass
class Config:
    deck_source: Optional[str] = None  # Source a different dataset file for the vocabulary to process.
    review_deck: pathlib.Path | None = None
    session_max_duration: float = 25 * 60 - 30  # Max 1 hour - 30 seconds per session.
    create_mp4: bool = True
    break_on_end_note: bool = True

    collect_audio: bool = True  # whether to actually collect the audio in use for other projects.

    final_review_session_count: int = 0

    resort_by_length: bool = False  # For use with smaller fixed vocabulary sets like 'Animals.'

    sessions_to_create: int = 999
    create_all_sessions: bool = True
    extra_sessions: int = 2

    new_card_max_tries: int = 7
    new_card_tries_decrement: int = 0

    new_cards_max_per_session: int = 21
    new_cards_per_session: int = 14  # 14  # 7
    new_cards_increment: int = 1

    review_card_max_tries: int = 5
    review_card_tries_decrement: int = 0

    review_cards_max_per_session: int = 21
    review_cards_per_session: int = 14  # 7
    review_cards_increment: int = 2

    temp_dir: str = "tmp"
    output_dir: str = "output"
    sort_deck_by_size: bool = False

    alpha: float = 1.3  # Duration multiplier. Lower = faster speaking, Higher - slower speaking.

    @staticmethod
    def load(file: TextIO):
        return Config.from_json(file.read())

    @staticmethod
    def save(file: TextIO, config: "Config") -> None:
        file.write(config.to_json(indent=4, sort_keys=True))
        file.write("\n")


if __name__ == "__main__":
    cfg: Config = Config()
    with open("test-config.json", "w") as f:
        Config.save(f, cfg)
