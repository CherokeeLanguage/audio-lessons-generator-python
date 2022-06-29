#!/usr/bin/env bash
"""true" '''\'
set -e
eval "$(${CONDA_EXE:-conda} shell.bash hook)"
conda deactivate
conda activate audio-lessons
exec python "$0" "$@"
exit $?
''"""
import re
from re import Match

from chrutils import ced2mco


def main() -> None:
    in_file: str = "data/cll2-v1-vocab-list-ced.txt"
    out_file: str = "data/cll2-v1-vocab-list-mco.txt"
    with open(in_file, "r") as r:
        with open(out_file, "w") as w:
            for line in r:
                if not line.strip():
                    continue
                # line = line.replace("\u00a0", " ")
                if "[" in line:
                    matches: list[str] = re.findall("\\[.*?]", line)
                    if not matches:
                        continue
                    for match in matches:
                        mco_text = ced2mco(match)
                        line = line.replace(match, mco_text)
                if "(" in line:
                    matches: list[str] = re.findall("\\(.*?\\)", line)
                    if not matches:
                        continue
                    for match in matches:
                        mco_text = ced2mco(match)
                        line = line.replace(match, mco_text)
                w.write(line)
    pass


if __name__ == '__main__':
    main()
