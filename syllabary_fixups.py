#!/usr/bin/env bash
"""true" '''\'
set -e
eval "$(${CONDA_EXE:-conda} shell.bash hook)"
conda activate audio-lessons
exec python "$0" "$@"
exit $?
''"""
# ID|PSET|ALT_PRONOUNCE|PRONOUN|VERB|GENDER|SYLLABARY|PRONOUNCE|ENGLISH|INTRO NOTE|END NOTE|APP_FILE
import glob
import pathlib
import shutil

import chrutils


def main() -> None:
    backup_dir: pathlib.Path = pathlib.Path("data/backup")
    backup_dir.mkdir(exist_ok=True)
    for dataset in glob.glob("data/*.txt"):
        shutil.copy(dataset, backup_dir)
        with open(dataset, "r") as r:
            line = r.readline().strip()
        if "|" not in line:
            continue
        header_fields = line.split("|")
        if len(header_fields) != 12:
            continue
        if "SYLLABARY" not in header_fields:
            continue
        ix_alt_pronounce = header_fields.index("ALT_PRONOUNCE")
        ix_pronounce = header_fields.index("PRONOUNCE")
        ix_syllabary = header_fields.index("SYLLABARY")
        output_file: str = dataset+".tmp"
        with open(dataset, "r") as r, open(output_file, "w") as w:
            w.write(r.readline())
            for line in r:
                sline = line.strip()
                if sline.startswith("#"):
                    w.write(line)
                    continue
                if not sline:
                    w.write(line)
                    continue
                fields = line.strip().split("|")
                if len(fields) != 12:
                    w.write(line)
                    continue
                if not fields[ix_pronounce] and not fields[ix_alt_pronounce]:
                    w.write(line)
                    continue
                # Move alt pronunciations into main pronounce field
                if fields[ix_alt_pronounce]:
                    if fields[ix_pronounce]:
                        fields[ix_pronounce] += "; "
                    fields[ix_pronounce] += fields[ix_alt_pronounce]
                    fields[ix_alt_pronounce] = ""
                fields[ix_syllabary] = ""
                for subfield in fields[ix_pronounce].split(";"):
                    subfield = subfield.strip()
                    if fields[ix_syllabary]:
                        fields[ix_syllabary] = fields[ix_syllabary] + "; "
                    fields[ix_syllabary] = fields[ix_syllabary] + chrutils.pronounce2syllabary(subfield)
                w.write("|".join(fields))
                w.write("\n")


if __name__ == '__main__':
    main()
