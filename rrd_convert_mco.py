#!/usr/bin/env bash
"""true" '''\'
set -e
eval "$(${CONDA_EXE:-conda} shell.bash hook)"
conda activate audio-lessons
exec python "$0" "$@"
exit $?
''"""
import csv
import os
import re
import unicodedata
from collections.abc import Sequence
from pathlib import Path

from chrutils import fix_rrd_pronunciation
from chrutils import rrd2mco
from chrutils import pronounce2syllabary


def main() -> None:
    os.chdir(os.path.dirname(__file__))
    in_file = Path("data").joinpath("raven-dictionary-edit-file-orig.csv")
    out_file = Path("data").joinpath("raven-dictionary-edit-file.csv")

    fieldnames: Sequence
    with open(in_file, "r", newline='') as r, open(out_file, "w", newline='') as w:
        reader: csv.DictReader = csv.DictReader(r)
        fieldnames = reader.fieldnames
        writer: csv.DictWriter = csv.DictWriter(w, fieldnames=fieldnames)
        writer.writeheader()
        for record in reader:
            pronunciation: str = record["PRONUNCIATION"]
            pronunciation = pronunciation.strip()
            pronunciation = re.sub("\\s+", " ", pronunciation)
            pronunciation = rrd2mco(pronunciation)
            syllabary: str = record["SYLLABARY"]
            if pronunciation:
                prev_pronunciation: str = pronunciation
                for syl in "ᏣᏤᏥᏦᏧᏨ":
                    if syl in syllabary:
                        pronunciation = fix_rrd_pronunciation(pronunciation)
                        syllabary_check: str = pronounce2syllabary(pronunciation)
                        if prev_pronunciation != pronunciation and syllabary_check != syllabary:
                            pronunciation = f"*{pronunciation}"
                        break
                record["PRONUNCIATION"] = pronunciation

            writer.writerow(record)


if __name__ == '__main__':
    main()

