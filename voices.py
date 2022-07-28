from typing import List
from shared_rand import rand

IMS_VOICES_MALE: List[str] = ["en-345-m", "en-360-m"]
# IMS_VOICES_FEMALE: List[str] = ["en-294-f", "en-330-f", "en-333-f", "en-361-f"]
IMS_VOICES_FEMALE: List[str] = ["en-333-f", "en-361-f"]
IMS_VOICES: List[str] = List()
IMS_VOICES.extend(IMS_VOICES_FEMALE)
IMS_VOICES.extend(IMS_VOICES_MALE)
IMS_VOICES.sort()
ims_voices: List[str] = List()

AMZ_VOICES_MALE: List[str] = ["Joey"]
# AMZ_VOICES_FEMALE: List[str] = ["Joanna", "Kendra", "Kimberly", "Salli"]
AMZ_VOICES_FEMALE: List[str] = ["Kendra"]
AMZ_VOICES: List[str] = List()
AMZ_VOICES.extend(AMZ_VOICES_FEMALE)
AMZ_VOICES.extend(AMZ_VOICES_MALE)
amz_voices: List[str] = List()

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
