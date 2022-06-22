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
from pydub import effects
from pydub.effects import normalize
from random import Random
from tqdm import tqdm

from CardUtils import CardUtils
from LeitnerAudioDeck import AudioCard
from LeitnerAudioDeck import AudioData
from LeitnerAudioDeck import LeitnerAudioDeck
from config import Config

DATASET: str = "cll1-v3"

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

cfg: Config | None = None


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
                raise Exception(f"Wrong field count of {len(fields)}. Should be {IX_ENGLISH + 1}.")
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
            gender: str = fields[IX_GENDER].strip()
            if gender:
                gender = gender.strip().lower()[0]
                if gender.lower() != "m" and gender.lower() != "f":
                    print(f"BAD GENDER: {fields}")
                    gender = ""

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
            if re.search("(?i), it\\b", english_text):
                english_text = re.sub("(?i), it\\b", " or it", english_text)
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
                to_en_data.sex = gender
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
    return effects.normalize(AudioSegment.from_file(mp3_file))


def get_mp3_en(voice: str | None, text_en: str) -> str:
    text_en = re.sub("\\s+", " ", text_en).strip()
    mp3_name_en: str = get_filename(voice, text_en)
    mp3_en: str = os.path.join(CACHE_EN, mp3_name_en)
    return mp3_en


def tts_en_audio(voice: str | None, text_en: str) -> AudioSegment:
    mp3_file = get_mp3_en(voice, text_en)
    return effects.normalize(AudioSegment.from_file(mp3_file))


def fix_english_sex_genders(text_en) -> str:
    tmp: str = re.sub("\\s+", " ", text_en).strip()
    if "brother" in tmp.lower():
        return text_en
    if "sister" in tmp.lower():
        return text_en
    if "himself" in tmp:
        tmp = re.sub("(?i)(He )", "\\1 or she ", tmp)
        tmp = re.sub("(?i)( himself)", "\\1 or herself", tmp)
    if "Himself" in tmp:
        tmp = re.sub("(?i)\\b(He )", "\\1or she ", tmp)
        tmp = re.sub("(?i)\\b(Himself)", "\\1 or herself", tmp)
    if re.search(".*\\b[Hh]is\\b.*", tmp):
        tmp = re.sub("(?i)\\b(His)", "\\1 or her", tmp)
    if " or she" not in tmp:
        tmp = re.sub("(?i)\\b(He )", "\\1or she ", tmp)
    if " or her" not in tmp:
        tmp = re.sub("(?i)( him)", "\\1 or her", tmp)
    tmp = re.sub("(?i)x(he|she|him|her|his)", "\\1", tmp)
    return tmp


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
    _ = unicodedata.normalize("NFC", re.sub("[^a-z_]", "", _))
    if len(_) > 32:
        _ = _[:32]
    mp3_name_chr: str = f"{_}_{voice}_{sha1}.mp3"
    return mp3_name_chr


def create_prompts() -> dict[str, AudioSegment]:
    print("Creating instructor prompts")
    prompts: dict[str, AudioSegment] = dict()
    voice: str = AMZ_VOICE_INSTRUCTOR

    tag: str = "produced"
    text: str = f"""
    This audio file was produced on
    {datetime.today().strftime("%B %d, %Y")}
    by Michael Conrad."
    """
    tts_en(voice, text)
    prompts[tag] = tts_en_audio(voice, text)

    tag: str = "first_phrase"
    text: str = "Here is your first phrase to learn for this session. Listen carefully:"
    tts_en(voice, text)
    prompts[tag] = tts_en_audio(voice, text)

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

    tag = "cll1-v3"
    text = "Cherokee Language Lessons 1. 3rd Edition."
    tts_en(voice, text)
    prompts[tag] = tts_en_audio(voice, text)

    tag = "bound-pronouns"
    text = "Bound Pronouns Training."
    tts_en(voice, text)
    prompts[tag] = tts_en_audio(voice, text)

    tag = "ced-mco"
    text = "Cherokee English Dictionary Vocabulary Cram."
    tts_en(voice, text)
    prompts[tag] = tts_en_audio(voice, text)

    tag = "osiyo-tohiju-then-what-mco"
    text = "Conversation Starters in Cherokee."
    tts_en(voice, text)
    prompts[tag] = tts_en_audio(voice, text)

    tag = "wwacc"
    text = "Advanced Conversational Cherokee."
    tts_en(voice, text)
    prompts[tag] = tts_en_audio(voice, text)

    tag = "walc-1"
    text = "We are learning Cherokee - Book 1."
    tts_en(voice, text)
    prompts[tag] = tts_en_audio(voice, text)

    tag = "animals-mco"
    text = "Cherokee animal names."
    tts_en(voice, text)
    prompts[tag] = tts_en_audio(voice, text)

    tag = "cll1-v3-about"
    text = """
    These audio excercise sessions complement the book 'Cherokee Language Lessons 1', 3rd Edition, by Michael Conrad.
    Each chapter indicates which audio excercise sessions
    should be completed before beginning that chapter.
    By the time you complete the assigned sessions, you will have
    little to no difficulty with reading the Cherokee in the chapter text.
    """
    tts_en(voice, text)
    prompts[tag] = tts_en_audio(voice, text)

    tag = "bound-pronouns-about"
    text = """
    These sessions closely follow the vocabulary from the Bound Pronouns app.
    These exercises are designed to assist
    with learning the different singular
    and plural bound pronoun combinations.
    """
    tts_en(voice, text)
    prompts[tag] = tts_en_audio(voice, text)

    tag = "two-men-hunting-about"
    text = """
    These sessions closely follow the vocabulary from the story entitled, 'Two Hunters',
    as recorded in the Cherokee English Dictionary, 1st edition.
    By the time you have completed these exercises you should be able to understand
    the full spoken story without any difficulty.
    """
    tts_en(voice, text)
    prompts[tag] = tts_en_audio(voice, text)

    tag = "ced-mco-about"
    text = """
    These sessions use vocabulary taken from the Cherokee English Dictionary, 1st Edition.
    The pronunciations are based on the pronunciation markings as found in the dictionary.
    """
    tts_en(voice, text)
    prompts[tag] = tts_en_audio(voice, text)

    tag = "osiyo-tohiju-then-what-mco-about"
    text = """
    These sessions closely follow the book entitled, 'Conversation Starters in Cherokee', by Prentice Robinson.
    The pronunciations are based on the pronunciation markings as found in the official
    Cherokee English Dictionary - 1st Edition.
    """
    tts_en(voice, text)
    prompts[tag] = tts_en_audio(voice, text)

    tag = "wwacc-about"
    text = """
    These sessions closely follow the booklet entitled, 'Advanced Conversational Cherokee', by Willard Walker.
    """
    tts_en(voice, text)
    prompts[tag] = tts_en_audio(voice, text)

    tag = "walc-1-about"
    text = """
    These sessions closely follow the lesson material 'We are learning Cherokee - Book 1'.
    """
    tts_en(voice, text)
    prompts[tag] = tts_en_audio(voice, text)

    tag = "animals-mco-about"
    text = """
    These sessions closely follow the vocabulary from the Animals app.
    """
    tts_en(voice, text)
    prompts[tag] = tts_en_audio(voice, text)

    return prompts


vstem_counts: dict[str, int] = dict()
pbound_counts: dict[str, int] = dict()


def save_stem_counts(finished_deck) -> None:
    global vstem_counts, pbound_counts
    vstem_counts.clear()
    pbound_counts.clear()
    for card in finished_deck.cards:
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


def main() -> None:
    global cfg, max_new_reached, review_count
    global main_deck, discards_deck, finished_deck, active_deck
    util: CardUtils = CardUtils()
    os.chdir(os.path.dirname(__file__))
    print(os.getcwd())

    main_deck = load_main_deck(DATASET + ".txt")
    create_card_audio(main_deck)
    prompts = create_prompts()

    with open("walc1/walc1.json", "r") as f:
        cfg = Config.load(f)

    temp_dir: str = os.path.join(cfg.data_dir, "temp")
    out_dir: str = os.path.join(cfg.data_dir, "output")
    challenges_file: str = os.path.join(cfg.data_dir, "challenges.txt")

    _exercise_set: int = 0
    keep_going: bool = cfg.create_all_sessions
    new_vocab_all_sessions: list = []

    prev_card_id: str = ""

    while _exercise_set < cfg.sessions_to_create or keep_going:
        if _exercise_set > 0:
            new_vocab_all_sessions.append("")
            new_vocab_all_sessions.append("")
            print()
            print()

        new_vocab_all_sessions.append(f"=== SESSION: {_exercise_set+1:04}")
        new_vocab_all_sessions.append("")

        print(f"=== SESSION: {_exercise_set+1:04}")
        print()

        lead_in: AudioSegment = AudioSegment.silent(1_000, LESSON_HZ).set_channels(1)

        # Exercise set title
        lead_in = lead_in.append(prompts[DATASET])
        lead_in = lead_in.append(AudioSegment.silent(1_000))

        if _exercise_set == 0:
            # Description of exercise set
            if DATASET + "-about" in prompts:
                lead_in = lead_in.append(prompts[DATASET + "-about"])
                lead_in = lead_in.append(AudioSegment.silent(1_000))

            # Pre-lesson verbiage
            lead_in = lead_in.append(prompts["language_culture_1"])
            lead_in = lead_in.append(AudioSegment.silent(2_000))

            lead_in = lead_in.append(prompts["keep_going"])
            lead_in = lead_in.append(AudioSegment.silent(2_000))

            lead_in = lead_in.append(prompts["learn_sounds_first"])
            lead_in = lead_in.append(AudioSegment.silent(3_000))

            lead_in = lead_in.append(prompts["intro_2"])
            lead_in = lead_in.append(AudioSegment.silent(2_000))

            # Let us begin
            lead_in = lead_in.append(prompts["begin"])
            lead_in = lead_in.append(AudioSegment.silent(1_000))

        session_start: str = f"Session {_exercise_set + 1}."
        tts_en(AMZ_VOICE_INSTRUCTOR, session_start)
        lead_in = lead_in.append(tts_en_audio(AMZ_VOICE_INSTRUCTOR, session_start))
        lead_in = lead_in.append(AudioSegment.silent(1_000))

        lead_out: AudioSegment = AudioSegment.silent(3_000, LESSON_HZ).set_channels(1)
        lead_out = lead_out.append(prompts["concludes_this_exercise"])
        lead_out = lead_out.append(AudioSegment.silent(3_000))
        lead_out = lead_out.append(prompts["copy_1"])
        lead_out = lead_out.append(AudioSegment.silent(2_000))
        lead_out = lead_out.append(prompts["copy_by_sa"])
        lead_out = lead_out.append(AudioSegment.silent(3_000))
        lead_out = lead_out.append(prompts["produced"])
        lead_out = lead_out.append(AudioSegment.silent(3_000))

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

        while lead_in.duration_seconds + lead_out.duration_seconds + main_audio.duration_seconds < cfg.session_max_duration:
            start_length: float = main_audio.duration_seconds
            card: AudioCard = next_card(_exercise_set, prev_card_id)
            if not card:
                break
            if keep_going:
                keep_going = main_deck.has_cards  # todo: add 2 extra sessions
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
                if introduce_card:
                    print(f"Introduced card: {data.challenge} [{card_stats.tries_remaining:,}]")
                else:
                    card_stats.new_card = False
                    card.reset_tries_remaining(max(cfg.review_card_max_tries // 2,  #
                                                   cfg.review_card_max_tries  #
                                                   - cfg.review_card_tries_decrement  #
                                                   * _exercise_set))
                    print(f"Hidden new card: {data.challenge} [{card_stats.tries_remaining:,}]")
            if new_card:
                if introduce_card:
                    introduced_count += 1
                else:
                    hidden_count += 1
                new_count += 1
                if new_count >= max_new_cards_this_session:
                    max_new_reached = True
                main_audio = main_audio.append(AudioSegment.silent(2_000))
                card_stats.new_card = False
                if new_count < 6 and _exercise_set == 0:
                    if new_count == 1:
                        first_new_phrase = prompts["first_phrase"]
                        main_audio = main_audio.append(first_new_phrase)
                    else:
                        main_audio = main_audio.append(prompts["new_phrase"])
                else:
                    main_audio = main_audio.append(prompts["new_phrase_short"])
                main_audio = main_audio.append(AudioSegment.silent(1_000))
            else:
                challenge_count += 1
                if extra_delay > 0:
                    _: int = int(1_000 * min(7.0, extra_delay))
                    main_audio = main_audio.append(AudioSegment.silent(_), crossfade=0)
                if challenge_count < 16 and _exercise_set == 0:
                    main_audio = main_audio.append(prompts["translate"])
                else:
                    main_audio = main_audio.append(prompts["translate_short"])
                main_audio = main_audio.append(AudioSegment.silent(1_000))
            data_file: AudioSegment = tts_chr_audio(next_ims_voice(data.sex), data.challenge)
            main_audio = main_audio.append(data_file)
            if introduce_card:
                data_file: AudioSegment = tts_chr_audio(next_ims_voice(data.sex), data.challenge)
                main_audio = main_audio.append(AudioSegment.silent(2_000))
                if new_count < 8 and _exercise_set == 0:
                    main_audio = main_audio.append(prompts["listen_again"])
                else:
                    main_audio = main_audio.append(prompts["listen_again_short"])
                main_audio = main_audio.append(AudioSegment.silent(2_000))
                main_audio = main_audio.append(data_file)
                main_audio = main_audio.append(AudioSegment.silent(2_000))
                if new_count < 10 and _exercise_set == 0:
                    main_audio = main_audio.append(prompts["its_translation_is"])
                    main_audio = main_audio.append(AudioSegment.silent(1_000))
                else:
                    main_audio = main_audio.append(prompts["in_english"])
                    main_audio = main_audio.append(AudioSegment.silent(1_000))
            else:
                gap_duration: float = data_file.duration_seconds
                main_audio = main_audio.append(AudioSegment.silent(int(1_000 * gap_duration)))

            # The answer
            answer_audio: AudioSegment = tts_en_audio(next_amz_voice(data.sex), data.answer)
            main_audio = main_audio.append(answer_audio)
            if _exercise_set == 0:
                main_audio = main_audio.append(AudioSegment.silent(3_000))
            elif _exercise_set < 5:
                main_audio = main_audio.append(AudioSegment.silent(2_000))
            else:
                main_audio = main_audio.append(AudioSegment.silent(1_000))

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
        print(f"New cards: {new_count}. Review cards: {review_count}.")

        # Output exercise audio
        combined_audio: AudioSegment = lead_in.append(main_audio)
        combined_audio = combined_audio.append(lead_out)
        output_mp3: str = f"output-{_exercise_set + 1:04}.mp3"
        minutes: int = int(combined_audio.duration_seconds // 60)
        seconds: int = int(combined_audio.duration_seconds) % 60
        print(f"Creating {output_mp3}. {minutes:02d}:{seconds:02d}.")
        combined_audio.export(output_mp3, format="mp3")

        # Bump counter
        _exercise_set += 1

        # Free up memory
        del lead_in
        del lead_out
        del main_audio
        del combined_audio


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

    if finished_deck.next_show_time <= 0 and finished_deck.has_cards \
            and review_count < cfg.review_cards_max_per_session:
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
