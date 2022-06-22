import math

from dataclasses import field

from dataclasses import dataclass


@dataclass
class CardUtils:

    pimsleur_intervals: list[float] = field(default_factory=list)
    sm2_intervals: list[float] = field(default_factory=list)
    sm2_intervals_days: list[int] = field(default_factory=list)

    def __post_init__(self):
        ms: float = 1
        for i in range(0, 15):
            ms *= 5.0
            self.pimsleur_intervals.append(ms)

        # for fractional SM2 gaps
        secs_day: float = 60 * 60 * 24
        days: float = 4.0
        self.sm2_intervals.append(secs_day)
        for i in range(0, 15):
            self.sm2_intervals.append(secs_day * days)
            days *= 1.7

        # for whole SM2 gaps
        days = 4.0
        self.sm2_intervals_days.append(1)
        for i in range(0, 15):
            self.sm2_intervals_days.append(math.ceil(days))
            days *= 1.7

    def next_pimsleur_interval(self, correct_in_a_row: int) -> float:
        if correct_in_a_row < 0:
            correct_in_a_row = 0
        if correct_in_a_row > len(self.pimsleur_intervals) - 1 :
            correct_in_a_row = len(self.pimsleur_intervals) - 1
        return self.pimsleur_intervals[correct_in_a_row]

    def next_session_interval_secs(self, box: int) -> float:
        if box >= len(self.sm2_intervals):
            box = len(self.sm2_intervals) -1
        if box < 0:
            box = 0
        return self.sm2_intervals[box]

    def next_session_interval_days(self, box: int) -> int:
        if box >= len(self.sm2_intervals_days):
            box = len(self.sm2_intervals_days) - 1
        if box < 0:
            box = 0
        return self.sm2_intervals_days[box]
