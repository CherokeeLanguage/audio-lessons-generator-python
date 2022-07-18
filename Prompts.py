from datetime import datetime
from pydub import AudioSegment

from TTS import en_audio

AMZ_VOICE_INSTRUCTOR: str = "Matthew"


def create_prompts() -> dict[str, AudioSegment]:
    print("Creating instructor prompts")
    prompts: dict[str, AudioSegment] = dict()
    voice: str = AMZ_VOICE_INSTRUCTOR

    tag: str = "also_hear"
    text: str = "You will also hear the following:"
    prompts[tag] = en_audio(voice, text)

    tag: str = "also_hear_short"
    text: str = "Also:"
    prompts[tag] = en_audio(voice, text)

    tag: str = "produced"
    text: str = f"""
    This audio file was produced on
    {datetime.today().strftime("%B %d, %Y")}
    by Michael Conrad."
    """
    prompts[tag] = en_audio(voice, text)

    tag: str = "first_phrase"
    text: str = "Here is your first phrase to learn for this session. Listen carefully:"
    prompts[tag] = en_audio(voice, text)

    tag: str = "language_culture_1"
    text: str = """
    Language and culture which are not shared and taught openly and freely will die.
    If our language and culture die, then, as a people, so do we.
    """
    prompts[tag] = en_audio(voice, text)

    tag = "copy_1"
    text = f"Production copyright {datetime.utcnow().year} by Michael Conrad."
    prompts[tag] = en_audio(voice, text)

    tag = "copy_by_sa"
    text = f"""
    This work is licensed to you under the Creative Commons Attribution Share-Alike license.
    To obtain a copy of this license please look up Creative Commons online.
    You are free to share, copy, and distribute this work.
    If you alter, build upon, or transform this work, you must use the same license on the resulting work.
    """
    prompts[tag] = en_audio(voice, text)

    tag = "copy_by_nc"
    text = f"""
    This work is licensed to you under the Creative Commons Attribution Non-Commercial license.
    To obtain a copy of this license please look up Creative Commons online.
    You are free to share and adapt this work. If you alter, build upon, or transform this work,
    you must use the same license on the resulting work.
    """
    prompts[tag] = en_audio(voice, text)

    tag = "is_derived"
    text = "This is a derived work."
    prompts[tag] = en_audio(voice, text)

    tag = "is_derived_cherokee_nation"
    text = """
    This is a derived work. Permission to use the original Cherokee audio and print materials for
    non-commercial use granted by "The Cherokee Nation of Oklahoma".
    """
    prompts[tag] = en_audio(voice, text)

    tag = "walc1_attribution"
    text = """
    Original audio copyright 2018 by the Cherokee Nation of Oklahoma.
    The contents of the "We are Learning Cherokee Level 1" textbook were developed by Durbin Feeling,
    Patrick Rochford, Anna Sixkiller, David Crawler, John Ross, Dennis Sixkiller, Ed Fields, Edna Jones,
    Lula Elk, Lawrence Panther, Jeff Edwards, Zachary Barnes, Wade Blevins, and Roy Boney, Jr.";
    """
    prompts[tag] = en_audio(voice, text)

    tag = "intro_1"
    text = """
    In these sessions, you will learn Cherokee phrases by responding with each phrase's English
    translation. Each new phrase will be introduced with it's English translation. You will then be
    prompted to translate different phrases into English. It is important to respond aloud.
    """
    prompts[tag] = en_audio(voice, text)

    tag = "intro_3"
    text = """
    In these sessions, you will learn by responding aloud in English.
    Each phrase will be introduced with an English translation.
    As the sessions progress you will be prompted to translate different phrases into English.
    It is important to respond aloud.
    """
    prompts[tag] = en_audio(voice, text)

    tag = "intro_2"
    text = """
        About the pronoun, "you". In English this pronoun can refer to 1 person, 2 people, or more people.
        Cherokee has three different forms for, "you". A different word when referring to 1 person.
        Another word when referring to 2 people. And another when referring to 3 or more people.
        When you hear the word, "you", assume it refers to one person unless it is followed by
        the word, "both", or the word, "all".
        """
    prompts[tag] = en_audio(voice, text)

    tag = "keep_going"
    text = """
    Do not become discouraged while doing these sessions.
    It is normal to have to repeat them several times.
    As you progress you will find the later sessions much easier.
    """
    prompts[tag] = en_audio(voice, text)

    tag = "begin"
    text = "Let us begin."
    prompts[tag] = en_audio(voice, text)

    tag = "learn_sounds_first"
    text = """
    Only after you have learned how the words in Cherokee sound and how they are used together will you
    be able to speak Cherokee. This material is designed to assist with learning these sounds and word
    combinations. This is the way young children learn their first language or languages.
    """
    prompts[tag] = en_audio(voice, text)

    tag = "new_phrase"
    text = "Here is a new phrase to learn. Listen carefully:"
    prompts[tag] = en_audio(voice, text)

    tag = "new_phrase_short"
    text = "Here is a new phrase:"
    prompts[tag] = en_audio(voice, text)

    tag = "translate"
    text = "Translate into English:"
    prompts[tag] = en_audio(voice, text)

    tag = "translate_short"
    text = "Translate:"
    prompts[tag] = en_audio(voice, text)

    tag = "listen_again"
    text = "Here is the phrase again:"
    prompts[tag] = en_audio(voice, text)

    tag = "listen_again_short"
    text = "Again:"
    prompts[tag] = en_audio(voice, text)

    tag = "its_translation_is"
    text = "Here it is in English:"
    prompts[tag] = en_audio(voice, text)

    tag = "in_english"
    text = "In English:"
    prompts[tag] = en_audio(voice, text)

    tag = "concludes_this_exercise"
    text = "This concludes this audio exercise."
    prompts[tag] = en_audio(voice, text)

    tag = "cll1-v3"
    text = "Cherokee Language Lessons 1. 3rd Edition."
    prompts[tag] = en_audio(voice, text)

    tag = "ced-sentences"
    text = "Example sentences. Cherokee English Dictionary, 1st edition."
    prompts[tag] = en_audio(voice, text)

    tag = "bound-pronouns"
    text = "Bound Pronouns Training."
    prompts[tag] = en_audio(voice, text)

    tag = "ced-mco"
    text = "Cherokee English Dictionary Vocabulary Cram."
    prompts[tag] = en_audio(voice, text)

    tag = "osiyo-tohiju-then-what"
    text = "Conversation Starters in Cherokee."
    prompts[tag] = en_audio(voice, text)

    tag = "wwacc"
    text = "Advanced Conversational Cherokee."
    prompts[tag] = en_audio(voice, text)

    tag = "walc-1"
    text = "We are learning Cherokee - Book 1."
    prompts[tag] = en_audio(voice, text)

    tag = "animals"
    text = "Cherokee animal names."
    prompts[tag] = en_audio(voice, text)

    tag = "cll1-v3-about"
    text = """
    These audio exercise sessions complement the book 'Cherokee Language Lessons 1', 3rd Edition, by Michael Conrad.
    Each set of audio exercises are meant to be completed before working through the 
    corresponding chapters in the book. The audio will indicate when you should
    switch to the book exercises.
    By the time you complete the assigned sessions, you should have
    little to no difficulty with reading the Cherokee in the chapter texts.
    """
    prompts[tag] = en_audio(voice, text)

    tag = "beginning-cherokee"
    text = "Beginning Cherokee. 2nd Edition."
    prompts[tag] = en_audio(voice, text)

    tag = "beginning-cherokee-about"
    text = """
        These audio exercise sessions were createdf to complement
        the book 'Beginning Cherokee', 2nd Edition, by Ruth Bradley Holmes and Betty Sharp Smith.
        Each set of audio exercises should be completed before working through the 
        corresponding lessons in the book.
        The audio will indicate when you should switch to the book exercises.
        By the time you complete the assigned audio exercises, you should have
        little to no difficulty with reading the Cherokee in the chapter texts.
        """
    prompts[tag] = en_audio(voice, text)

    tag = "ced-sentences-about"
    text = """
        These audio exercise sessions complement the 'Cherokee English Dictionary', 1st Edition.
        Vocabulary is based on the example sentences from each dictionary entry.
        """
    prompts[tag] = en_audio(voice, text)

    tag = "bound-pronouns-about"
    text = """
    These sessions closely follow the vocabulary from the Bound Pronouns app.
    These exercises are designed to assist
    with learning the different singular
    and plural bound pronoun combinations.
    """
    prompts[tag] = en_audio(voice, text)

    tag = "two-men-hunting-about"
    text = """
    These sessions closely follow the vocabulary from the story entitled, 'Two Hunters',
    as recorded in the Cherokee English Dictionary, 1st edition.
    By the time you have completed these exercises you should be able to understand
    the full spoken story without any difficulty.
    """
    prompts[tag] = en_audio(voice, text)

    tag = "ced-mco-about"
    text = """
    These sessions use vocabulary taken from the Cherokee English Dictionary, 1st Edition.
    The pronunciations are based on the pronunciation markings as found in the dictionary.
    """
    prompts[tag] = en_audio(voice, text)

    tag = "osiyo-tohiju-then-what-about"
    text = """
    These sessions closely follow the book entitled, 'Conversation Starters in Cherokee', by Prentice Robinson.
    The pronunciations are based on the pronunciation markings as found in the official
    Cherokee English Dictionary - 1st Edition.
    """
    prompts[tag] = en_audio(voice, text)

    tag = "wwacc-about"
    text = """
    These sessions closely follow the booklet entitled, 'Advanced Conversational Cherokee', by Willard Walker.
    """
    prompts[tag] = en_audio(voice, text)

    tag = "walc-1-about"
    text = """
    These sessions closely follow the lesson material 'We are learning Cherokee - Book 1'.
    """
    prompts[tag] = en_audio(voice, text)

    tag = "animals-about"
    text = """
    These sessions closely follow the vocabulary from the Animals app.
    """
    prompts[tag] = en_audio(voice, text)

    tag = "short-speech"
    text = """
    Much the same way that English speakers shorten phrases such as “do not” into “don't” and “can not” into “can't”,
     Cherokee speakers also shorten phrases by dropping certain vowels, syllables, and words in everyday speech.
     Vocabulary will be introduced using the long form of the word or phrase.
     Many challenges will be using a mixture of full and short forms.
    """
    prompts[tag] = en_audio(voice, text)

    return prompts
