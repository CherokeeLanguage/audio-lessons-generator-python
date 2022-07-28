
import unicodedata
import re
import pathlib
import os

import jsonpickle

from LeitnerAudioDeck import AudioCard, AudioData, LeitnerAudioDeck
from column_names import IX_ALT_PRONOUNCE, IX_PRONOUN, IX_VERB, IX_GENDER, IX_SYLLABARY, IX_PRONOUNCE, IX_ENGLISH, IX_INTRO_NOTE, IX_END_NOTE, IX_APP_FILE

UNDERDOT: str = "\u0323"

def save_deck(deck: LeitnerAudioDeck, destination: pathlib.Path):

    jsonpickle.load_backend('simplejson', 'dumps', 'loads', ValueError)
    jsonpickle.set_preferred_backend('simplejson')
    jsonpickle.set_encoder_options('simplejson', ensure_ascii=False)

    if not os.path.exists(destination.parent):
        destination.parent.mkdir(exist_ok=True)
    with open(destination, "w") as w:
        w.write(jsonpickle.dumps(deck, indent=2))
        w.write("\n")

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
            if cherokee_text.startswith("#"):
                continue
            if not re.sub("(?i)[^a-z]", "", unicodedata.normalize("NFD", cherokee_text)):
                print(f"Warning - no Cherokee text: {line}")
                continue

            if ";" in cherokee_text:
                for text in cherokee_text.split(";"):
                    text = text.strip()
                    if text and text not in cherokee_text_alts:
                        cherokee_text_alts.append(text)
                cherokee_text = cherokee_text[0:cherokee_text.index(";")].strip()

            cherokee_text = cherokee_text[0].upper() + cherokee_text[1:]
            if cherokee_text[-1] not in ",.?!":
                cherokee_text += "."
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
            if "v.t." in english_text or "v.i." in english_text:
                english_text = english_text.replace("v.t.", "").replace("v.i.", "")
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
                    if not alt or alt in to_en_data.challenge_alts:
                        continue
                    to_en_data.challenge_alts.append(alt)
                for alt in cherokee_text_alts:
                    alt = alt.strip()
                    if not alt or alt in to_en_data.challenge_alts:
                        continue
                    to_en_data.challenge_alts.append(alt)

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
