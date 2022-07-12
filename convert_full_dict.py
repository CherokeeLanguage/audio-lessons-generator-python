#!/usr/bin/env bash
"""true" '''\'
set -e
eval "$(${CONDA_EXE:-conda} shell.bash hook)"
conda activate audio-lessons
exec python "$0" "$@"
exit $?
''"""
import os
import unicodedata
from pathlib import Path
import re
from chrutils import ascii_ced2mco
from chrutils import rrd2mco


def main() -> None:

    os.chdir(Path(__file__).resolve().parent)

    in_file: Path = Path("data").joinpath("full_dict_raw.txt")
    out_file: Path = Path("data").joinpath("full_dict_mco.txt")

    idx_id: int = 0
    idx_definition: int = 1

    idx_example_english: int = 3
    idx_example_translit: int = 4
    idx_example_syllabary: int = 5

    idx_syll_entry: int = 6
    idx_syll_na_plural: int = 2
    idx_syll_present_1st: int = 7
    idx_syll_immediate_2nd: int = 8
    idx_syll_deverbal: int = 9
    idx_syll_completive: int = 10
    idx_syll_incompletive: int = 11

    idx_pron_entry: int = 12
    idx_pron_na_plural: int = 13
    idx_pron_present_1st: int = 14
    idx_pron_immediate_2nd: int = 15
    idx_pron_deverbal: int = 16
    idx_pron_completive: int = 17
    idx_pron_incompletive: int = 18

    idx_source: int = 19

    lines: list[str] = list()
    with open(in_file, "r") as r:
        for line in r:
            line = line.strip()
            if line.startswith("id|") or line.startswith("-"):
                continue
            parts = line.split("|")
            parts = [part.strip() for part in parts]
            main_entry_syllabary: str = parts[idx_syll_entry].strip()
            if not main_entry_syllabary or main_entry_syllabary == "-":
                continue
            main_entry_pronounce: str = parts[idx_pron_entry].strip()
            if not main_entry_pronounce or main_entry_pronounce == "-":
                continue
            if main_entry_pronounce.startswith("-") or main_entry_pronounce.endswith("-"):
                continue
            record_id: str = parts[idx_id]
            definition: str = parts[idx_definition]

            syll: list[str] = list()
            syll.append(parts[idx_syll_entry])
            syll.append(parts[idx_syll_na_plural])
            syll.append(parts[idx_syll_present_1st])
            syll.append(parts[idx_syll_completive])
            syll.append(parts[idx_syll_incompletive])
            syll.append(parts[idx_syll_immediate_2nd])
            syll.append(parts[idx_syll_deverbal])

            pron: list[str] = list()
            pron.append(parts[idx_pron_entry])
            pron.append(parts[idx_pron_na_plural])
            pron.append(parts[idx_pron_present_1st])
            pron.append(parts[idx_pron_completive])
            pron.append(parts[idx_pron_incompletive])
            pron.append(parts[idx_pron_immediate_2nd])
            pron.append(parts[idx_pron_deverbal])

            example_syllabary: str = parts[idx_example_syllabary]
            example_translit: str = parts[idx_example_translit]
            example_english: str = parts[idx_example_english]

            source: str = parts[idx_source]

            text: str = ""
            item: str = ""
            for item in pron:
                item = item.strip()
                if source == "ced":
                    item = ascii_ced2mco(item).strip()
                if source == "rrd":
                    item = rrd2mco(item).strip()
                text += "|"
                if item.startswith("-") or item.endswith("-"):
                    continue
                if item:
                    translit: str = unicodedata.normalize("NFD", item)
                    translit = re.sub("(?i)[^a-z ]", "", translit)
                    text += item + f" [{translit}]"

            for item in syll:
                item = item.strip()
                text += "|"
                if item.startswith("-"):
                    continue
                text += item

            lines.append(f"{definition}\n{text[1:]}|{record_id}|{source}")

    with open(out_file, "w") as w:
        for line in lines:
            w.write(line)
            w.write("\n\n")


if __name__ == '__main__':
    main()

