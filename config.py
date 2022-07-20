#!/usr/bin/env python3
from dataclasses import dataclass
from typing import Optional
from typing import TextIO

from dataclasses_json import dataclass_json


@dataclass_json
@dataclass
class Config:
    deck_source: Optional[str] = None  # Source a different dataset file for the vocabulary to process.
    session_max_duration: float = 60 * 60 - 30  # Max 1 hour - 30 seconds per session.
    create_mp4: bool = True
    break_on_end_note: bool = True

    final_review_session_count: int = 0
    data_dir: str = "walc1"

    debug_deck: bool = False
    debug_deck_size: int = 20
    sessions_to_create: int = 999
    create_all_sessions: bool = True
    extra_sessions: int = 2

    new_card_max_tries: int = 7
    new_card_tries_decrement: int = 0

    new_cards_max_per_session: int = 28
    new_cards_per_session: int = 14  # 14  # 7
    new_cards_increment: int = 1

    review_card_max_tries: int = 6
    review_card_tries_decrement: int = 0

    review_cards_max_per_session: int = 42
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
