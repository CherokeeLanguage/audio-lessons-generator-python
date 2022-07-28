#!/usr/bin/env bash
"""true" '''\'
set -e
eval "$(${CONDA_EXE:-conda} shell.bash hook)"
conda activate audio-lessons
exec python "$0" "$@"
exit $?
''"""
from __future__ import annotations
from typing import Dict, List
from artifacts import save_audio_lesson

import os
import pathlib
import shutil

import simplejson
from pydub import AudioSegment
from tqdm import tqdm

from CardUtils import CardUtils
from LeitnerAudioDeck import AudioCard
from LeitnerAudioDeck import LeitnerAudioDeck
import Prompts
import tts
from SrtEntry import SrtEntry
from config import Config
from shared_rand import rand
from voices import AMZ_VOICES, IMS_VOICES, next_amz_voice, next_ims_voice
from deck_utils import load_main_deck, save_deck


# DATASET: str = "osiyo-tohiju-then-what"
# DATASET: str = "cll1-v3"
# DATASET: str = "cll1-v3-cram"
# DATASET: str = "animals"
# DATASET: str = "bound-pronouns"
# DATASET: str = "ced-sentences"
DATASET: str = "beginning-cherokee"

RESORT_BY_LENGTH: bool = False
if DATASET == "animals":
    RESORT_BY_LENGTH = True

CACHE_CHR = os.path.join("cache", "chr")
CACHE_EN = os.path.join("cache", "en")

AMZ_HZ: str = "24000"
LESSON_HZ: int = 48_000


def create_card_audio(cfg: Config, main_deck: LeitnerAudioDeck):
    os.makedirs(CACHE_CHR, exist_ok=True)
    os.makedirs(CACHE_EN, exist_ok=True)
    print("Creating card audio")
    for card in tqdm(main_deck.cards):
        data = card.data
        text_chr = data.challenge
        text_chr_alts = data.challenge_alts
        text_en = data.answer
        for voice in IMS_VOICES:
            tts.tts_chr(voice, text_chr, cfg.alpha)
            for alt in text_chr_alts:
                tts.tts_chr(voice, alt, cfg.alpha)
        for voice in AMZ_VOICES:
            tts.tts_en(voice, text_en)


vstem_counts: dict[str, int] = dict()
pbound_counts: dict[str, int] = dict()


def save_stem_counts(finished_deck: LeitnerAudioDeck) -> None:
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
    # TODO: Add docstring - why do we skip some new cards?
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


def introduce_new_card(
    cfg: Config,
    card: AudioCard,
    *,
    main_audio: AudioSegment,
    prompts: Dict[str, AudioSegment],
    exercise_no: int,
    should_do_long_introduction: bool,
    first_new_challenge: str,
    new_count: int,
    max_new_cards_this_session: int
    ):
    """
    Update card state for a new card.

    Inform listener that a new term is about to be introduced.
    """
    max_new_reached = False
    last_new_challenge = "" # FIXME: make this None

    if not first_new_challenge:
        first_new_challenge = card.data.challenge
    else:
        last_new_challenge = card.data.challenge

    end_note = card.data.end_note
    # empy end note means no end note
    if end_note == "":
        end_note = None

    if should_do_long_introduction:
        print(f"Introduced card: {card.data.challenge} [{card.card_stats.tries_remaining:,}]")
    else:
        card.card_stats.leitner_box += 2  # hidden new cards should be already known vocabulary
        card.card_stats.new_card = False
        card.reset_tries_remaining(max(cfg.review_card_max_tries // 2,  #
                                        cfg.review_card_max_tries  #
                                        - cfg.review_card_tries_decrement  #
                                        * exercise_no))
        print(f"Hidden new card: {card.data.challenge} [{card.card_stats.tries_remaining:,}]")

    if end_note is not None:
        print(f"- End note: {end_note}")
        if cfg.break_on_end_note:
            max_new_reached = True
            print(f" - No more new cards this session.")

    if new_count >= max_new_cards_this_session:
        max_new_reached = True
        print(f" - No more new cards this session.")

    main_audio = main_audio.append(AudioSegment.silent(1_500))

    card.card_stats.new_card = False

    if new_count < 6 and exercise_no == 0:
        if new_count == 1:
            first_new_phrase = prompts["first_phrase"]
            main_audio = main_audio.append(first_new_phrase)
        else:
            main_audio = main_audio.append(prompts["new_phrase"])
    else:
        main_audio = main_audio.append(prompts["new_phrase_short"])

    main_audio = main_audio.append(AudioSegment.silent(750))

    return main_audio, end_note, first_new_challenge, last_new_challenge, max_new_reached

def repeat_and_provide_translation(

    cfg: Config,
    card: AudioCard,
    *,
    main_audio: AudioSegment,
    prompts: Dict[str, AudioSegment],
    exercise_no: int,
    challenge: str,
    new_count: int,
):
    """
    Repeat a new phrase, provide alternative pronounciations, and provide a translation.
    """
    srt_entries: List[SrtEntry] = []
    # introduce Cherokee challenge
    main_audio = main_audio.append(AudioSegment.silent(1_500))
    data_file: AudioSegment = tts.chr_audio(next_ims_voice(card.data.sex), challenge, cfg.alpha)
    if new_count < 8 and exercise_no == 0:
        main_audio = main_audio.append(prompts["listen_again"])
    else:
        main_audio = main_audio.append(prompts["listen_again_short"])
    main_audio = main_audio.append(AudioSegment.silent(1_500))
    srt_entry: SrtEntry = SrtEntry()
    srt_entry.text = challenge
    srt_entry.start = main_audio.duration_seconds
    main_audio = main_audio.append(data_file, crossfade=0)
    srt_entry.end = main_audio.duration_seconds
    srt_entries.append(srt_entry)
    main_audio = main_audio.append(AudioSegment.silent(1_500))

    # introduce alt pronunciations
    if card.data.challenge_alts:
        if new_count < 6 and exercise_no <= 2:
            main_audio = main_audio.append(prompts["also_hear"])
        else:
            main_audio = main_audio.append(prompts["also_hear_short"])
        main_audio = main_audio.append(AudioSegment.silent(1_000))
        for alt in card.data.challenge_alts:
            if alt == challenge:
                continue
            main_audio = main_audio.append(AudioSegment.silent(500))
            srt_entry: SrtEntry = SrtEntry()
            srt_entries.append(srt_entry)
            srt_entry.text = alt
            srt_entry.start = main_audio.duration_seconds
            main_audio = main_audio.append(tts.chr_audio(next_ims_voice(card.data.sex), alt, cfg.alpha),
                                            crossfade=0)
            srt_entry.end = main_audio.duration_seconds
            main_audio = main_audio.append(AudioSegment.silent(1_000))

    # output English gloss
    if new_count < 10 and exercise_no == 0:
        main_audio = main_audio.append(prompts["its_translation_is"])
        main_audio = main_audio.append(AudioSegment.silent(750))
    else:
        main_audio = main_audio.append(prompts["in_english"])
        main_audio = main_audio.append(AudioSegment.silent(750))

    return main_audio, srt_entries 

def provide_answer(*, card: AudioCard, main_audio: AudioSegment, challenge_audio_seconds: float, wait_for_listner_response: bool):
    """
    Provide an answer for a challenge, optionally with a gap for the user to respond first.
    """

    answer_audio = tts.en_audio(next_amz_voice(card.data.sex), card.data.answer)
    if wait_for_listner_response:
        gap_duration: float = max(challenge_audio_seconds, 1.0)
        main_audio = main_audio.append(AudioSegment.silent(int(1_000 * gap_duration)))
        # Silence gap for user to respond during. Only if the card was not introduced.
        _ = AudioSegment.silent(int((2 + 1.1 * answer_audio.duration_seconds) * 1_000))
        main_audio = main_audio.append(_)

    # Provide answer.
    srt_entry: SrtEntry = SrtEntry()
    srt_entry.text = card.data.answer
    srt_entry.start = main_audio.duration_seconds
    main_audio = main_audio.append(answer_audio)
    srt_entry.end = main_audio.duration_seconds

    return srt_entry, main_audio

def read_challenge(cfg, *, main_audio: AudioSegment, challenge: str, sex: str):
    challenge_audio: AudioSegment = tts.chr_audio(next_ims_voice(sex), challenge, cfg.alpha)

    srt_entry: SrtEntry = SrtEntry()
    srt_entry.text = challenge
    srt_entry.start = main_audio.duration_seconds
    main_audio = main_audio.append(challenge_audio, crossfade=0)
    srt_entry.end = main_audio.duration_seconds

    return main_audio, srt_entry, challenge_audio

def pick_challenge(card: AudioCard, *, should_do_long_introduction: bool):
    if not card.data.challenge_alts or should_do_long_introduction:
        return card.data.challenge
    else:
        return rand.choice(card.data.challenge_alts)
    
def append_audio_for_new_card(
    cfg: Config,
    card: AudioCard,
    *,
    main_audio: AudioSegment,
    prompts: Dict[str, AudioSegment],
    exercise_no: int,
    new_count: int,
    should_do_long_introduction: bool,
    first_new_challenge: str,
    max_new_cards_this_session: int
    ):
    """
    Append audio for a new card.

    This will be something like:
    "Here is a new term"
    <Cherokee term>
    "Again"
    <Same term>
    "Also"
    <Alternate pronounciation>
    "In English"
    <English translation>
    """
    srt_entries: List[SrtEntry] = []
    main_audio,end_note, first_new_challenge, last_new_challenge, max_new_reached = introduce_new_card(
        cfg,
        card,
        main_audio=main_audio,
        prompts=prompts,
        exercise_no=exercise_no,
        should_do_long_introduction=should_do_long_introduction,
        first_new_challenge=first_new_challenge,
        new_count=new_count,
        max_new_cards_this_session=max_new_cards_this_session,
    )

    # pick challenge
    challenge = pick_challenge(card,
        should_do_long_introduction=should_do_long_introduction
    )
    main_audio, srt_entry, challenge_audio = read_challenge(cfg, main_audio=main_audio, challenge=challenge, sex=card.data.sex,)
    srt_entries.append(srt_entry)
    
    main_audio, new_srt_entries  = repeat_and_provide_translation(
        cfg,
        card,
        main_audio=main_audio,
        prompts=prompts,
        exercise_no=exercise_no,
        challenge=challenge,
        new_count=new_count
    )
    srt_entries.extend(new_srt_entries)

    srt_entry, main_audio = provide_answer(
        card=card,
        main_audio=main_audio,
        challenge_audio_seconds=challenge_audio.duration_seconds,
        wait_for_listner_response=False
    )

    srt_entries.append(srt_entry)

    return main_audio, srt_entries, end_note, first_new_challenge, last_new_challenge, max_new_reached

def append_audio_for_review_card(cfg: Config, card: AudioCard, *, main_audio: AudioSegment, challenge_count: int, prompts: Dict[str, AudioSegment], exercise_no: int, first_review_challenge: str):
    """
    Append audio for a review card.

    This will be something like:
    "Translate"
    <Cherokee term>
    <Pause>
    <English translation>
    """
    srt_entries: List[SrtEntry] = []
    last_review_challenge = ""
    
    # prompt the listener to translate
    if challenge_count < 16 and exercise_no == 0:
        main_audio = main_audio.append(prompts["translate"])
    else:
        main_audio = main_audio.append(prompts["translate_short"])
    main_audio = main_audio.append(AudioSegment.silent(1_000))
    
    # track review challenges
    if not card.card_stats.shown:
        if not first_review_challenge:
            first_review_challenge = card.data.challenge
        else:
            last_review_challenge = card.data.challenge
        
    # pick challenge
    challenge = pick_challenge(card,
        should_do_long_introduction=False
    )
    srt_entry, main_audio, challenge_audio = read_challenge(cfg, main_audio=main_audio, challenge=challenge, sex=card.data.sex,)
    srt_entries.append(srt_entry)

    
    srt_entry, main_audio = provide_answer(
        card=card,
        main_audio=main_audio,
        challenge_audio_seconds=challenge_audio.duration_seconds,
        wait_for_listner_response=False
    )

    srt_entries.append(srt_entry)

    return main_audio, srt_entries, first_review_challenge, last_review_challenge

def create_audio_lessons(cfg: Config, *, dataset:str, util: CardUtils, out_dir: str, main_deck: LeitnerAudioDeck):
    discards_deck: LeitnerAudioDeck = LeitnerAudioDeck()
    finished_deck: LeitnerAudioDeck = LeitnerAudioDeck()
    active_deck: LeitnerAudioDeck = LeitnerAudioDeck()

    prompts = Prompts.create_prompts()

    exercise_no: int = 0
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

    while keep_going and (exercise_no < cfg.sessions_to_create or cfg.create_all_sessions):

        if exercise_no > 0:
            print()
            print()

        print(f"=== SESSION: {exercise_no + 1:04}")
        print()

        lead_in: AudioSegment = AudioSegment.silent(750, LESSON_HZ).set_channels(1)
        # Exercise set title
        lead_in = lead_in.append(prompts[dataset])
        lead_in = lead_in.append(AudioSegment.silent(750))

        if exercise_no == 0:
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

        session_start: str = f"Session {exercise_no + 1}."
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
                                              cfg.new_cards_per_session + exercise_no * cfg.new_cards_increment)
        print(f"--- Max new cards: {max_new_cards_this_session:,d}")
        max_review_cards_this_session = min(cfg.review_cards_max_per_session,
                                            cfg.review_cards_per_session + exercise_no * cfg.review_cards_increment)
        print(f"--- Max review cards: {max_review_cards_this_session:,d}")

        end_note: str | None = None

        first_new_challenge: str = ""
        last_new_challenge: str = ""
        first_review_challenge: str = ""
        last_review_challenge: str = ""

        srt_entries: list[SrtEntry] = list()

        while (lead_in.duration_seconds
                + lead_out.duration_seconds
                + main_audio.duration_seconds
                < cfg.session_max_duration):
            start_length: float = main_audio.duration_seconds
            card = next_card(
                cfg,
                exercise_set=exercise_no,
                main_deck=main_deck,
                active_deck=active_deck,
                discards_deck=discards_deck,
                finished_deck=finished_deck,
                prev_card_id=prev_card_id,
                max_new_reached=max_new_reached,
                max_review_cards_this_session=max_review_cards_this_session
            )
            if not card:
                # we have done all available cards
                break
                
            # TODO: should this live in next_card()?
            card_id: str = card.data.card_id
            if card_id == prev_card_id:
                # if we just saw this card, don't show it again
                card.card_stats.show_again_delay = 32
                continue
            
            prev_card_id = card_id

            if card.card_stats.new_card:
                should_do_long_introduction: bool = card.card_stats.new_card and not skip_new(card)
                
                if should_do_long_introduction:
                    introduced_count += 1
                else:
                    hidden_count += 1
                new_count += 1

                new_srt_entries, main_audio, end_note, first_new_challenge, last_new_challenge, max_new_reached = append_audio_for_new_card(
                    cfg, card,
                    main_audio=main_audio,
                    prompts=prompts,
                    exercise_no=exercise_no,
                    new_count=new_count,
                    should_do_long_introduction=should_do_long_introduction,
                    first_new_challenge=first_new_challenge,
                    max_new_cards_this_session=max_new_cards_this_session
                )

                srt_entries.extend(new_srt_entries)
            else:
                challenge_count += 1
                if card.card_stats.show_again_delay > 0:
                    extra_delay_time: int = int(1_000 * min(7.0, card.card_stats.show_again_delay))
                    main_audio = main_audio.append(AudioSegment.silent(extra_delay_time), crossfade=0)

                main_audio, new_srt_entries, first_review_challenge, last_review_challenge = append_audio_for_review_card(
                    cfg,
                    card,
                    main_audio=main_audio,
                    challenge_count=challenge_count,
                    prompts=prompts,
                    exercise_no=exercise_no,
                    first_review_challenge=first_review_challenge
                )

                srt_entries.extend(new_srt_entries)

            # Add a break after each card
            if exercise_no == 0:
                main_audio = main_audio.append(AudioSegment.silent(2_250))
            elif exercise_no < 5:
                main_audio = main_audio.append(AudioSegment.silent(1_500))
            else:
                main_audio = main_audio.append(AudioSegment.silent(750))

            delta_tick: float = main_audio.duration_seconds - start_length
            active_deck.update_time(delta_tick)
            discards_deck.update_time(delta_tick)
            finished_deck.update_time(delta_tick)

            card.card_stats.pimsleur_slot_inc()
            next_interval: float = util.next_pimsleur_interval(card.card_stats.pimsleur_slot) + 1.0
            card.card_stats.show_again_delay = next_interval

        # Prepare decks for next session
        bump_completed(discards_deck=discards_deck, finished_deck=finished_deck)
        seconds_offset: float = 0.0
        for card in active_deck.cards.copy():
            discards_deck.append(card)
        if active_deck.has_cards:
            raise Exception("Active Deck should be empty!")
        for card in discards_deck.cards.copy():
            card_stats = card.card_stats
            if card_stats.shown >= card_stats.tries_remaining:
                card_stats.tries_remaining = 0
                bump_completed(discards_deck=discards_deck, finished_deck=finished_deck)
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

        tags = save_audio_lesson(cfg,
            dataset=dataset,
            out_dir=out_dir,
            lead_in=lead_in,
            lead_out=lead_out,
            main_audio=main_audio,
            exercise_no=exercise_no,
            review_count=review_count,
            introduced_count=introduced_count,
            hidden_count=hidden_count,
            first_new_challenge=first_new_challenge,
            first_review_challenge=first_review_challenge,
            last_new_challenge=last_new_challenge,
            last_review_challenge=last_review_challenge,
            srt_entries=srt_entries,
            end_note=end_note or ""
        )
        
        end_notes_by_track[exercise_no] = end_note or ""
        metadata_by_track[exercise_no] = tags

        # Bump counter
        exercise_no += 1

        # Free up memory
        del lead_in
        del lead_out
        del main_audio

        if not main_deck.has_cards:
            keep_going = extra_sessions > 0
            extra_sessions -= 1

    return exercise_no, end_notes_by_track, metadata_by_track, finished_deck


def main() -> None:
    global review_count
    deck_source: str

    util: CardUtils = CardUtils()
    os.chdir(os.path.dirname(__file__))

    cfg = load_config(DATASET)

    out_dir: str

    if cfg.alpha and cfg.alpha != 1.0:
        out_dir = os.path.join(os.path.realpath("."), "output", f"{DATASET}_{cfg.alpha:.2f}")
    else:
        out_dir = os.path.join(os.path.realpath("."), "output", DATASET)

    if cfg.deck_source:
        deck_source = cfg.deck_source
    else:
        deck_source = DATASET

    shutil.rmtree(out_dir, ignore_errors=True)
    os.makedirs(out_dir, exist_ok=True)

    main_deck = load_main_deck(os.path.join("data", deck_source + ".txt"))
    if RESORT_BY_LENGTH:
        main_deck.cards.sort(key=lambda c: c.data.sort_key)
    
    save_deck(main_deck, pathlib.Path("decks", f"{DATASET}-orig.json"))

    # good abstraction
    create_card_audio(cfg, main_deck)
    _exercise_set, end_notes_by_track, metadata_by_track, finished_deck = create_audio_lessons(cfg, dataset=DATASET, util=util, out_dir=out_dir, main_deck=main_deck)

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

    save_deck(finished_deck, pathlib.Path("decks", f"{DATASET}.json"))


def load_config(DATASET: str):
    os.makedirs("configs", exist_ok=True)
    cfg_file: str = f"configs/{DATASET}-cfg.json"
    if os.path.exists(cfg_file):
        with open(cfg_file, "r") as f:
            cfg = Config.load(f)
    else:
        cfg = Config()
        with open(cfg_file, "w") as w:
            Config.save(w, cfg)

    return cfg


review_count: int = 0


def scan_for_cards_to_show_again(*, discards_deck: LeitnerAudioDeck, active_deck: LeitnerAudioDeck) -> None:
    """
    Check for cards in the discard deck that should be shown again.
    """
    # Scan for cards to show again
    for card in discards_deck.cards.copy():
        if card.card_stats.show_again_delay > 0:
            continue
        active_deck.append(card)


def next_card(
    cfg: Config,
    *,
    main_deck: LeitnerAudioDeck,
    active_deck: LeitnerAudioDeck,
    discards_deck: LeitnerAudioDeck,
    finished_deck: LeitnerAudioDeck,
    exercise_set: int,
    prev_card_id: str,
    max_new_reached: bool,
    max_review_cards_this_session: int,
    ) -> AudioCard | None:
    global review_count # FIXME: put this state somewhere
    bump_completed(discards_deck=discards_deck, finished_deck=finished_deck)
    if active_deck.top_card:
        card = active_deck.top_card
        discards_deck.append(card)
        if card.data.card_id != prev_card_id:
            card_stats = card.card_stats
            card_stats.tries_remaining_dec()
            card_stats.shown += 1
            return card
        if active_deck.has_cards:
            return next_card(
                cfg,
                main_deck=main_deck,
                active_deck=active_deck,
                discards_deck=discards_deck,
                finished_deck=finished_deck,
                exercise_set=exercise_set,
                prev_card_id=prev_card_id,
                max_new_reached=max_new_reached,
                max_review_cards_this_session=max_review_cards_this_session
            )

    if finished_deck.next_show_time <= 0 and finished_deck.has_cards and review_count < max_review_cards_this_session:
        review_count += 1
        review_card = finished_deck.top_card
        if review_card is None:
            raise ValueError("Finished deck has no top card!")
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
    scan_for_cards_to_show_again(discards_deck=discards_deck, active_deck=active_deck)

    if not max_new_reached and main_deck.top_card:
        new_card = main_deck.top_card
        new_card.card_stats.new_card = True
        # check to see if "new" state should be ignored
        new_card.reset_tries_remaining(  #
                max(cfg.new_card_max_tries // 2,  #
                    cfg.new_card_max_tries - cfg.new_card_tries_decrement * exercise_set))
        discards_deck.append(new_card)
        return new_card
    if active_deck.top_card:
        active_deck.sort_by_show_again()
        card = active_deck.top_card
        discards_deck.append(card)
        card.card_stats.show_again_delay = extra_delay
        card.card_stats.tries_remaining_dec()
        card.card_stats.shown += 1
        return card
    else:
        print(" - Active deck is out of cards.")
        return None


def bump_completed(discards_deck: LeitnerAudioDeck, finished_deck: LeitnerAudioDeck) -> None:
    util: CardUtils = CardUtils() # FIXME: should we pass this in?
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
