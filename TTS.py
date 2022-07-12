from __future__ import annotations

import shutil

import boto3
import hashlib
import os
import re
import subprocess
import textwrap
import unicodedata
from boto3_type_annotations.polly import Client as Polly
from pydub import AudioSegment
from pydub import effects

from main import AMZ_HZ
from main import CACHE_CHR
from main import CACHE_EN


def tts_chr(voice: str | None, text_chr: str):
    mp3_chr: str = get_mp3_chr(voice, text_chr)
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
    cmd.append(mp3_chr+".tmp")
    cmd.append("--text")
    cmd.append(text_chr)
    result = subprocess.run(cmd, capture_output=True)
    if result.returncode:
        print(result.stdout.decode())
        print(result.stderr.decode())
        raise Exception("run_tts.py fail")
    else:
        shutil.move(mp3_chr+".tmp", mp3_chr)


def get_mp3_chr(voice: str | None, text_chr: str) -> str:
    # text_chr = re.sub("\\s+", " ", textwrap.dedent(text_chr)).strip()
    mp3_name_chr: str = get_filename(voice, text_chr)
    mp3_chr: str = os.path.join(CACHE_CHR, mp3_name_chr)
    return mp3_chr


def chr_audio(voice: str | None, text_chr: str) -> AudioSegment:
    tts_chr(voice, text_chr)
    mp3_file = get_mp3_chr(voice, text_chr)
    return effects.normalize(AudioSegment.from_file(mp3_file))


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
    with open(mp3_en+".tmp", "wb") as w:
        w.write(response["AudioStream"].read())
    shutil.move(mp3_en+".tmp", mp3_en)


def get_mp3_en(voice: str | None, text_en: str) -> str:
    text_en = re.sub("\\s+", " ", text_en).strip()
    mp3_name_en: str = get_filename(voice, text_en)
    mp3_en: str = os.path.join(CACHE_EN, mp3_name_en)
    return mp3_en


def en_audio(voice: str | None, text_en: str) -> AudioSegment:
    tts_en(voice, text_en)
    mp3_file = get_mp3_en(voice, text_en)
    return effects.normalize(AudioSegment.from_file(mp3_file))


def get_filename(voice: str, text: str):
    text = re.sub("\\s+", " ", textwrap.dedent(text)).strip()
    text = text.lower()
    if not voice:
        voice = "-"
    sha1: str
    sha1 = hashlib.sha1(text.encode("UTF-8")).hexdigest()
    _ = unicodedata.normalize("NFD", text).replace(" ", "_")
    _ = unicodedata.normalize("NFC", re.sub("[^a-z_]", "", _))
    if len(_) > 32:
        _ = _[:32]
    filename: str = f"{_}_{voice}_{sha1}.mp3"
    return filename
