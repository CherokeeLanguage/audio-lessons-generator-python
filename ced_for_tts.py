#!/usr/bin/env bash
"""true" '''\'
set -e
eval "$(${CONDA_EXE:-conda} shell.bash hook)"
conda activate audio-lessons
exec python "$0" "$@"
exit $?
''"""
import hashlib
import os
import re
import textwrap
import unicodedata
from pathlib import Path


def main() -> None:

    os.chdir(os.path.dirname(__file__))

    voices: list[str] = ["en-345-m", "en-360-m", "en-333-f", "en-361-f"]
    # voices: list[str] = ["en-345-m"]
    in_file: Path = Path("cherokee-vocab-data/full_dict_mco.txt").resolve()
    out_file: Path = Path("cherokee-vocab-data/ced-for-tts.txt").resolve()

    already: set[str] = set()
    ced: list[tuple[str, str, str, str]] = list()
    with open(in_file, "r") as r:
        for line in r:
            line = line.strip()
            if "|" not in line:
                continue
            parts = line.split("|")
            # Only want C.E.D. for now.
            if parts[15] != "ced":
                continue
            for part in parts:
                # The source file has the pronunciations combined with romanization
                if "[" not in part:
                    continue
                part = part[:part.index("[")].strip()
                sub_parts = part.split(",")
                for sub_part in sub_parts:
                    sub_part = sub_part.strip().lower()
                    if sub_part in already:
                        print(f"dupe: {sub_part}")
                        continue
                    for voice in voices:
                        gender: str = "male" if voice.endswith("-m") else "female"
                        ced.append((sub_part, gender, voice, get_filename(voice, sub_part)))
                    already.add(sub_part)

    # sort by pronunciation, then sort by voice to order by voice, pronunciation
    ced.sort(key=lambda item: item[0].lower())
    ced.sort(key=lambda item: item[2].lower())

    with open(out_file, "w") as w:
        for entry in ced:
            w.write(f"{entry[0]}|{entry[1]}|{entry[2]}|{entry[3]}\n")


def get_filename(voice: str, text: str):
    text = re.sub("\\s+", " ", textwrap.dedent(text)).strip()
    text = text.lower()
    if not voice:
        voice = "-"
    sha1: str
    sha1 = hashlib.sha1(text.encode("UTF-8")).hexdigest()
    _ = unicodedata.normalize("NFD", text).replace(" ", "_")
    _ = unicodedata.normalize("NFC", re.sub("[^a-z_]", "", _))
    if len(_) > 32:
        _ = _[:32]
    filename: str = f"{_}_{voice}_{sha1}.mp3"
    return filename


if __name__ == '__main__':
    main()
