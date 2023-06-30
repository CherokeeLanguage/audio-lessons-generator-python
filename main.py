#!/usr/bin/env bash
"""true" '''\'
set -e
eval "$(${CONDA_EXE:-conda} shell.bash hook)"
conda activate audio-lessons
exec python "$0" "$@"
exit $?
''"""
from __future__ import annotations
from os.path import relpath
import argparse
import dataclasses
import os
import pathlib
import random
import re
import shutil
import subprocess
import unicodedata
from datetime import date
from datetime import datetime
from random import Random

import jsonpickle
import simplejson
from pydub import AudioSegment
from tqdm import tqdm

import Prompts
import tts
from CardUtils import CardUtils
from LeitnerAudioDeck import AudioCard
from LeitnerAudioDeck import AudioData
from LeitnerAudioDeck import AudioDataFile
from LeitnerAudioDeck import LeitnerAudioDeck
from SrtEntry import SrtEntry
from config import Config

MP3_QUALITY: int = 3
MP3_HZ: int = 48_000

RESORT_BY_LENGTH: bool = False

IX_ALT_PRONOUNCE: int = 2
IX_PRONOUN: int = 3
IX_VERB: int = 4
IX_GENDER: int = 5
IX_SYLLABARY: int = 6
IX_PRONOUNCE: int = 7
IX_ENGLISH: int = 8
IX_INTRO_NOTE: int = 9
IX_END_NOTE: int = 10
IX_APP_FILE: int = 11

UNDERDOT: str = "\u0323"

CACHE_CHR = os.path.join("cache", "chr")
CACHE_EN = os.path.join("cache", "en")

IMS_VOICES_MALE: list[str] = ["en-345-m", "en-360-m"]
# IMS_VOICES_FEMALE: list[str] = ["en-294-f", "en-330-f", "en-333-f", "en-361-f"]
IMS_VOICES_FEMALE: list[str] = ["en-333-f", "en-361-f"]
IMS_VOICES: list[str] = list()
IMS_VOICES.extend(IMS_VOICES_FEMALE)
IMS_VOICES.extend(IMS_VOICES_MALE)
IMS_VOICES.sort()
ims_voices: list[str] = list()

AMZ_VOICES_MALE: list[str] = ["Joey"]
# AMZ_VOICES_FEMALE: list[str] = ["Joanna", "Kendra", "Kimberly", "Salli"]
AMZ_VOICES_FEMALE: list[str] = ["Kendra"]
AMZ_VOICES: list[str] = list()
AMZ_VOICES.extend(AMZ_VOICES_FEMALE)
AMZ_VOICES.extend(AMZ_VOICES_MALE)
amz_voices: list[str] = list()

AMZ_HZ: str = "24000"
LESSON_HZ: int = 48_000

rand: Random = Random(1234)
previous_voice: str = ""
amz_previous_voice: str = ""

cfg: Config | None = None


@dataclasses.dataclass
class Options:
    dataset: str = ""
    mp4: bool | None = None
    only_assemble: bool = False


def parse_args() -> Options:
    options: Options = Options()
    parser: argparse.ArgumentParser = argparse.ArgumentParser(description="Build challenge response audio sessions.")
    parser.add_argument("--dataset", type=str, required=True)
    parser.add_argument("--mp4", dest="mp4", action="store_const", const=True, required=False, help="""
    Enable mp4 generation. Use --no-mp4 to disable mp4 generation.
    Overrides value provided in dataset configuration file.
    """, default=None)
    parser.add_argument("--no-mp4", dest="mp4", action="store_const", const=False, required=False, help="""
        Enable mp4 generation. Use --no-mp4 to disable mp4 generation.
        Overrides value provided in dataset configuration file.
        """, default=None)
    parser.add_argument("--only-assemble", dest="only_assemble", action="store_const", const=True, default=False)
    args: argparse.Namespace = parser.parse_args()
    if args.mp4 is not None:
        options.mp4 = args.mp4
        if args.mp4:
            print(f"Forcing mp4 generation.")
        else:
            print(f"Skipping mp4 generation.")
    if args.only_assemble:
        options.only_assemble = True
    options.dataset = args.dataset
    return options


def next_ims_voice(gender: str = "") -> str:
    """Utility function to return a different non-repeated voice name based on gender"""
    global IMS_VOICES_FEMALE, IMS_VOICES_MALE, rand
    global previous_voice, ims_voices
    if not ims_voices:
        ims_voices.extend(IMS_VOICES_MALE)
        ims_voices.extend(IMS_VOICES_FEMALE)
        rand.shuffle(ims_voices)
    voice: str = ims_voices.pop()
    if gender:
        if gender == "m":
            if len(IMS_VOICES_MALE) < 2:
                previous_voice = ""
            if voice not in IMS_VOICES_MALE:
                return next_ims_voice(gender)
        if gender == "f":
            if len(IMS_VOICES_FEMALE) < 2:
                previous_voice = ""
            if voice not in IMS_VOICES_FEMALE:
                return next_ims_voice(gender)
    if previous_voice and voice == previous_voice:
        return next_ims_voice(gender)
    previous_voice = voice
    return voice


def next_amz_voice(gender: str = "") -> str:
    """Utility function to return a different non-repeated voice name based on gender"""
    global AMZ_VOICES_FEMALE, AMZ_VOICES_MALE, rand
    global amz_previous_voice, amz_voices
    if not amz_voices:
        amz_voices.extend(AMZ_VOICES_MALE)
        amz_voices.extend(AMZ_VOICES_FEMALE)
        rand.shuffle(amz_voices)
    voice: str = amz_voices.pop()
    if gender:
        if gender == "m":
            if len(AMZ_VOICES_MALE) < 2:
                amz_previous_voice = ""
            if voice not in AMZ_VOICES_MALE:
                return next_amz_voice(gender)
        if gender == "f":
            if len(AMZ_VOICES_FEMALE) < 2:
                amz_previous_voice = ""
            if voice not in AMZ_VOICES_FEMALE:
                return next_amz_voice(gender)
    if voice == amz_previous_voice:
        return next_amz_voice(gender)
    amz_previous_voice = voice
    return voice


def load_main_deck(source_file: str) -> LeitnerAudioDeck:
    chr2en_deck: LeitnerAudioDeck = LeitnerAudioDeck()
    dupe_pronunciation_check: set[str] = set()
    dupe_end_note_check: set[str] = set()
    cards_for_english_answers: dict[str, AudioCard] = dict()

    line_no: int = 0
    with open(source_file, "r") as r:
        id_chr2en: int = 0
        for line in r:
            # skip header line
            if not line_no:
                line_no = 1
                continue
            line_no += 1
            line = unicodedata.normalize("NFC", line).strip()
            # skip comments and blank lines
            if line.startswith("#") or not line:
                continue
            fields = line.split("|")
            if len(fields) > IX_APP_FILE + 1 or len(fields) < IX_APP_FILE:
                print(f"; {line}")
                raise Exception(f"[Line {line_no:,}] Wrong field count of {len(fields)}."
                                f" Should be {IX_APP_FILE + 1}.")
            skip_as_new = "*" in fields[0]

            verb_stem: str = unicodedata.normalize("NFD", fields[IX_VERB])
            verb_stem = re.sub("[¹²³⁴" + UNDERDOT + "]", "", verb_stem)
            verb_stem = unicodedata.normalize("NFC", verb_stem)

            bound_pronoun: str = unicodedata.normalize("NFD", fields[IX_PRONOUN])
            bound_pronoun = re.sub("[¹²³⁴" + UNDERDOT + "]", "", bound_pronoun)
            bound_pronoun = unicodedata.normalize("NFC", bound_pronoun)

            cherokee_text_alts: list[str] = list()
            cherokee_text = fields[IX_PRONOUNCE].strip()
            cherokee_text = re.sub("(?i)[ˀɁɂ]", "ʔ", cherokee_text)
            if not re.sub("(?i)[^a-z]", "", unicodedata.normalize("NFD", cherokee_text)):
                print(f"Warning - no Cherokee text: {line}")
                continue

            if ";" in cherokee_text:
                for text in cherokee_text.split(";"):
                    text = text.strip()
                    if not text:
                        continue
                    if text[-1] not in ",.?!":
                        text += "."
                    if text and text not in cherokee_text_alts:
                        cherokee_text_alts.append(text[0].upper()+text[1:])
                cherokee_text = cherokee_text[0:cherokee_text.index(";")].strip()
            if cherokee_text[-1] not in ",.?!":
                cherokee_text += "."
            cherokee_text = cherokee_text[0].upper() + cherokee_text[1:]

            check_text = re.sub("(?i)[.,!?;]", "", cherokee_text).strip()
            if check_text in dupe_pronunciation_check:
                print(f"[Line {line_no:,}] Duplicate pronunciation: {check_text}\n{fields}")
                raise Exception(f"[Line {line_no:,}] Duplicate pronunciation: {check_text}\n{fields}")
            dupe_pronunciation_check.add(check_text)
            gender: str = fields[IX_GENDER].strip()
            if gender:
                gender = gender.strip().lower()[0]
                if gender.lower() != "m" and gender.lower() != "f":
                    print(f"BAD GENDER: {fields}")
                    gender = ""

            english_text = fields[IX_ENGLISH].strip()
            if not re.sub("(?i)[^a-z]", "", unicodedata.normalize("NFD", english_text)):
                print(f"Warning - no English text: {line}")
                continue
            texts: list[str] = english_text.split(";")
            if texts:
                english_text = ""
                for text in texts:
                    text = text.strip()
                    if text[-1] not in ",.?!":
                        text += "."
                    if english_text:
                        english_text += " Or. "
                    english_text += text
            if "v. t." in english_text or "v.t." in english_text or "v. i." in english_text or "v.i." in english_text:
                english_text = english_text.replace("v.t.", "").replace("v.i.", "")\
                    .replace("v. t.", "").replace("v. i.", "")
            if "1." in english_text:
                english_text = english_text.replace("1.", "")
                english_text = english_text.replace("2.", ". Or, ")
                english_text = english_text.replace("3.", ". Or, ")
                english_text = english_text.replace("4.", ". Or, ")
            if "(" in english_text:
                english_text = english_text.replace(" (1)", "")
                english_text = english_text.replace(" (one)", "")
                english_text = english_text.replace(" (animate)", ", living, ")
                english_text = english_text.replace(" (inanimate)", ", non-living, ")
            if "/" in english_text:
                english_text = english_text.replace("/", ", or, ")

            if re.search("(?i)\\bhe, it\\b", english_text):
                english_text = re.sub("(?i)(he), it\\b", "\\1, or, it", english_text)
            if re.search("(?i)\\bhim, it\\b", english_text):
                english_text = re.sub("(?i)(him), it\\b", "\\1, or, it", english_text)
            if re.search("(?i)\\bshe, it\\b", english_text):
                english_text = re.sub("(?i)(she), it\\b", "\\1, or, it", english_text)
            if re.search("(?i)\\bher, it\\b", english_text):
                english_text = re.sub("(?i)(her), it\\b", "\\1, or, it", english_text)

            if "'s" in english_text:
                english_text = english_text.replace("he's", "he is")
                english_text = english_text.replace("she's", "she is")
                english_text = english_text.replace("it's", "it is")
                english_text = english_text.replace("He's", "He is")
                english_text = english_text.replace("She's", "She is")
                english_text = english_text.replace("It's", "It is")
            if "'re" in english_text:
                english_text = english_text.replace("'re", " are")
            english_text = english_text[0].upper() + english_text[1:]

            english_text = fix_english_sex_genders(english_text)

            to_en_card: AudioCard
            to_en_data: AudioData

            intro_note: str
            if len(fields) > IX_INTRO_NOTE:
                intro_note = fields[IX_INTRO_NOTE].strip()
            else:
                intro_note: str = ""

            end_note: str
            if len(fields) > IX_END_NOTE:
                end_note = fields[IX_END_NOTE].strip()
            else:
                end_note: str = ""
            if end_note:
                if end_note in dupe_end_note_check:
                    print(f"- WARN DUPLICATE END NOTE: ({line_no:,}) {end_note}\n{fields}")
                dupe_end_note_check.add(end_note)

            if check_text in cards_for_english_answers:
                to_en_card = cards_for_english_answers[check_text]
                to_en_data = to_en_card.data
                old_answer: str = to_en_data.answer
                to_en_data.answer += " Or, " + english_text
                print(f"- {old_answer} => {to_en_data.answer}")
                if intro_note:
                    to_en_card.data.intro_note = intro_note
                if end_note:
                    to_en_card.data.end_note = end_note
            else:
                id_chr2en += 1

                to_en_card = AudioCard()
                to_en_data = AudioData()
                to_en_card.data = to_en_data

                to_en_data.bound_pronoun = bound_pronoun
                to_en_data.verb_stem = verb_stem
                to_en_data.answer = english_text
                to_en_data.challenge = cherokee_text
                to_en_data.card_id = id_chr2en
                to_en_data.sex = gender
                if intro_note:
                    to_en_card.data.intro_note = intro_note
                if end_note:
                    to_en_card.data.end_note = end_note
                if skip_as_new:
                    to_en_data.bound_pronoun = "*"
                    to_en_data.verb_stem = "*"
                cards_for_english_answers[check_text] = to_en_card
                syllabary: str = fields[IX_SYLLABARY]
                to_en_data.sort_key = syllabary if syllabary else cherokee_text
                chr2en_deck.append(to_en_card)

            if fields[IX_ALT_PRONOUNCE] or cherokee_text_alts:
                alts: list[str] = fields[IX_ALT_PRONOUNCE].split(";")
                if cherokee_text not in to_en_data.challenge_alts:
                    to_en_data.challenge_alts.append(cherokee_text)
                for alt in alts:
                    alt = alt.strip()
                    if not alt:
                        continue
                    if alt[-1] not in ",.?!":
                        alt += "."
                    alt = re.sub("(?i)[ˀɁɂ]", "ʔ", alt)
                    if not alt or alt in to_en_data.challenge_alts:
                        continue
                    to_en_data.challenge_alts.append(alt)
                for alt in cherokee_text_alts:
                    alt = alt.strip()
                    if not alt:
                        continue
                    alt = re.sub("(?i)[ˀɁɂ]", "ʔ", alt)
                    if not alt or alt in to_en_data.challenge_alts:
                        continue
                    to_en_data.challenge_alts.append(alt)
            syllabary: str = fields[IX_SYLLABARY]
            if syllabary:
                to_en_data.syllabary = syllabary

    # Fix casing if needed.
    for to_en_card in chr2en_deck:
        to_en_data = to_en_card.data
        challenge: str = to_en_data.challenge
        to_en_data.challenge = challenge[0].upper() + challenge[1:]
        answer: str = to_en_data.answer
        to_en_data.answer = answer[0].upper() + answer[1:]
        alts: list[str] = to_en_data.challenge_alts.copy()
        to_en_data.challenge_alts.clear()
        for challenge in alts:
            challenge = challenge[0].upper() + challenge[1:]
            to_en_data.challenge_alts.append(challenge)

    review_sheet_chr2en: str = ""
    review_sheet_en2chr: str = ""
    for to_en_card in chr2en_deck:
        to_en_data = to_en_card.data
        review_sheet_chr2en += to_en_data.card_id
        review_sheet_chr2en += "|"
        review_sheet_chr2en += to_en_data.bound_pronoun
        review_sheet_chr2en += "|"
        review_sheet_chr2en += to_en_data.verb_stem
        review_sheet_chr2en += "|"
        review_sheet_chr2en += to_en_data.challenge
        review_sheet_chr2en += "|"
        review_sheet_chr2en += to_en_data.answer
        review_sheet_chr2en += "\n"

    with open("review-sheet-chr-en.txt", "w") as w:
        w.write(review_sheet_chr2en)

    with open("review-sheet-en-chr.txt", "w") as w:
        w.write(review_sheet_en2chr)

    return chr2en_deck


def fix_english_sex_genders(text_en) -> str:
    tmp: str = re.sub("\\s+", " ", text_en).strip()
    if "brother" in tmp.lower():
        return text_en
    if "sister" in tmp.lower():
        return text_en
    if "himself" in tmp:
        tmp = re.sub("(?i)(He )", "\\1 or she ", tmp)
        tmp = re.sub("\\bhimself", "themself", tmp)
    if "Himself" in tmp:
        tmp = re.sub("(?i)\\b(He )", "\\1or she ", tmp)
        tmp = re.sub("\\bHimself", "Themself", tmp)
    if re.search(".*\\b[Hh]is\\b.*", tmp):
        tmp = re.sub("(?i)\\b(His)", "\\1 or her", tmp)
    if " or she" not in tmp:
        tmp = re.sub("(?i)\\b(He )", "\\1or she ", tmp)
    if " or her" not in tmp:
        tmp = re.sub("(?i)( him)", "\\1 or her", tmp)
    tmp = re.sub("(?i)x(he|she|him|her|his)", "\\1", tmp)
    return tmp


def create_card_audio(deck: LeitnerAudioDeck):
    os.makedirs(CACHE_CHR, exist_ok=True)
    os.makedirs(CACHE_EN, exist_ok=True)
    entries: list[tts.TTSBatchEntry] = list()
    print("Scanning deck for cards needing Cherokee audio.")
    for card in tqdm(deck.cards):
        data: AudioData = card.data
        text_chr = data.challenge
        text_chr_alts = data.challenge_alts
        for voice in IMS_VOICES:
            data_file: AudioDataFile = AudioDataFile()
            data_file.file = tts.get_mp3_chr(voice, text_chr, cfg.alpha)
            data_file.voice = voice
            data_file.pronunciation = text_chr
            data.challenge_files.append(data_file)
            entry: tts.TTSBatchEntry = tts.TTSBatchEntry()
            entry.text=text_chr
            entry.voice=voice
            entries.append(entry)
            # tts.tts_chr(voice, text_chr, cfg.alpha)
            for alt in text_chr_alts:
                if alt == text_chr:
                    # don't add another entry to challenge files if we have the same
                    # pronunciation has already been added
                    continue
                data_file: AudioDataFile = AudioDataFile()
                data_file.file = tts.get_mp3_chr(voice, alt, cfg.alpha)
                data_file.voice = voice
                data_file.pronunciation = alt
                data.challenge_files.append(data_file)
                entry: tts.TTSBatchEntry = tts.TTSBatchEntry()
                entry.text = alt
                entry.voice = voice
                entries.append(entry)
                # tts.tts_chr(voice, alt, cfg.alpha)
    print("Creating Cherokee audio challenges.")
    tts.tts_chr_batch(entries, cfg.alpha)

    print("Creating English audio answers.")
    for card in tqdm(deck.cards):
        data: AudioData = card.data
        text_en = data.answer
        for voice in AMZ_VOICES:
            data_file: AudioDataFile = AudioDataFile()
            data_file.file = tts.get_mp3_en(voice, text_en)
            data_file.voice = voice
            data_file.pronunciation = text_en
            data.answer_files.append(data_file)
            tts.tts_en(voice, text_en)


vstem_counts: dict[str, int] = dict()
pbound_counts: dict[str, int] = dict()


def save_stem_counts(deck: LeitnerAudioDeck) -> None:
    global vstem_counts, pbound_counts
    vstem_counts.clear()
    pbound_counts.clear()
    for card in deck.cards:
        data = card.data
        bp: str = data.bound_pronoun.strip()
        if not bp:
            continue
        if bp not in pbound_counts:
            pbound_counts[bp] = 0
        pbound_counts[bp] += 1
        vs: str = data.verb_stem.strip()
        if vs not in vstem_counts:
            vstem_counts[vs] = 0
        vstem_counts[vs] += 1


def skip_new(card: AudioCard) -> bool:
    data = card.data
    if "*" in data.card_id:
        return True
    bp = data.bound_pronoun
    vs = data.verb_stem
    if bp == "*" or vs == "*":
        return True
    if bp not in pbound_counts:
        return False
    if vs not in vstem_counts:
        return False
    return pbound_counts[bp] > 2 and vstem_counts[vs] > 4


main_deck: LeitnerAudioDeck | None = None
discards_deck: LeitnerAudioDeck | None = LeitnerAudioDeck()
finished_deck: LeitnerAudioDeck | None = LeitnerAudioDeck()
active_deck: LeitnerAudioDeck | None = LeitnerAudioDeck()
max_review_cards_this_session: int = 0


def save_deck(deck: LeitnerAudioDeck, destination: pathlib.Path):
    jsonpickle.load_backend('simplejson', 'dumps', 'loads', ValueError)
    jsonpickle.set_preferred_backend('simplejson')
    jsonpickle.set_encoder_options('simplejson', ensure_ascii=False)

    if not os.path.exists(destination.parent):
        destination.parent.mkdir(exist_ok=True)
    with open(destination, "w") as w:
        w.write(jsonpickle.dumps(deck, indent=2))
        w.write("\n")


def load_review_deck(source: pathlib.Path) -> LeitnerAudioDeck:
    deck: LeitnerAudioDeck
    jsonpickle.load_backend('simplejson', 'dumps', 'loads', ValueError)
    jsonpickle.set_preferred_backend('simplejson')
    jsonpickle.set_encoder_options('simplejson', ensure_ascii=False)
    if not os.path.exists(source):
        raise RuntimeError(f"Review deck {source} not found.")
    with open(source, "r") as r:
        json_text = r.read()
        return jsonpickle.loads(json_text)


def collect_audio(dataset: str, out_dir: str, deck: LeitnerAudioDeck) -> None:
    print("Collecting audio for other projects to use.")
    dest_audio: pathlib.Path = pathlib.Path(os.path.join(out_dir, "source")).resolve()
    dest_en = os.path.join(dest_audio, "en")
    os.makedirs(dest_en, exist_ok=True)
    dest_chr = os.path.join(dest_audio, "chr")
    os.makedirs(dest_chr, exist_ok=True)
    card: AudioCard
    for card in tqdm(deck):
        data = card.data
        for file in data.challenge_files:
            shutil.copy(file.file, dest_chr)
            file.file = os.path.basename(file.file)
        for file in data.answer_files:
            shutil.copy(file.file, dest_en)
            file.file = os.path.basename(file.file)
    # save deck *after* altering the file paths
    save_deck(main_deck, pathlib.Path(dest_audio, f"{dataset}-with-audio-file.json"))
    cwd: str = os.getcwd()
    os.chdir(dest_audio)
    zip_file = pathlib.Path(dest_audio).with_stem(f"{dataset}-source").with_suffix(".zip")
    subprocess.run(["zip", zip_file, "-r", relpath(dest_audio)])
    os.chdir(cwd)

def main() -> None:
    random.seed(0)  # Make output idempotent for consecutive runs on the same day.
    global cfg, max_new_reached, review_count, max_review_cards_this_session
    global main_deck, discards_deck, finished_deck, active_deck
    deck_source: str

    util: CardUtils = CardUtils()
    os.chdir(os.path.dirname(__file__))

    options: Options = parse_args()
    load_config(options.dataset)
    dataset: str = options.dataset
    if options.mp4 is not None:
        cfg.create_mp4 = options.mp4

    out_dir: str

    if cfg.alpha and cfg.alpha != 1.0:
        out_dir = os.path.join(os.path.realpath("."), "output", f"{dataset}_{cfg.alpha:.2f}")
    else:
        out_dir = os.path.join(os.path.realpath("."), "output", dataset)

    if cfg.deck_source:
        deck_source = cfg.deck_source
    else:
        deck_source = dataset

    shutil.rmtree(out_dir, ignore_errors=True)
    os.makedirs(out_dir, exist_ok=True)

    main_deck = load_main_deck(os.path.join("cherokee-vocab-data", deck_source + ".txt"))

    if cfg.resort_by_length:
        main_deck.cards.sort(key=lambda c: c.data.sort_key)
    save_deck(main_deck, pathlib.Path("decks", f"{dataset}-orig.json"))

    create_card_audio(main_deck)

    if cfg.collect_audio:
        collect_audio(dataset, out_dir, main_deck)
        if options.only_assemble:
            return

    if cfg.review_deck:
        review_deck: LeitnerAudioDeck = load_review_deck(cfg.review_deck)
        for card in review_deck.cards:
            finished_deck.append(card)
        # save_deck(main_deck, pathlib.Path("decks", f"{dataset}-with-review-cards.json"))

    prompts = Prompts.create_prompts()

    _exercise_set: int = 0
    keep_going: bool = True

    prev_card_id: str = ""
    extra_sessions: int = cfg.extra_sessions

    short_speech_intro: bool = False
    for card in main_deck:
        if card.data.challenge_alts:
            short_speech_intro = True
            break

    end_notes_by_track: dict[int, str] = dict()
    metadata_by_track: dict[int, dict[str, str]] = dict()

    while keep_going and (_exercise_set < cfg.sessions_to_create or cfg.create_all_sessions):

        if _exercise_set > 0:
            print()
            print()

        print(f"=== DAY: {_exercise_set + 1:04}")
        print()

        lead_in: AudioSegment = AudioSegment.silent(750, LESSON_HZ).set_channels(1)
        # Exercise set title
        lead_in = lead_in.append(prompts[dataset])
        lead_in = lead_in.append(AudioSegment.silent(750))

        if _exercise_set == 0:
            # Description of exercise set
            if dataset + "-about" in prompts:
                lead_in = lead_in.append(prompts[dataset + "-about"])
                lead_in = lead_in.append(AudioSegment.silent(750))

            if dataset + "-notes" in prompts:
                lead_in = lead_in.append(prompts[dataset + "-about"])
                lead_in = lead_in.append(AudioSegment.silent(750))

            # Pre-lesson verbiage
            lead_in = lead_in.append(prompts["language_culture_1"])
            lead_in = lead_in.append(AudioSegment.silent(1_500))

            lead_in = lead_in.append(prompts["keep_going"])
            lead_in = lead_in.append(AudioSegment.silent(1_500))

            lead_in = lead_in.append(prompts["learn_sounds_first"])
            lead_in = lead_in.append(AudioSegment.silent(2_250))

            lead_in = lead_in.append(prompts["intro_2"])
            lead_in = lead_in.append(AudioSegment.silent(1_500))

            lead_in = lead_in.append(prompts["intro_3"])
            lead_in = lead_in.append(AudioSegment.silent(1_500))

            if short_speech_intro:
                lead_in = lead_in.append(prompts["short-speech"])
                lead_in = lead_in.append(AudioSegment.silent(1_500))
                short_speech_intro = False

            # Let us begin
            lead_in = lead_in.append(prompts["begin"])
            lead_in = lead_in.append(AudioSegment.silent(750))

        session_start: str = f"Day {_exercise_set + 1}."
        lead_in = lead_in.append(tts.en_audio(Prompts.AMZ_VOICE_INSTRUCTOR, session_start))
        lead_in = lead_in.append(AudioSegment.silent(750))

        lead_out: AudioSegment = AudioSegment.silent(2_250, LESSON_HZ).set_channels(1)
        lead_out = lead_out.append(prompts["concludes_this_exercise"])
        lead_out = lead_out.append(AudioSegment.silent(2_250))
        lead_out = lead_out.append(prompts["copy_1"])
        lead_out = lead_out.append(AudioSegment.silent(1_500))
        lead_out = lead_out.append(prompts["copy_by_sa"])
        lead_out = lead_out.append(AudioSegment.silent(2_250))
        lead_out = lead_out.append(prompts["produced"])
        lead_out = lead_out.append(AudioSegment.silent(2_250))

        main_audio: AudioSegment = AudioSegment.silent(100, LESSON_HZ).set_channels(1)

        new_count: int = 0
        introduced_count: int = 0
        hidden_count: int = 0
        challenge_count: int = 0

        max_new_reached = False
        review_count = 0
        finished_deck.update_time(60 * 60 * 24)  # One day seconds
        finished_deck.sort_by_show_again()
        save_stem_counts(finished_deck)
        if finished_deck.has_cards:
            print(f"--- Have {len(finished_deck.cards):,} previously finished cards for possible use.")

        max_new_cards_this_session: int = min(cfg.new_cards_max_per_session,
                                              cfg.new_cards_per_session + _exercise_set * cfg.new_cards_increment)
        print(f"--- Max new cards: {max_new_cards_this_session:,d}")
        max_review_cards_this_session = min(cfg.review_cards_max_per_session,
                                            cfg.review_cards_per_session + _exercise_set * cfg.review_cards_increment)
        print(f"--- Max review cards: {max_review_cards_this_session:,d}")

        end_note: str = ""
        prev_end_note: str = ""

        first_new_challenge: str = ""
        last_new_challenge: str = ""
        first_review_challenge: str = ""
        last_review_challenge: str = ""

        srt_entries: list[SrtEntry] = list()
        srt_entry: SrtEntry

        new_cards: list[str] = list()
        review_cards: list[str] = list()
        hidden_cards: list[str] = list()

        while (lead_in.duration_seconds + lead_out.duration_seconds + main_audio.duration_seconds
               < cfg.session_max_duration):
            start_length: float = main_audio.duration_seconds
            card: AudioCard = next_card(_exercise_set, prev_card_id)
            if not card:
                break
            card_id: str = card.data.card_id
            card_stats = card.card_stats
            new_card: bool = card_stats.new_card
            introduce_card: bool = new_card and not skip_new(card)
            extra_delay: float = card_stats.show_again_delay
            data = card.data
            if card_id == prev_card_id:
                card_stats.show_again_delay = 32
                continue
            prev_card_id = card_id
            if new_card:
                if not first_new_challenge:
                    first_new_challenge = data.challenge
                else:
                    last_new_challenge = data.challenge
                if data.end_note:
                    end_note = data.end_note
                if introduce_card:
                    print(f"Introduced card: {data.challenge} [{card_stats.tries_remaining:,}]")
                else:
                    card_stats.leitner_box += 2  # hidden new cards should be already known vocabulary
                    card_stats.new_card = False
                    card.reset_tries_remaining(max(cfg.review_card_max_tries // 2,  #
                                                   cfg.review_card_max_tries  #
                                                   - cfg.review_card_tries_decrement  #
                                                   * _exercise_set))
                    print(f"Hidden new card: {data.challenge} [{card_stats.tries_remaining:,}]")
                if end_note and end_note != prev_end_note:
                    prev_end_note = end_note
                    print(f"- End note: {end_note}")
                    if cfg.break_on_end_note:
                        max_new_reached = True
                        print(f" - No more new cards this session.")
            if new_card:
                if introduce_card:
                    introduced_count += 1
                else:
                    hidden_count += 1
                new_count += 1
                if new_count >= max_new_cards_this_session:
                    max_new_reached = True
                    print(f" - No more new cards this session.")
                main_audio = main_audio.append(AudioSegment.silent(1_500))
                card_stats.new_card = False
                if introduce_card:
                    main_audio = append_introduce_phrase(main_audio, prompts, _exercise_set, new_count)
            if not introduce_card:
                if not new_card:
                    challenge_count += 1
                if extra_delay > 0:
                    _: int = int(1_000 * min(7.0, extra_delay))
                    main_audio = main_audio.append(AudioSegment.silent(_), crossfade=0)
                main_audio = append_translate_phrase(main_audio, prompts, _exercise_set, challenge_count)
                if not card_stats.shown:
                    if not first_review_challenge:
                        first_review_challenge = data.challenge
                    else:
                        last_review_challenge = data.challenge
            challenge: str
            syllabary: str = data.syllabary
            if ";" in syllabary:
                syllabary=syllabary[:syllabary.index(";")].strip()
            if not data.challenge_alts or (new_card and introduce_card):
                challenge = data.challenge
            else:
                challenge = rand.choice(data.challenge_alts)
            vocabulary_text = f"{data.challenge}|{data.answer}|{syllabary}"
            if new_card:
                if introduce_card:
                    new_cards.append(vocabulary_text)
                else:
                    hidden_cards.append(vocabulary_text)
            else:
                if vocabulary_text not in review_cards \
                        and vocabulary_text not in new_cards \
                        and vocabulary_text not in hidden_cards:
                            review_cards.append(vocabulary_text)
            srt_entry: SrtEntry = SrtEntry()
            srt_entry.text = challenge
            srt_entry.start = main_audio.duration_seconds
            srt_entries.append(srt_entry)
            data_file: AudioSegment = tts.chr_audio(next_ims_voice(data.sex), challenge, cfg.alpha)
            main_audio = main_audio.append(data_file, crossfade=0)
            srt_entry.end = main_audio.duration_seconds
            if introduce_card:
                # introduce Cherokee challenge
                main_audio = main_audio.append(AudioSegment.silent(1_500))
                data_file: AudioSegment = tts.chr_audio(next_ims_voice(data.sex), challenge, cfg.alpha)
                if new_count < 8 and _exercise_set == 0:
                    main_audio = main_audio.append(prompts["listen_again"])
                else:
                    main_audio = main_audio.append(prompts["listen_again_short"])
                main_audio = main_audio.append(AudioSegment.silent(1_500))
                srt_entry: SrtEntry = SrtEntry()
                srt_entries.append(srt_entry)
                srt_entry.text = challenge
                srt_entry.start = main_audio.duration_seconds
                main_audio = main_audio.append(data_file, crossfade=0)
                srt_entry.end = main_audio.duration_seconds
                main_audio = main_audio.append(AudioSegment.silent(1_500))

                # introduce alt pronunciations
                if len(data.challenge_alts) >  1:
                    if new_count < 6 and _exercise_set <= 2:
                        main_audio = main_audio.append(prompts["also_hear"])
                    else:
                        main_audio = main_audio.append(prompts["also_hear_short"])
                    main_audio = main_audio.append(AudioSegment.silent(1_000))
                    for alt in data.challenge_alts:
                        if alt == challenge:
                            continue
                        main_audio = main_audio.append(AudioSegment.silent(500))
                        srt_entry: SrtEntry = SrtEntry()
                        srt_entries.append(srt_entry)
                        srt_entry.text = alt
                        srt_entry.start = main_audio.duration_seconds
                        main_audio = main_audio.append(tts.chr_audio(next_ims_voice(data.sex), alt, cfg.alpha),
                                                       crossfade=0)
                        srt_entry.end = main_audio.duration_seconds
                        main_audio = main_audio.append(AudioSegment.silent(1_000))

                # output English gloss
                if new_count < 10 and _exercise_set == 0:
                    main_audio = main_audio.append(prompts["its_translation_is"])
                    main_audio = main_audio.append(AudioSegment.silent(750))
                else:
                    main_audio = main_audio.append(prompts["in_english"])
                    main_audio = main_audio.append(AudioSegment.silent(750))
            else:
                gap_duration: float = max(data_file.duration_seconds, 1.0)
                main_audio = main_audio.append(AudioSegment.silent(int(1_000 * gap_duration)))

            # The answer
            answer_audio: AudioSegment = tts.en_audio(next_amz_voice(data.sex), data.answer)
            # Silence gap for user to respond during. Only if the card was not introduced.
            if not introduce_card:
                _ = AudioSegment.silent(int((2 + 1.1 * answer_audio.duration_seconds) * 1_000))
                main_audio = main_audio.append(_)
            # Provide answer.
            srt_entry: SrtEntry = SrtEntry()
            srt_entry.text = data.answer
            srt_entry.start = main_audio.duration_seconds
            srt_entries.append(srt_entry)
            main_audio = main_audio.append(answer_audio)
            srt_entry.end = main_audio.duration_seconds
            if _exercise_set == 0:
                main_audio = main_audio.append(AudioSegment.silent(2_250))
            elif _exercise_set < 5:
                main_audio = main_audio.append(AudioSegment.silent(1_500))
            else:
                main_audio = main_audio.append(AudioSegment.silent(750))

            delta_tick: float = main_audio.duration_seconds - start_length
            active_deck.update_time(delta_tick)
            discards_deck.update_time(delta_tick)
            finished_deck.update_time(delta_tick)

            card_stats.pimsleur_slot_inc()
            next_interval: float = util.next_pimsleur_interval(card_stats.pimsleur_slot) + 1.0
            card_stats.show_again_delay = next_interval

        # Prepare decks for next session
        bump_completed()
        seconds_offset: float = 0.0
        for card in active_deck.cards.copy():
            discards_deck.append(card)
        if active_deck.has_cards:
            raise Exception("Active Deck should be empty!")
        for card in discards_deck.cards.copy():
            card_stats = card.card_stats
            if card_stats.shown >= card_stats.tries_remaining:
                card_stats.tries_remaining = 0
                bump_completed()
                continue
            card_stats.show_again_delay = seconds_offset
            seconds_offset += 1
            finished_deck.append(card)
        if discards_deck.has_cards:
            raise Exception("Discards Deck should be empty!")

        print("---")
        print(f"Introduced cards: {introduced_count:,}."
              f" Review cards: {review_count:,}."
              f" Hidden new cards: {hidden_count:,}.")

        challenge_start: str = first_new_challenge if first_new_challenge else first_review_challenge
        # challenge_start = re.sub("(?i)[^a-z- ]", "", unicodedata.normalize("NFD", challenge_start))
        challenge_start = unicodedata.normalize("NFC", challenge_start).strip()
        while challenge_start[-1] in ".,!?:":
            challenge_start = challenge_start[:-1]

        challenge_stop: str = last_new_challenge if last_new_challenge else last_review_challenge
        # challenge_stop = re.sub("(?i)[^a-z- ]", "", unicodedata.normalize("NFD", challenge_stop))
        challenge_stop = unicodedata.normalize("NFC", challenge_stop).strip()
        while challenge_stop[-1] in ".,!?:":
            challenge_stop = challenge_stop[:-1]

        # https://wiki.multimedia.cx/index.php/FFmpeg_Metadata#MP3
        tags: dict[str, str] = dict()

        challenge_start = unicodedata.normalize("NFC", challenge_start)
        challenge_stop = unicodedata.normalize("NFC", challenge_stop)

        if dataset == "cll1-v3":
            tags["album"] = "Cherokee Language Lessons 1 - 3rd Edition"
            tags["title"] = f"CLL 1 [{_exercise_set + 1:02d}] {challenge_start}…{challenge_stop}"
        elif dataset == "cll2":
            tags["album"] = "Cherokee Language Lessons 2"
            tags["title"] = f"CLL 2 [{_exercise_set + 1:02d}] {challenge_start}…{challenge_stop}"
        elif dataset == "beginning-cherokee":
            tags["album"] = "Beginning Cherokee - 2nd Edition"
            tags["title"] = f"BC [{_exercise_set + 1:02d}] {challenge_start}…{challenge_stop}"
        elif dataset == "animals":
            tags["album"] = "Animals"
            tags["title"] = f"Animals [{_exercise_set + 1:02d}] {challenge_start}…{challenge_stop}"
        elif dataset == "bound-pronouns":
            tags["album"] = "Bound Pronouns"
            tags["title"] = f"BP [{_exercise_set + 1:02d}] {challenge_start}…{challenge_stop}"
        elif dataset == "osiyo-tohiju-then-what":
            tags["album"] = "Osiyo, Tohiju?…Then what?"
            tags["title"] = f"Osiyo [{_exercise_set + 1:02d}] {challenge_start} ... {challenge_stop}"
        elif dataset == "ced-sentences":
            tags["album"] = "Example Sentences. Cherokee English Dictionary, 1st Edition"
            tags["title"] = f"C.E.D. Examples [{_exercise_set + 1:02d}] {challenge_start}…{challenge_stop}"
        else:
            tags["album"] = dataset
            tags["title"] = f"[{_exercise_set + 1:02d}] {challenge_start}…{challenge_stop}"

        tags["composer"] = "Michael Conrad"
        tags["copyright"] = f"©{date.today().year} Michael Conrad CC-BY"
        tags["language"] = "chr"
        tags["artist"] = "IMS-Toucan"
        tags["publisher"] = "Michael Conrad"
        tags["track"] = str(_exercise_set + 1)
        tags["date"] = str(datetime.utcnow().isoformat(sep="T", timespec="seconds"))
        tags["creation_time"] = str(datetime.utcnow().isoformat(sep="T", timespec="seconds"))
        tags["genre"] = "Spoken"
        tags["comments"] = "https://github.com/CherokeeLanguage/IMS-Toucan"
        tags["year"] = str(date.today().year)

        metadata_by_track[_exercise_set] = tags

        # Put mp3 for website related stuff in subfolder
        mp3_out_dir: str = os.path.join(out_dir, "mp3")
        os.makedirs(mp3_out_dir, exist_ok=True)

        srt_out_dir: str = os.path.join(out_dir, "srt")
        os.makedirs(srt_out_dir, exist_ok=True)

        # Track vocab by session
        vocab_out_dir: str = os.path.join(out_dir, "vocab")
        os.makedirs(vocab_out_dir, exist_ok=True)

        # Put graphic related stuff in subfolder
        img_out_dir: str = os.path.join(out_dir, "img")
        os.makedirs(img_out_dir, exist_ok=True)

        # Put MP4 related stuff in subfolder
        mp4_out_dir: str = os.path.join(out_dir, "mp4")
        os.makedirs(mp4_out_dir, exist_ok=True)

        # Output exercise audio
        combined_audio: AudioSegment = lead_in.append(main_audio)
        # Add any special end of session notes.
        if end_note:
            combined_audio = combined_audio.append(AudioSegment.silent(2_250))
            combined_audio = combined_audio.append(tts.en_audio(Prompts.AMZ_VOICE_INSTRUCTOR, end_note))
            print(f"* {end_note}")
        end_notes_by_track[_exercise_set] = end_note
        combined_audio = combined_audio.append(lead_out)

        # Add leadin offset to SRT entries. Assign sequence numbers. Capitalize first letter.
        _: int = 0
        for srt_entry in srt_entries:
            _ += 1
            srt_entry.seq = _
            srt_entry.start += lead_in.duration_seconds  # - 0.125  # appear slightly early
            srt_entry.end += lead_in.duration_seconds  # + 0.125  # disappear slightly late
            srt_entry.text = srt_entry.text[0].upper() + srt_entry.text[1:]

        # Output SRT file for use by ffmpeg mp4 creation process
        srt_name: str = f"{dataset}-{_exercise_set + 1:04}.srt"
        output_srt: str = os.path.join(srt_out_dir, srt_name)
        with open(output_srt, "w") as srt:
            for srt_entry in srt_entries:
                srt_text: str = unicodedata.normalize("NFC", str(srt_entry))
                srt.write(srt_text)

        # Output New Vocabulary, Hidden Vocabulary, and Review Vocabulary lists
        vocab_name: str = f"{dataset}-{_exercise_set + 1:04}-vocab-new.txt"
        output_vocab: str = os.path.join(vocab_out_dir, vocab_name)
        with open(os.path.join(output_vocab), "w") as w:
            for entry in new_cards:
                w.write(f"{entry}\n")
            if end_note:
                w.write(f"# {end_note}\n")
        vocab_name: str = f"{dataset}-{_exercise_set + 1:04}-vocab-hidden.txt"
        output_vocab: str = os.path.join(vocab_out_dir, vocab_name)
        with open(os.path.join(output_vocab), "w") as w:
            for entry in hidden_cards:
                w.write(f"{entry}\n")
            if end_note:
                w.write(f"# {end_note}\n")
        vocab_name: str = f"{dataset}-{_exercise_set + 1:04}-vocab-review.txt"
        output_vocab: str = os.path.join(vocab_out_dir, vocab_name)
        with open(os.path.join(output_vocab), "w") as w:
            for entry in review_cards:
                w.write(f"{entry}\n")
            if end_note:
                w.write(f"# {end_note}\n")

        # Output mp3
        mp3_name: str = f"{dataset}-{_exercise_set + 1:04}.mp3"
        output_mp3: str = os.path.join(mp3_out_dir, mp3_name)
        minutes: int = int(combined_audio.duration_seconds // 60)
        seconds: int = int(combined_audio.duration_seconds) % 60
        tags["duration"] = f"{minutes:02d}:{seconds:02d}"
        print(f"Creating {mp3_name}. {tags['duration']}.")
        save_title = tags["title"]
        if tags["album"]:
            tags["title"] = tags["title"] + " (" + tags["album"] + ")"
        combined_audio.set_frame_rate(MP3_HZ).export(output_mp3 + ".tmp", format="mp3",
                                                     parameters=["-qscale:a", str(MP3_QUALITY)], tags=tags)
        tags["title"] = save_title
        shutil.move(output_mp3 + ".tmp", output_mp3)

        # Generate graphic for MP4
        svg_title: str
        with open("cherokee-vocab-data/svg/title_template.svg", "r") as r:
            svg_title = r.read()
        svg_title = svg_title.replace("_album_", tags["album"])
        title = tags["title"]
        if "]" in title:
            svg_title = svg_title.replace("_title1_", title[:title.index("]") + 1].strip())
            svg_title = svg_title.replace("_title2_", title[title.index("]") + 1:].strip())
        else:
            svg_title = svg_title.replace("_title1_", tags["title"])
            svg_title = svg_title.replace("_title2_", " ")
        svg_title = svg_title.replace("_artist_", tags["artist"])

        if end_note:
            svg_title = svg_title.replace("_end_note_", end_note)
        else:
            svg_title = svg_title.replace("_end_note_", " ")

        new_items: str = f"{introduced_count + hidden_count:,}"
        old_items: str = f"{review_count:,}"
        svg_title = svg_title.replace("_new_", new_items)
        svg_title = svg_title.replace("_old_", old_items)

        svg_name: str = f"{dataset}-{_exercise_set + 1:04}.svg"
        print(f"Creating {svg_name}.")
        output_svg: str = os.path.join(img_out_dir, svg_name)
        with open(output_svg, "w") as w:
            w.write(svg_title)
        png_name: str = f"{dataset}-{_exercise_set + 1:04}.png"
        output_png: str = os.path.join(img_out_dir, png_name)
        cmd: list[str] = list()
        cmd.append("inkscape")
        cmd.append("-o")
        cmd.append(output_png)
        cmd.append("-C")
        cmd.append("--export-background=white")
        cmd.append("--export-background-opacity=1.0")
        cmd.append("--export-png-color-mode=RGB_16")
        cmd.append("--export-area-page")
        cmd.append(output_svg)
        print(f"Creating {png_name}.")
        subprocess.run(cmd, check=True, stdout=subprocess.DEVNULL, stderr=subprocess.STDOUT)

        if cfg.create_mp4:
            mp4_name: str = f"{dataset}-{_exercise_set + 1:04}.mp4"
            output_mp4: str = os.path.join(mp4_out_dir, mp4_name)

            cmd: list[str] = list()
            cmd.append("ffmpeg")
            cmd.append("-nostdin")  # non-interactive
            cmd.append("-y")  # overwrite
            cmd.append("-r")  # input frame rate
            cmd.append("1")
            cmd.append("-loop")
            cmd.append("1")
            cmd.append("-i")
            cmd.append(output_png)
            cmd.append("-i")
            cmd.append(output_mp3)
            cmd.append("-shortest")
            cmd.append("-q:a")
            cmd.append("3")
            cmd.append("-pix_fmt")
            cmd.append("yuv420p")
            cmd.append("-r")  # output frame rate
            cmd.append("23.976")
            cmd.append("-x264-params")
            cmd.append(f"keyint={int(23.976*3600+1)}:scenecut=0")
            cmd.append("-tune")
            cmd.append("stillimage")
            cmd.append("-movflags")
            cmd.append("+faststart")

            cmd.append(output_mp4+".tmp.mp4")

            print(f"Creating {mp4_name}.")
            subprocess.run(cmd, check=True, stdout=subprocess.DEVNULL, stderr=subprocess.STDOUT)

            cmd = list()
            cmd.append("ffmpeg")
            cmd.append("-nostdin")  # non-interactive
            cmd.append("-y")  # overwrite
            cmd.append("-i")
            cmd.append(output_mp4+".tmp.mp4")
            cmd.append("-i")
            cmd.append(output_srt)
            cmd.append("-c")
            cmd.append("copy")
            cmd.append("-c:s")
            cmd.append("mov_text")
            mp4_tags: dict[str, str] = tags.copy()
            if mp4_tags["album"]:
                mp4_tags["title"] = mp4_tags["title"] + " (" + mp4_tags["album"] + ")"
            for k, v in mp4_tags.items():
                cmd.append("-metadata")
                cmd.append(f"{k}={v}")
            cmd.append("-movflags")
            cmd.append("+faststart")
            cmd.append(output_mp4)

            print(f"Adding subtitles to {mp4_name}.")
            subprocess.run(cmd, check=True, stdout=subprocess.DEVNULL, stderr=subprocess.STDOUT)
            os.unlink(output_mp4+".tmp.mp4")

        # Bump counter
        _exercise_set += 1

        # Free up memory
        del lead_in
        del lead_out
        del main_audio
        del combined_audio
        del svg_title

        if not main_deck.has_cards:
            keep_going = extra_sessions > 0
            extra_sessions -= 1

    info_out_dir: str = os.path.join(out_dir, "info")
    os.makedirs(info_out_dir, exist_ok=True)

    with open(os.path.join(info_out_dir, "end-notes.txt"), "w") as w:
        for _ in range(_exercise_set):
            if _ not in end_notes_by_track:
                continue
            end_note = end_notes_by_track[_]
            w.write(f"{_ + 1:04d}: {end_note}\n")

    with open(os.path.join(info_out_dir, "track-info.txt"), "w") as w:
        for _ in range(_exercise_set):
            if _ not in metadata_by_track:
                continue
            metadata = metadata_by_track[_]
            w.write(f"{_ + 1:04d}|{metadata['date']}|{metadata['title']}|{metadata['album']}|{metadata['duration']}\n")

    with open(os.path.join(info_out_dir, "track-info.json"), "w") as w:
        simplejson.dump(metadata_by_track, w, indent=2, sort_keys=True, ensure_ascii=False)
        w.write("\n")

    save_deck(finished_deck, pathlib.Path("decks", f"{dataset}.json"))


def append_translate_phrase(main_audio, prompts, _exercise_set, challenge_count):
    if challenge_count < 16 and _exercise_set == 0:
        main_audio = main_audio.append(prompts["translate"])
    else:
        main_audio = main_audio.append(prompts["translate_short"])
    main_audio = main_audio.append(AudioSegment.silent(1_000))
    return main_audio


def append_introduce_phrase(main_audio, prompts, _exercise_set, new_count):
    if new_count < 6 and _exercise_set == 0:
        if new_count == 1:
            first_new_phrase = prompts["first_phrase"]
            main_audio = main_audio.append(first_new_phrase)
        else:
            main_audio = main_audio.append(prompts["new_phrase"])
    else:
        main_audio = main_audio.append(prompts["new_phrase_short"])
    main_audio = main_audio.append(AudioSegment.silent(750))
    return main_audio


def load_config(dataset: str):
    global cfg
    os.makedirs("configs", exist_ok=True)
    cfg_file: str = f"configs/{dataset}-cfg.json"
    if os.path.exists(cfg_file):
        with open(cfg_file, "r") as f:
            cfg = Config.load(f)
    else:
        cfg = Config()
        with open(cfg_file, "w") as w:
            Config.save(w, cfg)


review_count: int = 0
max_new_reached: bool = False


def scan_for_cards_to_show_again() -> None:
    # Scan for cards to show again
    for card in discards_deck.cards.copy():
        if card.card_stats.show_again_delay > 0:
            continue
        active_deck.append(card)


def next_card(exercise_set: int, prev_card_id: str) -> AudioCard | None:
    global cfg, review_count
    bump_completed()
    if active_deck.has_cards:
        card = active_deck.top_card
        discards_deck.append(card)
        if card.data.card_id != prev_card_id:
            card_stats = card.card_stats
            card_stats.tries_remaining_dec()
            card_stats.shown += 1
            return card
        if active_deck.has_cards:
            return next_card(exercise_set, prev_card_id)

    if finished_deck.next_show_time <= 0 and finished_deck.has_cards and review_count < max_review_cards_this_session:
        review_count += 1
        review_card: AudioCard = finished_deck.top_card
        card_stats = review_card.card_stats
        card_stats.new_card = False
        review_card.reset_stats()
        tries_left: int = max(cfg.review_card_max_tries // 2,
                              cfg.review_card_max_tries - cfg.review_card_tries_decrement * exercise_set)
        review_card.reset_tries_remaining(tries_left)
        discards_deck.append(review_card)
        print(f"Review card: {review_card.data.challenge} [{review_card.card_stats.tries_remaining:,d}]")
        return review_card

    extra_delay: float = discards_deck.next_show_time
    discards_deck.update_time(extra_delay)
    scan_for_cards_to_show_again()

    if not max_new_reached and main_deck.has_cards:
        new_card = main_deck.top_card
        new_card.card_stats.new_card = True
        # check to see if "new" state should be ignored
        new_card.reset_tries_remaining(  #
                max(cfg.new_card_max_tries // 2,  #
                    cfg.new_card_max_tries - cfg.new_card_tries_decrement * exercise_set))
        discards_deck.append(new_card)
        return new_card
    if not active_deck.has_cards:
        print(" - Active deck is out of cards.")
        return None
    active_deck.sort_by_show_again()
    card = active_deck.top_card
    discards_deck.append(card)
    card.card_stats.show_again_delay = extra_delay
    card.card_stats.tries_remaining_dec()
    card.card_stats.shown += 1
    return card


def bump_completed() -> None:
    global discards_deck, finished_deck
    util: CardUtils = CardUtils()
    for card in discards_deck.cards.copy():
        card_stats = card.card_stats
        if card_stats.tries_remaining < 1:
            leitner_box: int = card_stats.leitner_box
            next_session_delay: float = util.next_session_interval_secs(leitner_box)
            card_stats.show_again_delay = next_session_delay
            card_stats.leitner_box_inc()
            finished_deck.append(card)


if __name__ == "__main__":
    main()
