#!/usr/bin/env bash
"""true" '''\'
set -e
eval "$(${conda_exe:-conda} shell.bash hook)"
conda activate audio-lessons
exec python "$0" "$@"
exit $?
''"""
import re
import unicodedata
from builtins import dict
from builtins import list
from builtins import str


def char_range(c1, c2):
    for c in range(ord(c1), ord(c2) + 1):
        yield chr(c)


translit2syl: dict = dict()
translit2syl_vowels: list = ["a", "e", "i", "o", "u", "v"]

for syl, vowel in zip(char_range("Ꭰ", "Ꭵ"), translit2syl_vowels):
    translit2syl[vowel] = syl

translit2syl["ga"] = "Ꭶ"
translit2syl["ka"] = "Ꭷ"

for syl, vowel in zip(char_range("Ꭸ", "Ꭼ"), translit2syl_vowels[1:]):
    translit2syl["g" + vowel] = syl
    translit2syl["k" + vowel] = syl

for syl, vowel in zip(char_range("Ꭽ", "Ꮂ"), translit2syl_vowels):
    translit2syl["h" + vowel] = syl

for syl, vowel in zip(char_range("Ꮃ", "Ꮈ"), translit2syl_vowels):
    translit2syl["l" + vowel] = syl

for syl, vowel in zip(char_range("Ꮉ", "Ꮍ"), translit2syl_vowels[:-1]):
    translit2syl["m" + vowel] = syl

translit2syl["na"] = "Ꮎ"
translit2syl["naH"] = "Ꮐ"
translit2syl["hna"] = "Ꮏ"

for syl, vowel in zip(char_range("Ꮑ", "Ꮕ"), translit2syl_vowels[1:]):
    translit2syl["n" + vowel] = syl
    translit2syl["hn" + vowel] = syl

for syl, vowel in zip(char_range("Ꮖ", "Ꮛ"), translit2syl_vowels):
    translit2syl["gw" + vowel] = syl
    translit2syl["kw" + vowel] = syl

translit2syl["sa"] = "Ꮜ"
translit2syl["s"] = "Ꮝ"

for syl, vowel in zip(char_range("Ꮞ", "Ꮢ"), translit2syl_vowels[1:]):
    translit2syl["s" + vowel] = syl

translit2syl["da"] = "Ꮣ"
translit2syl["de"] = "Ꮥ"
translit2syl["di"] = "Ꮧ"
translit2syl["do"] = "Ꮩ"
translit2syl["du"] = "Ꮪ"
translit2syl["dv"] = "Ꮫ"

translit2syl["ta"] = "Ꮤ"
translit2syl["te"] = "Ꮦ"
translit2syl["ti"] = "Ꮨ"
translit2syl["to"] = "Ꮩ"
translit2syl["tu"] = "Ꮪ"
translit2syl["tv"] = "Ꮫ"

translit2syl["dla"] = "Ꮬ"
translit2syl["tla"] = "Ꮭ"
translit2syl["hla"] = "Ꮭ"

for syl, vowel in zip(char_range("Ꮮ", "Ꮲ"), translit2syl_vowels[1:]):
    translit2syl["dl" + vowel] = syl
    translit2syl["tl" + vowel] = syl
    translit2syl["hl" + vowel] = syl

for syl, vowel in zip(char_range("Ꮳ", "Ꮸ"), translit2syl_vowels):
    translit2syl["j" + vowel] = syl
    translit2syl["z" + vowel] = syl
    translit2syl["ch" + vowel] = syl

for syl, vowel in zip(char_range("Ꮹ", "Ꮾ"), translit2syl_vowels):
    translit2syl["w" + vowel] = syl
    translit2syl["hw" + vowel] = syl

for syl, vowel in zip(char_range("Ꮿ", "Ᏼ"), translit2syl_vowels):
    translit2syl["y" + vowel] = syl
    translit2syl["hy" + vowel] = syl

translit2syl["h"] = ""  # hopefully intrusive 'h' only


# specials
key: str
for key in [*translit2syl.keys()]:
    if key.startswith("s"):
        translit2syl["ak"+key] = "ꭰꭹ" + translit2syl[key]


translit_lookup: list[str] = [*translit2syl.keys()]
translit_lookup.sort(key=lambda key: len(key), reverse=True)


def pronounce2syllabary(text: str) -> str:
    text = text.lower().strip()
    text = re.sub("(?i)[^a-z\\s.,!?]", "", unicodedata.normalize("NFD", text))
    tmp_syl = ""
    while text:
        changed: bool = False
        for lookup in translit_lookup:
            if text.startswith(lookup):
                tmp_syl += translit2syl[lookup]
                text = text[len(lookup):]
                changed = True
                break
        if not changed:
            letter = text[0]
            text = text[1:]
            if letter == "l":
                tmp_syl += "ꮅ"
            else:
                tmp_syl += letter
    return unicodedata.normalize("NFC", tmp_syl)


rrd_fix_lookup:dict [str, str] = dict()
for vowel in translit2syl_vowels:
    rrd_fix_lookup["ts" + vowel] = "j" + vowel


def fix_rrd_pronunciation(pronunciation: str) -> str:
    pronunciation = unicodedata.normalize("NFD", pronunciation).lower()
    prev_pronunciation: str = pronunciation
    for lookup in rrd_fix_lookup:
        if lookup in pronunciation:
            pronunciation = pronunciation.replace(lookup, rrd_fix_lookup[lookup])
    if "ts" in pronunciation and prev_pronunciation == pronunciation:
        pronunciation = pronunciation.replace("ts", "j")
    return unicodedata.normalize("NFC", pronunciation).lower()


def test():
    ced_test = ["u²sgal²sdi ạ²dv¹ne²³li⁴sgi.", "ụ²wo²³dị³ge⁴ʔi gi²hli a¹ke²³he³²ga na ạ²chu⁴ja.",
                "ạ²ni²³tạʔ³li ạ²ni²sgạ²ya a¹ni²no²hạ²li²³do³²he, ạ²hwi du¹ni²hyọ²he.",
                "sa¹gwu⁴hno ạ²sgạ²ya gạ²lo¹gwe³ ga²ne²he sọ³ʔị³hnv³ hla².",
                "na³hnv³ gạ²lo¹gwe³ ga²ne⁴hi u²dlv²³kwsạ²ti ge¹se³, ạ²le go²hu⁴sdi yu²³dv³²ne⁴la a¹dlv²³kwsge³.",
                "a¹na³ʔi²sv⁴hnv go²hu⁴sdi wu²³ni³go²he do²jụ²wạ³ʔị²hlv,",
                "na³hnv³ gạ²lo¹gwe³ ga²ne⁴hi kị²lạ²gwu ị²yv⁴da wị²du²³sdạ³yo²hle³ o²³sdạ²gwu nu²³ksẹ²stạ²nv⁴na "
                "ị²yu³sdi da¹sdạ²yo²hị²hv⁴.",
                "u²do²hị²yu⁴hnv³ wu²³yo³hle³ ạ²le u¹ni²go²he³ gạ²nv³gv⁴.",
                "na³hnv³ gạ²lo¹gwe³ nị²ga²³ne³hv⁴na \"ạ²hwi e¹ni²yo³ʔa!\" u¹dv²hne.",
                "\"ji²yo³ʔe³²ga\" u¹dv²hne na³ gạ²lo¹gwe³ ga²ne⁴hi, a¹dlv²³kwsgv³.",
                "u¹na³ne²lu²³gi³²se do²jụ²wạ³ʔị²hlv³ di³dla, nạ²ʔv²³hnị³ge⁴hnv wu²³ni³luh²ja u¹ni²go²he³ so²³gwị³li "
                "gạʔ³nv⁴.",
                "\"so²³gwị³lị³le³² i¹nạ²da²hị³si\" u¹dv²hne³ na³ u²yo²hlv⁴.", "\"hạ²da²hị³se³²ga³\" a¹go¹se²³le³."]

    for a in ced_test:
        print("_______________")
        print()
        print(a)
        print(ced2mco(a))

    ascii_ced_text = ["ga.2da.2de3ga", "ha.2da.2du1ga", "u2da.2di23nv32di", "u1da.2di23nv32sv23?i", "a1da.2de3go3?i"]
    for a in ascii_ced_text:
        print("_______________")
        print()
        print(a)
        print(ascii_ced2mco(a))
    print()
    print("_______________")
    translit_text: str = "osiyo, tohiju? tohigwu."
    print(translit_text)
    print(pronounce2syllabary(translit_text))
    print()


def ced2mco(text: str):
    import unicodedata as ud
    import re

    tones2mco = [("²³", "\u030C"), ("³²", "\u0302"), ("¹", "\u0300"), ("²", ""), ("³", "\u0301"), ("⁴", "\u030b")]

    text = ud.normalize('NFD', text)

    # ensure consistent handling of glottal stop variations
    text = re.sub("[\u02c0\u0241\u0242]", "\u0294", text)

    text = re.sub("(?i)([aeiouv])([^¹²³⁴\u0323]+)", "\\1\u0323\\2", text)
    text = re.sub("(?i)([aeiouv])([¹²³⁴]+)$", "\\1\u0323\\2", text)
    text = re.sub("(?i)([aeiouv])([¹²³⁴]+)([^¹²³⁴a-zʔ])", "\\1\u0323\\2\\3", text)
    text = re.sub("(?i)([^aeiouv\u0323¹²³⁴]+)([¹²³⁴]+)", "\\2\\1", text)
    text = re.sub("(?i)([aeiouv])([¹²³⁴]+)", "\\1\\2:", text)
    text = text.replace("\u0323", "")
    text = re.sub("(?i)([aeiouv])²$", "\\1\u0304", text)
    text = re.sub("(?i)([aeiouv])²([^a-zʔ¹²³⁴:])", "\\1\u0304\\2", text)
    for ced2mcotone in tones2mco:
        text = text.replace(ced2mcotone[0], ced2mcotone[1])

    return ud.normalize('NFC', text)


def ascii_ced2mco(text: str):
    import unicodedata as ud
    text = ud.normalize('NFD', text)
    text = text.replace(".", "\u0323")
    text = text.replace("1", "¹")
    text = text.replace("2", "²")
    text = text.replace("3", "³")
    text = text.replace("4", "⁴")
    text = text.replace("?", "ʔ")
    return ced2mco(text)


def rrd2mco(text: str):
    import unicodedata as ud
    text: str = ud.normalize('NFD', text)
    text = re.sub("(?i)([aeiouv]\u0323)([^\\s¹²³⁴])", "\\1²\\2", text)
    text = re.sub("(?i)([aeiouv])([^\\s\u0323¹²³⁴])", "\\1²\\2", text)
    return ced2mco(text)


if __name__ == "__main__":
    test()
