#!/usr/bin/env bash
"""true" '''\'
set -e
eval "$(${CONDA_EXE:-conda} shell.bash hook)"
conda activate audio-lessons
exec python "$0" "$@"
exit $?
''"""
from __future__ import annotations

from datetime import datetime

import textwrap
import boto3
import hashlib
import os
import re
import subprocess
import unicodedata
from boto3_type_annotations.polly import Client as Polly
from pydub import AudioSegment
from random import Random
from tqdm import tqdm

from LeitnerAudioDeck import AudioCard
from LeitnerAudioDeck import AudioData
from LeitnerAudioDeck import LeitnerAudioDeck
from config import Config

IX_PRONOUN: int = 3
IX_VERB: int = 4
IX_GENDER: int = 5
IX_SYLLABARY: int = 6
IX_PRONOUNCE: int = 7
IX_ENGLISH: int = 8

UNDERDOT: str = "\u0323"

auto_split_cherokee: bool = True

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

AMZ_VOICE_INSTRUCTOR: str = "Matthew"
AMZ_HZ: str = "24000"

LESSON_HZ: int = 48_000

rand: Random = Random(1234)
previous_voice: str = ""
amz_previous_voice: str = ""


def next_ims_voice(gender: str = "") -> str:
    """Utility function to return a different non-repeated voice name based on gender"""
    global IMS_VOICES_FEMALE, IMS_VOICES_MALE, rand
    global previous_voice, ims_voices
    if not ims_voices:
        ims_voices.extend(IMS_VOICES_MALE)
        ims_voices.extend(IMS_VOICES_FEMALE)
        rand.shuffle(ims_voices)
    voice: str = ims_voices.pop(0)
    if gender:
        gender = gender.strip().lower()[0]
        if gender == "m" and len(IMS_VOICES_MALE) < 2:
            previous_voice = ""
        if gender == "f" and len(IMS_VOICES_FEMALE) < 2:
            previous_voice = ""
        if gender == "m" and voice not in IMS_VOICES_MALE:
            return next_ims_voice(gender)
        if voice not in IMS_VOICES_FEMALE:
            return next_ims_voice(gender)
    if voice == previous_voice:
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
    voice: str = amz_voices.pop(0)
    if gender:
        gender = gender.strip().lower()[0]
        if gender == "m" and len(AMZ_VOICES_MALE) < 2:
            amz_previous_voice = ""
        if gender == "f" and len(AMZ_VOICES_FEMALE) < 2:
            amz_previous_voice = ""
        if gender == "m" and voice not in AMZ_VOICES_MALE:
            return next_amz_voice(gender)
        if voice not in IMS_VOICES_FEMALE:
            return next_amz_voice(gender)
    if voice == amz_previous_voice:
        return next_amz_voice(gender)
    amz_previous_voice = voice
    return voice


def load_main_deck(source_file: str) -> LeitnerAudioDeck:
    chr2en_deck: LeitnerAudioDeck = LeitnerAudioDeck()
    dupe_pronunciation_check: set[str] = set()
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
            if len(fields) < IX_ENGLISH + 1 or len(fields) > IX_ENGLISH + 2:
                print(f"; {line}")
                raise Exception(f"Wrong field count of {len(fields)}. Should be {IX_ENGLISH+1}.")
            skip_as_new = "*" in fields[0]

            verb_stem: str = unicodedata.normalize("NFD", fields[IX_VERB])
            verb_stem = re.sub("[¹²³⁴" + UNDERDOT + "]", "", verb_stem)
            verb_stem = unicodedata.normalize("NFC", verb_stem)

            bound_pronoun: str = unicodedata.normalize("NFD", fields[IX_PRONOUN])
            bound_pronoun = re.sub("[¹²³⁴" + UNDERDOT + "]", "", bound_pronoun)
            bound_pronoun = unicodedata.normalize("NFC", bound_pronoun)

            cherokee_text = fields[IX_PRONOUNCE].strip()
            if not cherokee_text:
                continue
            if cherokee_text.startswith("#"):
                continue
            if "," in cherokee_text and auto_split_cherokee:
                cherokee_text = cherokee_text[0:cherokee_text.index(",")]
            cherokee_text = cherokee_text[0].upper() + cherokee_text[1:]
            if cherokee_text[-1] not in ",.?!":
                cherokee_text += "."
            # check_text = re.sub("(?i)[.,!?;]", "", cherokee_text).strip()
            # if check_text in dupe_pronunciation_check:
            #     raise Exception(f"DUPLICATE PRONUNCIATION: ({line_no:,}) {check_text}\n{fields}")
            # dupe_pronunciation_check.add(check_text)
            sex: str = fields[IX_GENDER].strip()
            english_text = fields[IX_ENGLISH].strip()
            if not english_text:
                continue
            if ";" in english_text:
                english_text = english_text.replace(";", ", Or, ")
            if english_text[-1] not in ",.?!":
                english_text += "."
            if "v.t." in english_text or "v.i." in english_text:
                english_text = english_text.replace("v.t.", "").replace("v.i.", "")
            if "1." in english_text:
                english_text = english_text.replace("1.", "")
                english_text = english_text.replace("2.", ". Or, ")
                english_text = english_text.replace("3.", ". Or, ")
                english_text = english_text.replace("4.", ". Or, ")
            if "(" in english_text:
                # english_text = english_text.replace(" (1)", " one")
                english_text = english_text.replace(" (1)", "")
                english_text = english_text.replace(" (animate)", ", living, ")
                english_text = english_text.replace(" (inanimate)", ", non-living, ")
            if "/" in english_text:
                english_text = english_text.replace("/", " or ")
            if re.match(", it\\b", english_text):
                english_text = re.sub(", it\\b", " or it", english_text)
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

            to_en_card: AudioCard
            to_en_data: AudioData

            if cherokee_text in cards_for_english_answers:
                to_en_card = cards_for_english_answers[cherokee_text]
                to_en_data = to_en_card.data
                to_en_data.answer += " Or, " + english_text
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
                to_en_data.sex = sex
                if skip_as_new:
                    to_en_data.bound_pronoun = "*"
                    to_en_data.verb_stem = "*"
                cards_for_english_answers[cherokee_text] = to_en_card
                syllabary: str = fields[IX_SYLLABARY]
                to_en_data.sort_key = syllabary if syllabary else cherokee_text
                chr2en_deck.append(to_en_card)

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


def tts_chr(voice: str | None, text_chr: str):
    mp3_name_chr: str = get_filename(voice, text_chr)
    mp3_chr: str = os.path.join(CACHE_CHR, mp3_name_chr)
    if os.path.exists(mp3_chr):
        return
    cmd: list[str] = list()
    cmd.append(os.path.expanduser("~/git/IMS-Toucan/run_tts.py"))
    cmd.append("--lang")
    cmd.append("chr")
    if voice:
        cmd.append("--ref")
        cmd.append(os.path.realpath(os.path.join("ref", f"{voice}.wav")))
    cmd.append("--mp3")
    cmd.append(mp3_chr)
    cmd.append("--text")
    cmd.append(text_chr)
    result = subprocess.run(cmd, capture_output=True)
    if result.returncode:
        print(result.stdout.decode())
        print(result.stderr.decode())
        raise Exception("run_tts.py fail")


def get_mp3_chr(voice: str | None, text_chr: str) -> str:
    text_chr = re.sub("\\s+", " ", textwrap.dedent(text_chr)).strip()
    mp3_name_chr: str = get_filename(voice, text_chr)
    mp3_chr: str = os.path.join(CACHE_CHR, mp3_name_chr)
    return mp3_chr


def tts_chr_audio(voice: str | None, text_chr: str) -> AudioSegment:
    mp3_file = get_mp3_chr(voice, text_chr)
    return AudioSegment.from_file(mp3_file)


def get_mp3_en(voice: str | None, text_en: str) -> str:
    text_en = re.sub("\\s+", " ", textwrap.dedent(text_en)).strip()
    mp3_name_en: str = get_filename(voice, text_en)
    mp3_en: str = os.path.join(CACHE_EN, mp3_name_en)
    return mp3_en


def tts_en_audio(voice: str | None, text_en: str) -> AudioSegment:
    mp3_file = get_mp3_en(voice, text_en)
    return AudioSegment.from_file(mp3_file)


def tts_en(voice: str, text_en: str):
    mp3_en = get_mp3_en(voice, text_en)
    if os.path.exists(mp3_en):
        return
    polly_client: Polly = boto3.Session().client("polly")
    response = polly_client.synthesize_speech(OutputFormat="mp3",  #
                                              Text=text_en,  #
                                              VoiceId=voice,  #
                                              SampleRate=AMZ_HZ,  #
                                              LanguageCode="en-US",  #
                                              Engine="neural")
    with open(mp3_en, "wb") as w:
        w.write(response["AudioStream"].read())


def create_card_audio(main_deck: LeitnerAudioDeck):
    os.makedirs(CACHE_CHR, exist_ok=True)
    os.makedirs(CACHE_EN, exist_ok=True)
    print("Creating card audio")
    for card in tqdm(main_deck.cards):
        data = card.data
        text_chr = data.challenge
        text_en = data.answer
        for voice in IMS_VOICES:
            tts_chr(voice, text_chr)
        for voice in AMZ_VOICES:
            tts_en(voice, text_en)


def get_filename(voice: str, text_chr: str):
    if not voice:
        voice = "-"
    sha1: str
    sha1 = hashlib.sha1(text_chr.encode("UTF-8")).hexdigest()
    _ = unicodedata.normalize("NFD", text_chr).lower().replace(" ", "_")
    if len(_) > 32:
        _ = _[:32]
    _ = unicodedata.normalize("NFC", re.sub("[^a-z_]", "", _))
    mp3_name_chr: str = f"{_}_{voice}_{sha1}.mp3"
    return mp3_name_chr


def create_prompts() -> dict[str, AudioSegment]:
    print("Creating instructor prompts")
    prompts: dict[str, AudioSegment] = dict()
    voice: str = AMZ_VOICE_INSTRUCTOR

    tag: str = "language_culture_1"
    text: str = """
    Language and culture which are not shared and taught openly and freely will die.
    If our language and culture die, then, as a people, so do we.
    """
    tts_en(voice, text)
    prompts[tag] = tts_en_audio(voice, text)

    tag = "copy_1"
    text = f"Production copyright {datetime.utcnow().year} by Michael Conrad."
    tts_en(voice, text)
    prompts[tag] = tts_en_audio(voice, text)

    tag = "copy_by_sa"
    text = f"""
    This work is licensed to you under the Creative Commons Attribution Share-Alike license.
    To obtain a copy of this license please look up Creative Commons online.
    You are free to share, copy, and distribute this work.
    If you alter, build upon, or transform this work, you must use the same license on the resulting work.
    """
    tts_en(voice, text)
    prompts[tag] = tts_en_audio(voice, text)

    tag = "copy_by_nc"
    text = f"""
    This work is licensed to you under the Creative Commons Attribution Non-Commercial license.
    To obtain a copy of this license please look up Creative Commons online.
    You are free to share and adapt this work. If you alter, build upon, or transform this work,
    you must use the same license on the resulting work.
    """
    tts_en(voice, text)
    prompts[tag] = tts_en_audio(voice, text)

    tag = "is_derived"
    text = "This is a derived work."
    tts_en(voice, text)
    prompts[tag] = tts_en_audio(voice, text)

    tag = "is_derived_cherokee_nation"
    text = """
    This is a derived work. Permission to use the original Cherokee audio and print materials for
    non-commercial use granted by "The Cherokee Nation of Oklahoma".
    """
    tts_en(voice, text)
    prompts[tag] = tts_en_audio(voice, text)

    tag = "walc1_attribution"
    text = """
    Original audio copyright 2018 by the Cherokee Nation of Oklahoma.
    The contents of the "We are Learning Cherokee Level 1" textbook were developed by Durbin Feeling,
    Patrick Rochford, Anna Sixkiller, David Crawler, John Ross, Dennis Sixkiller, Ed Fields, Edna Jones,
    Lula Elk, Lawrence Panther, Jeff Edwards, Zachary Barnes, Wade Blevins, and Roy Boney, Jr.";
    """
    tts_en(voice, text)
    prompts[tag] = tts_en_audio(voice, text)

    tag = "intro_1"
    text = """
    In these sessions, you will learn Cherokee phrases by responding with each phrase's English
    translation. Each new phrase will be introduced with it's English translation. You will then be
    prompted to translate different phrases into English. It is important to respond aloud.
    """
    tts_en(voice, text)
    prompts[tag] = tts_en_audio(voice, text)

    tag = "intro_2"
    text = """
    In these sessions, you will learn by responding aloud in English.
    Each phrase will be introduced with an English translation.
    As the sessions progress you will be prompted to translate different phrases into English.
    It is important to respond aloud.
    """
    tts_en(voice, text)
    prompts[tag] = tts_en_audio(voice, text)

    tag = "keep_going"
    text = """
    Do not become discouraged while doing these sessions.
    It is normal to have to repeat them several times.
    As you progress you will find the later sessions much easier.
    """
    tts_en(voice, text)
    prompts[tag] = tts_en_audio(voice, text)

    tag = "begin"
    text = "Let us begin."
    tts_en(voice, text)
    prompts[tag] = tts_en_audio(voice, text)

    tag = "learn_sounds_first"
    text = """
    Only after you have learned how the words in Cherokee sound and how they are used together will you
    be able to speak Cherokee. This material is designed to assist with learning these sounds and word
    combinations. This is the way young children learn their first language or languages.
    """
    tts_en(voice, text)
    prompts[tag] = tts_en_audio(voice, text)

    tag = "new_phrase"
    text = "Here is a new phrase to learn. Listen carefully:"
    tts_en(voice, text)
    prompts[tag] = tts_en_audio(voice, text)

    tag = "new_phrase_short"
    text = "Here is a new phrase:"
    tts_en(voice, text)
    prompts[tag] = tts_en_audio(voice, text)

    tag = "translate"
    text = "Translate into English:"
    tts_en(voice, text)
    prompts[tag] = tts_en_audio(voice, text)

    tag = "translate_short"
    text = "Translate:"
    tts_en(voice, text)
    prompts[tag] = tts_en_audio(voice, text)

    tag = "listen_again"
    text = "Here is the phrase again:"
    tts_en(voice, text)
    prompts[tag] = tts_en_audio(voice, text)

    tag = "listen_again_short"
    text = "Again:"
    tts_en(voice, text)
    prompts[tag] = tts_en_audio(voice, text)

    tag = "its_translation_is"
    text = "Here it is in English:"
    tts_en(voice, text)
    prompts[tag] = tts_en_audio(voice, text)

    tag = "in_english"
    text = "In English:"
    tts_en(voice, text)
    prompts[tag] = tts_en_audio(voice, text)

    tag = "concludes_this_exercise"
    text = "This concludes this audio exercise."
    tts_en(voice, text)
    prompts[tag] = tts_en_audio(voice, text)

    return prompts


def main() -> None:
    os.chdir(os.path.dirname(__file__))
    print(os.getcwd())

    main_deck: LeitnerAudioDeck = load_main_deck("animals-mco.txt")
    create_card_audio(main_deck)
    prompts = create_prompts()

    discards_deck: LeitnerAudioDeck = LeitnerAudioDeck()
    finished_deck: LeitnerAudioDeck = LeitnerAudioDeck()
    active_deck: LeitnerAudioDeck = LeitnerAudioDeck()

    cfg: Config
    with open("walc1/walc1.json", "r") as f:
        cfg = Config.load(f)

    temp_dir: str = os.path.join(cfg.data_dir, "temp")
    out_dir: str = os.path.join(cfg.data_dir, "output")
    challenges_file: str = os.path.join(cfg.data_dir, "challenges.txt")

    _exercise_set: int = 0
    keep_going: bool = cfg.create_all_sessions
    new_vocab_all_sessions: list = []

    while _exercise_set < cfg.sessions_to_create or keep_going:
        exercise_set: str = f"{_exercise_set:04d}"
        if _exercise_set > 0:
            new_vocab_all_sessions.append("")
            new_vocab_all_sessions.append("")
        new_vocab_all_sessions.append(f"=== SESSION: {exercise_set}")
        new_vocab_all_sessions.append("")

        lead_in: AudioSegment = AudioSegment.silent(0, LESSON_HZ).set_channels(1)
        main_audio: AudioSegment = AudioSegment.silent(0, LESSON_HZ).set_channels(1)
        lead_out: AudioSegment = AudioSegment.silent(0, LESSON_HZ).set_channels(1)
        prev_card_id: str = ""

        # main_audio.append(AudioSegment.from_file(""))

        _exercise_set += 1
        break
    pass


if __name__ == "__main__":
    main()
