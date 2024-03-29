from __future__ import annotations

from functools import total_ordering

from typing import Iterable

from abc import abstractmethod

from typing import overload

from collections.abc import MutableSequence

import random

from dataclasses import dataclass
from dataclasses import field

rand: random.Random = random.Random(1234)


@dataclass(slots=True)
class AudioDataFile:
    file: str = ""
    pronunciation: str = ""
    voice: str = ""
    duration: float = 0.0


@dataclass(slots=True)
class AudioData:
    _sort_key: str = ""
    syllabary: str = ""
    bound_pronoun: str = ""
    verb_stem: str = ""
    answer_files: list[AudioDataFile] = field(default_factory=list)
    challenge_files: list[AudioDataFile] = field(default_factory=list)
    _card_id: str = ""
    sex: str = ""
    answer: str = ""
    challenge: str = ""
    intro_note: str = ""
    end_note: str = ""
    challenge_alts: list[str] = field(default_factory=list)

    @property
    def sort_key(self) -> str:
        return f"{len(self._sort_key):03}-{self._sort_key}"

    @sort_key.setter
    def sort_key(self, sort_key: str) -> None:
        if sort_key:
            self._sort_key = sort_key
        else:
            self._sort_key = ""

    @property
    def card_id(self) -> str:
        tmp: str = self._card_id
        while len(tmp) < 4:
            tmp = "0" + tmp
        return tmp

    @card_id.setter
    def card_id(self, card_id: str) -> None:
        tmp: str = str(card_id)
        while len(tmp) < 4:
            tmp = "0" + tmp
        self._card_id = tmp

    @property
    def answer_file(self) -> AudioDataFile:
        rand.shuffle(self.answer_files)
        return self.answer_files[0]

    @property
    def challenge_file(self) -> AudioDataFile:
        rand.shuffle(self.challenge_files)
        return self.challenge_files[0]


@dataclass(slots=True)
class AudioCardStats:
    correct: bool = False
    leitner_box: int = 0
    pimsleur_slot: int = 0
    show_again_delay: float = 0.0
    shown: int = 0
    total_shown_time: float = 0.0
    tries_remaining: int = 0
    new_card: bool = True
    next_session_show: int = 0

    def leitner_box_dec(self) -> None:
        if self.leitner_box:
            self.leitner_box -= 1

    def leitner_box_inc(self) -> None:
        self.leitner_box += 1

    def pimsleur_slot_dec(self) -> None:
        if self.pimsleur_slot:
            self.pimsleur_slot -= 1

    def pimsleur_slot_inc(self) -> None:
        self.pimsleur_slot += 1

    def tries_remaining_dec(self) -> None:
        if self.tries_remaining:
            self.tries_remaining -= 1

    def tries_remaining_inc(self) -> None:
        self.tries_remaining += 1


@dataclass(slots=True)
@total_ordering  # Only sorts by show again delay
class AudioCard:
    data: AudioData = field(default_factory=AudioData)
    my_deck: "LeitnerAudioDeck" = None
    card_stats: AudioCardStats = field(default_factory=AudioCardStats)

    def __eq__(self, other: AudioCard) -> bool:
        if self.card_stats.show_again_delay != other.card_stats.show_again_delay:
            return False
        return self.data.card_id == other.data.card_id

    def __lt__(self, other):
        return self.card_stats.show_again_delay < other.card_stats.show_again_delay

    def __hash__(self) -> int:
        return hash(repr(self))

    def next_session_threshold(self, max_shows: int) -> int:
        leitner_box: int = self.card_stats.leitner_box
        return max(max_shows - leitner_box, 1)

    def is_in_deck(self) -> bool:
        if self.my_deck and self in self.my_deck.cards:
            return True
        return False

    def reset_stats(self) -> None:
        self.card_stats.correct = True
        self.card_stats.shown = 0
        self.card_stats.total_shown_time = 0.0

    def reset_tries_remaining(self, max_tries_remaining: int = 3) -> None:
        self.card_stats.tries_remaining = self.next_session_threshold(max_tries_remaining)


@dataclass(slots=True)
class LeitnerAudioDeck(MutableSequence):

    cards: list[AudioCard] = field(default_factory=list)

    def update_time(self, delta_secs: float) -> None:
        for card in self.cards:
            show_again_delay: float = card.card_stats.show_again_delay
            show_again_delay -= delta_secs
            card.card_stats.show_again_delay = max(show_again_delay, 0.0)

    def sort_by_show_again(self) -> None:
        rand.shuffle(self.cards)
        self.cards.sort(key=lambda card: card.card_stats.show_again_delay)

    def insert(self, index: int, value: AudioCard) -> None:
        self.cards.insert(index, value)

    @overload
    @abstractmethod
    def __getitem__(self, i: int) -> AudioCard: ...

    @overload
    @abstractmethod
    def __getitem__(self, s: slice) -> MutableSequence[AudioCard]: ...

    def __getitem__(self, i: int) -> AudioCard:
        return self.cards[i]

    @overload
    @abstractmethod
    def __setitem__(self, i: int, o: AudioCard) -> None: ...

    @overload
    @abstractmethod
    def __setitem__(self, s: slice, o: Iterable[AudioCard]) -> None: ...

    def __setitem__(self, i: int, o: AudioCard) -> None:
        self.cards[i] = o

    @overload
    @abstractmethod
    def __delitem__(self, i: int) -> None: ...

    @overload
    @abstractmethod
    def __delitem__(self, i: slice) -> None: ...

    def __delitem__(self, i: int) -> None:
        del self.cards[i]

    def __len__(self) -> int:
        return len(self.cards)

    def append(self, value: AudioCard) -> None:
        if value.my_deck:
            value.my_deck.cards.remove(value)
        self.cards.append(value)
        value.my_deck = self

    @property
    def next_show_time(self) -> float:
        if not self.cards:
            return 0.0
        delay: float = self.top_card.card_stats.show_again_delay
        return 0.0 if delay < 0.0 else delay

    @property
    def top_card(self) -> AudioCard | None:
        if not self.cards:
            return None
        return self.cards[0]

    @property
    def has_cards(self) -> bool:
        return True if self.cards else False


