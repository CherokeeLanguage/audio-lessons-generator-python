from __future__ import annotations
from datetime import date, datetime
import shutil
from typing import Dict, List
import os
import subprocess
import unicodedata
from SrtEntry import SrtEntry

from pydub import AudioSegment

import tts
from config import Config
import Prompts

MP3_QUALITY: int = 3
MP3_HZ: int = 48_000


def save_mp4_graphic(*, dataset: str, tags: Dict[str, str], exercise_no: int, img_out_dir: str, review_count: int, introduced_count: int, hidden_count: int, end_note: str | None):
    svg_title: str
    with open("data/svg/title_template.svg", "r") as r:
        svg_title = r.read()
    svg_title = svg_title.replace("_album_", tags["album"])
    title = tags["title"]
    if "]" in title:
        svg_title = svg_title.replace("_title1_", title[:title.index("]") + 1].strip())
        svg_title = svg_title.replace("_title2_", title[title.index("]") + 1:].strip())
    else:
        svg_title = svg_title.replace("_title1_", tags["title"])
        svg_title = svg_title.replace("_title2_", " ")
    svg_title = svg_title.replace("_artist_", tags["artist"])

    if end_note:
        svg_title = svg_title.replace("_end_note_", end_note)
    else:
        svg_title = svg_title.replace("_end_note_", " ")

    new_items: str = f"{introduced_count + hidden_count:,}"
    old_items: str = f"{review_count:,}"
    svg_title = svg_title.replace("_new_", new_items)
    svg_title = svg_title.replace("_old_", old_items)

    svg_name: str = f"{dataset}-{exercise_no + 1:04}.svg"
    print(f"Creating {svg_name}.")
    output_svg: str = os.path.join(img_out_dir, svg_name)
    with open(output_svg, "w") as w:
        w.write(svg_title)
    png_name: str = f"{dataset}-{exercise_no + 1:04}.png"
    output_png: str = os.path.join(img_out_dir, png_name)
    cmd: list[str] = list()
    cmd.append("inkscape")
    cmd.append("-o")
    cmd.append(output_png)
    cmd.append("-C")
    cmd.append("--export-background=white")
    cmd.append("--export-background-opacity=1.0")
    cmd.append("--export-png-color-mode=RGB_16")
    cmd.append("--export-area-page")
    cmd.append(output_svg)
    print(f"Creating {png_name}.")
    subprocess.run(cmd, check=True, stdout=subprocess.DEVNULL, stderr=subprocess.STDOUT)
    return output_png

def save_mp4(*,
        dataset: str,
        tags: Dict[str,str],
        exercise_no: int,
        mp4_out_dir: str,
        output_png: str,
        output_mp3: str,
        output_srt: str
    ) -> str:
    mp4_name: str = f"{dataset}-{exercise_no + 1:04}.mp4"
    output_mp4: str = os.path.join(mp4_out_dir, mp4_name)

    cmd: list[str] = list()
    cmd.append("ffmpeg")
    cmd.append("-nostdin")  # non-interactive
    cmd.append("-y")  # overwrite
    cmd.append("-r")  # input frame rate
    cmd.append("1")
    cmd.append("-loop")
    cmd.append("1")
    cmd.append("-i")
    cmd.append(output_png)
    cmd.append("-i")
    cmd.append(output_mp3)
    cmd.append("-i")
    cmd.append(output_srt)
    cmd.append("-c:s")
    cmd.append("mov_text")
    cmd.append("-q:a")
    cmd.append("3")
    cmd.append("-pix_fmt")
    cmd.append("yuv420p")
    cmd.append("-shortest")
    cmd.append("-r")  # output frame rate
    cmd.append("1")
    # cmd.append("23.976")
    cmd.append("-tune")
    cmd.append("stillimage")
    save_title = tags["title"]
    if tags["album"]:
        tags["title"] = tags["title"] + " (" + tags["album"]+")"
    for k, v in tags.items():
        cmd.append("-metadata")
        cmd.append(f"{k}={v}")
    tags["title"] = save_title
    cmd.append("-movflags")
    cmd.append("+faststart")
    cmd.append(output_mp4)

    print(f"Creating {mp4_name}.")
    subprocess.run(cmd, check=True, stdout=subprocess.DEVNULL, stderr=subprocess.STDOUT)
    return output_mp4

def create_audio_lesson_tags(*, dataset: str, exercise_no: int, challenge_start: str, challenge_stop: str) -> Dict[str, str]:
    tags: dict[str, str] = dict()

    challenge_start = unicodedata.normalize("NFC", challenge_start)
    challenge_stop = unicodedata.normalize("NFC", challenge_stop)

    if dataset == "cll1-v3":
        tags["album"] = "Cherokee Language Lessons 1 - 3rd Edition"
        tags["title"] = f"CLL 1 [{exercise_no + 1:02d}] {challenge_start} ... {challenge_stop}"
    elif dataset == "beginning-cherokee":
        tags["album"] = "Beginning Cherokee - 2nd Edition"
        tags["title"] = f"BC [{exercise_no + 1:02d}] {challenge_start} ... {challenge_stop}"
    elif dataset == "animals":
        tags["album"] = "Animals"
        tags["title"] = f"Animals [{exercise_no + 1:02d}] {challenge_start} ... {challenge_stop}"
    elif dataset == "bound-pronouns":
        tags["album"] = "Bound Pronouns"
        tags["title"] = f"BP [{exercise_no + 1:02d}] {challenge_start} ... {challenge_stop}"
    elif dataset == "osiyo-tohiju-then-what":
        tags["album"] = "Osiyo, Tohiju? ... Then what?"
        tags["title"] = f"Osiyo [{exercise_no + 1:02d}] {challenge_start} ... {challenge_stop}"
    elif dataset == "ced-sentences":
        tags["album"] = "Example Sentences. Cherokee English Dictionary, 1st Edition"
        tags["title"] = f"C.E.D. Examples [{exercise_no + 1:02d}] {challenge_start} ... {challenge_stop}"
    else:
        tags["album"] = dataset
        tags["title"] = f"[{exercise_no + 1:02d}] {challenge_start} ... {challenge_stop}"

    tags["composer"] = "Michael Conrad"
    tags["copyright"] = f"©{date.today().year} Michael Conrad CC-BY"
    tags["language"] = "chr"
    tags["artist"] = "IMS-Toucan"
    tags["publisher"] = "Michael Conrad"
    tags["track"] = str(exercise_no + 1)
    tags["date"] = str(datetime.utcnow().isoformat(sep="T", timespec="seconds"))
    tags["creation_time"] = str(datetime.utcnow().isoformat(sep="T", timespec="seconds"))
    tags["genre"] = "Spoken"
    tags["comments"] = "https://github.com/CherokeeLanguage/IMS-Toucan"
    tags["year"] = str(date.today().year)

    return tags

def save_mp3_and_srt(*, dataset: str, lead_in: AudioSegment, main_audio: AudioSegment, lead_out: AudioSegment, exercise_no: int,mp3_out_dir:str, srt_out_dir,  first_new_challenge: str, first_review_challenge: str, last_new_challenge: str, last_review_challenge: str, end_note: str, srt_entries: List[SrtEntry]):
    challenge_start: str = first_new_challenge if first_new_challenge else first_review_challenge
    # challenge_start = re.sub("(?i)[^a-z- ]", "", unicodedata.normalize("NFD", challenge_start))
    challenge_start = unicodedata.normalize("NFC", challenge_start).strip()
    while challenge_start[-1] in ".,!?:":
        challenge_start = challenge_start[:-1]

    challenge_stop: str = last_new_challenge if last_new_challenge else last_review_challenge
    # challenge_stop = re.sub("(?i)[^a-z- ]", "", unicodedata.normalize("NFD", challenge_stop))
    challenge_stop = unicodedata.normalize("NFC", challenge_stop).strip()
    while challenge_stop[-1] in ".,!?:":
        challenge_stop = challenge_stop[:-1]

    # https://wiki.multimedia.cx/index.php/FFmpeg_Metadata#MP3
    tags = create_audio_lesson_tags(
        dataset=dataset,
        exercise_no=exercise_no,
        challenge_start=challenge_start,
        challenge_stop=challenge_stop
    )

    # Output exercise audio
    combined_audio: AudioSegment = lead_in.append(main_audio)

    # Add any special end of session notes.
    if end_note:
        combined_audio = combined_audio.append(AudioSegment.silent(2_250))
        combined_audio = combined_audio.append(tts.en_audio(Prompts.AMZ_VOICE_INSTRUCTOR, end_note))
        print(f"* {end_note}")

    combined_audio = combined_audio.append(lead_out)

    # Add leadin offset to SRT entries. Assign sequence numbers. Capitalize first letter.
    for str_entry_no, srt_entry in enumerate(srt_entries):
        srt_entry.seq = str_entry_no + 1
        srt_entry.start += lead_in.duration_seconds  # - 0.125  # appear slightly early
        srt_entry.end += lead_in.duration_seconds  # + 0.125  # disappear slightly late
        srt_entry.text = srt_entry.text[0].upper() + srt_entry.text[1:]

    # Output SRT file for use by ffmpeg mp4 creation process
    srt_name: str = f"{dataset}-{exercise_no + 1:04}.srt"
    output_srt: str = os.path.join(srt_out_dir, srt_name)
    with open(output_srt, "w") as srt:
        for srt_entry in srt_entries:
            srt_text: str = unicodedata.normalize("NFC", str(srt_entry))
            srt.write(srt_text)

    # Output mp3
    mp3_name: str = f"{dataset}-{exercise_no + 1:04}.mp3"
    output_mp3: str = os.path.join(mp3_out_dir, mp3_name)
    minutes: int = int(combined_audio.duration_seconds // 60)
    seconds: int = int(combined_audio.duration_seconds) % 60
    tags["duration"] = f"{minutes:02d}:{seconds:02d}"
    print(f"Creating {mp3_name}. {tags['duration']}.")
    save_title = tags["title"]
    if tags["album"]:
        tags["title"] = tags["title"] + " (" + tags["album"] + ")"
    combined_audio.set_frame_rate(MP3_HZ).export(output_mp3 + ".tmp", format="mp3",
                                                    parameters=["-qscale:a", str(MP3_QUALITY)], tags=tags)
    tags["title"] = save_title
    shutil.move(output_mp3 + ".tmp", output_mp3)

    return output_mp3, output_srt, tags

def save_audio_lesson(cfg: Config, *, 
            dataset:str, out_dir: str, lead_in: AudioSegment, main_audio: AudioSegment, lead_out: AudioSegment, exercise_no: int, review_count: int, introduced_count:int, hidden_count: int, first_new_challenge: str, first_review_challenge: str, last_new_challenge: str, last_review_challenge: str, end_note: str, srt_entries: List[SrtEntry]):
    # Put mp3 for website related stuff in subfolder
    mp3_out_dir: str = os.path.join(out_dir, "mp3")
    os.makedirs(mp3_out_dir, exist_ok=True)

    srt_out_dir: str = os.path.join(out_dir, "srt")
    os.makedirs(srt_out_dir, exist_ok=True)

    output_mp3, output_srt, tags = save_mp3_and_srt(
        dataset=dataset,
        lead_in=lead_in,
        lead_out=lead_out,
        main_audio=main_audio,
        exercise_no=exercise_no,
        mp3_out_dir=mp3_out_dir,
        srt_out_dir=srt_out_dir,
        first_new_challenge=first_new_challenge,
        first_review_challenge=first_review_challenge,
        last_new_challenge=last_new_challenge,
        last_review_challenge=last_review_challenge,
        srt_entries=srt_entries,
        end_note=end_note or ""
    )

    if cfg.create_mp4:
        # Put graphic related stuff in subfolder
        img_out_dir: str = os.path.join(out_dir, "img")
        os.makedirs(img_out_dir, exist_ok=True)

        # Put MP4 related stuff in subfolder
        mp4_out_dir: str = os.path.join(out_dir, "mp4")
        os.makedirs(mp4_out_dir, exist_ok=True)

        # Generate graphic for MP4
        output_png = save_mp4_graphic(
            dataset=dataset,
            tags=tags,
            exercise_no=exercise_no,
            img_out_dir=img_out_dir,
            review_count=review_count,
            introduced_count=introduced_count,
            hidden_count=hidden_count,
            end_note=end_note
        )
        # FIXME: should this be unused?
        output_mp4 = save_mp4(
            dataset=dataset,
            tags=tags,
            exercise_no=exercise_no,
            mp4_out_dir=mp4_out_dir,
            output_png=output_png,
            output_mp3=output_mp3,
            output_srt=output_srt
        )
    
    return tags