import unicodedata

import re

import boto3
import os
from boto3_type_annotations.polly import Client as Polly
from pydub import AudioSegment

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
                english_text = english_text.replace(" (1)", " one")
                english_text = english_text.replace(" (animate)", ", animate")
                english_text = english_text.replace(" (inanimate)", ", inanimate")
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


def main() -> None:
    os.chdir(os.path.dirname(__file__))
    print(os.getcwd())

    main_deck: LeitnerAudioDeck = load_main_deck("bound-pronouns.txt")
    discards_deck: LeitnerAudioDeck = LeitnerAudioDeck()
    finished_deck: LeitnerAudioDeck = LeitnerAudioDeck()
    active_deck: LeitnerAudioDeck = LeitnerAudioDeck()

    hz: int = 22050
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

        lead_in: AudioSegment = AudioSegment.silent(0, hz)
        main_audio: AudioSegment = AudioSegment.silent(0, hz)
        lead_out: AudioSegment = AudioSegment.silent(0, hz)
        prev_card_id: str = ""

        polly_client: Polly = boto3.Session().client("polly")
        response = polly_client.synthesize_speech(OutputFormat="mp3",  #
                                                  Text="Sample synthesize.",  #
                                                  VoiceId="Joanna",  #
                                                  SampleRate=str(hz),  #
                                                  LanguageCode="en-US",
                                                  Engine="neural")
        with open("test.mp3", "wb") as w:
            w.write(response["AudioStream"].read())

        # main_audio.append(AudioSegment.from_file(""))

        _exercise_set += 1
        break
    pass


if __name__ == "__main__":
    main()
