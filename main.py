import os

import boto3
from boto3_type_annotations.polly import Client as Polly
from leitner_cards.Leitner import LeitnerDeck

from pydub import AudioSegment

from config import Config

if __name__ == "__main__":

    os.chdir(os.path.dirname(__file__))
    print(os.getcwd())

    main_deck: LeitnerDeck = LeitnerDeck()
    discards_deck: LeitnerDeck = LeitnerDeck()
    finished_deck: LeitnerDeck = LeitnerDeck()
    active_deck: LeitnerDeck = LeitnerDeck()

    hz: int = 22050
    cfg: Config
    with open ("walc1/walc1.json", "r") as f:
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
        response = polly_client.synthesize_speech(
                Engine="neural",
                VoiceId="Joanna",
                Text="Sample synthesize.",
                SampleRate=str(hz),
                OutputFormat="mp3")
        with open("test.mp3", "wb") as w:
            w.write(response["AudioStream"].read())

        # main_audio.append(AudioSegment.from_file(""))

        _exercise_set += 1
        break
    pass
