#!/usr/bin/env bash
"""true" '''\'
set -e
eval "$(${CONDA_EXE:-conda} shell.bash hook)"
conda activate audio-lessons
exec python "$0" "$@"
exit $?
''"""
# ID|PSET|ALT_PRONOUNCE|PRONOUN|VERB|GENDER|SYLLABARY|PRONOUNCE|ENGLISH|INTRO NOTE|END NOTE|APP_FILE
import csv
import glob
import pathlib
import re
import shutil

import chrutils


def main() -> None:
    data_dir: pathlib.Path = pathlib.Path("syllabary_lookup")
    lookup_file: pathlib.Path = data_dir.joinpath("lookup.csv")
    syllabary_lookup: dict[str, str] = dict()
    if lookup_file.exists():
        with open(lookup_file, "r", newline='') as r:
            csv_reader = csv.reader(r)
            first_line: bool = True
            for row in csv_reader:
                if first_line:
                    first_line=False
                    continue
                if len(row) < 3:
                    continue
                pronounce = row[1].strip().lower()
                pronounce = re.sub("(?i)[ˀɁɂ]", "ʔ", pronounce)
                syllabary = row[2].strip()
                if not pronounce or not syllabary:
                    continue
                syllabary_lookup[pronounce] = syllabary
                
    for fixes_file in glob.glob("syllabary_lookup/*_fixes.csv"):
        with open(fixes_file, "r", newline='') as r:
            csv_reader = csv.reader(r)
            first_line: bool = True
            for row in csv_reader:
                if first_line:
                    first_line=False
                    continue
                if len(row) < 3:
                    continue
                pronounce = row[1].strip().lower()
                pronounce = re.sub("(?i)[ˀɁɂ]", "ʔ", pronounce)
                syllabary = row[2].strip()
                if not pronounce or not syllabary:
                    continue
                syllabary_lookup[pronounce] = syllabary

    backup_dir: pathlib.Path = pathlib.Path("cherokee-vocab-data/backup")
    backup_dir.mkdir(exist_ok=True)
    for dataset in glob.glob("cherokee-vocab-data/*.txt"):
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
                # Make sure we are using the IPA glottal stop
                fields[ix_pronounce] = re.sub("(?i)[ˀɁɂ]", "ʔ", fields[ix_pronounce])
                fields[ix_syllabary] = ""
                for subfield in fields[ix_pronounce].split(";"):
                    subfield = subfield.strip().lower()
                    if fields[ix_syllabary]:
                        fields[ix_syllabary] = fields[ix_syllabary] + "; "
                    if subfield in syllabary_lookup:
                        fields[ix_syllabary] = fields[ix_syllabary] + syllabary_lookup[subfield]
                    else:
                        new_syllabary: str = chrutils.pronounce2syllabary(subfield)
                        fields[ix_syllabary] = fields[ix_syllabary] + new_syllabary
                        if subfield not in syllabary_lookup:
                            syllabary_lookup[subfield] = new_syllabary
                w.write("|".join(fields))
                w.write("\n")
        shutil.move(output_file, dataset)

        with open(lookup_file.parent.joinpath("lookup.tmp"), "w", newline='') as w:
            csv_writer = csv.writer(w)
            csv_writer.writerow(["NEEDS_FIXING", "PRONOUNCE", "SYLLABARY"])
            keys: list[str] = [*syllabary_lookup]
            keys.sort()
            for key in keys:
                if not key:
                    continue
                _ = "*" if re.search("(?i)[a-z]", syllabary_lookup[key]) else ""
                csv_writer.writerow([_, key, syllabary_lookup[key]])
        shutil.move(lookup_file.parent.joinpath("lookup.tmp"), lookup_file)
        with open(lookup_file.parent.joinpath("lookup-bad.csv"), "w", newline='') as w:
            csv_writer = csv.writer(w)
            csv_writer.writerow(["NEEDS_FIXING", "PRONOUNCE", "SYLLABARY"])
            keys: list[str] = [*syllabary_lookup]
            keys.sort()
            for key in keys:
                if not key:
                    continue
                if re.search("(?i)[a-z]", syllabary_lookup[key]):
                    csv_writer.writerow(["*", key, syllabary_lookup[key]])


if __name__ == '__main__':
    main()
