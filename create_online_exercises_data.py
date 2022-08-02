import argparse
import json
from pathlib import Path
from typing import Dict, List, Optional
import os
import unicodedata

import jsonpickle
import simplejson

from LeitnerAudioDeck import LeitnerAudioDeck
from SrtEntry import SrtEntry
from config import Config

def main(cfg: Config, dataset: str):
    # get the run dir for the file
    if cfg.alpha and cfg.alpha != 1.0:
        run_dir = Path(os.path.join(os.path.realpath("."), "output", f"{dataset}_{cfg.alpha:.2f}"))
    else:
        run_dir = Path(os.path.join(os.path.realpath("."), "output", dataset))

    out_dir = run_dir / "online_exercises"
    os.makedirs(out_dir, exist_ok=True)

    terms_by_lesson = get_terms_by_lesson(Path(f"./data/{dataset}.txt"))
    simplejson.dump(terms_by_lesson, open(out_dir / "terms_by_lesson.json", "w"), ensure_ascii=False) 
    # srt_dir = run_dir / "srt"
    # srts_by_exercise = load_srts(srt_dir)

    # TODO: filter out English using deck challenge/challenge_alts

    # deck = load_deck(run_dir / "source" / f"{dataset}-with-audio-file.json")
    # terms_by_exercise = {
    #     exercise_no: [srt.text for srt in srts] for exercise_no, srts in srts_by_exercise.items()
    # }


def get_terms_by_lesson(source: Path) -> Dict[str, List[str]]:
    terms_by_lesson: Dict[str, List[str]] = {}
    current_lesson: Optional[str] = None
    with open(source, "r") as r:
        first_line = True
        for line in r:
            line = unicodedata.normalize("NFC", line)
            if first_line:
                first_line = False
                continue
            if line.startswith("#"):
                if line.startswith('#Chapter'):
                    current_lesson = line[1:].strip().strip('|')
                continue
            
            if line == "\n":
                continue

            if current_lesson is None:
                raise ValueError("File should have a chatper marker before any terms")

            pronounce = line.strip().split('|')[7]
            if not current_lesson in terms_by_lesson:
                terms_by_lesson[current_lesson] = [pronounce]
            else:
                terms_by_lesson[current_lesson].append(pronounce)
    
    return terms_by_lesson

def load_srts(srt_dir: Path) -> Dict[int, List[SrtEntry]]:
    entries_by_exercise: Dict[int, List[SrtEntry]] = {}
    for path in srt_dir.glob("*.srt"):
        exercise_no = int(path.stem.split('-')[-1])
        with open(path, 'r') as r:
            text = r.read()
        
        entries = [SrtEntry.deserialize(serialized) for serialized in text.split('\n\n')]

        entries_by_exercise[exercise_no] = entries

    return entries_by_exercise

def load_deck(path: Path):
    jsonpickle.load_backend('simplejson', 'dumps', 'loads', ValueError)
    jsonpickle.set_preferred_backend('simplejson')
    # jsonpickle.set_decoder_options('simplejson', ensure_ascii=False)
    with open(path, "r") as r:
        deck = jsonpickle.loads(r.read())

    assert isinstance(deck,  LeitnerAudioDeck), "Deck should be a leitner audio deck"

    return deck


if __name__ == "__main__":
    parser: argparse.ArgumentParser = argparse.ArgumentParser(
        description="Collect data from generating audio lessons to create metadata needed for online exercises."
    )
    parser.add_argument("--dataset", type=str, required=True, help="Dataset used to generate the audio exercises")
    args: argparse.Namespace = parser.parse_args()
    cfg_file: str = f"configs/{args.dataset}-cfg.json"

    with open(cfg_file, "r") as f:
        cfg = Config.load(f)

    main(cfg, args.dataset)