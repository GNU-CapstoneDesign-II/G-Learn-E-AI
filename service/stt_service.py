# app/gpt_service.py  ★ FFmpeg silencedetect + 25 MiB 보장 버전
import os
import io
import re
import math
import logging
import subprocess
import tempfile
from typing import List, Tuple

from dotenv import load_dotenv
from openai import OpenAI

# ─────────────────── 기본 세팅 ────────────────────
load_dotenv()
client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))

logger = logging.getLogger("gpt_service")
logger.setLevel(logging.INFO)
handler = logging.StreamHandler()
handler.setFormatter(logging.Formatter("[%(asctime)s] %(levelname)s: %(message)s"))
logger.addHandler(handler)

MAX_CHUNK_BYTES = 25 * 1024 * 1024          # Whisper 업로드 한도(25 MiB)
SILENCE_THRESH  = -40                       # dBFS
SILENCE_LEN_S   = 0.5                       # 최소 무음 지속 시간(초)
SEGMENT_TIME_S  = 180                       # fallback: 3 분 단위 고정 분할

# ───────────────── silence 구간 탐지 ─────────────────
_silence_start_re = re.compile(r"silence_start: (?P<ts>\d+\.?\d*)")
_silence_end_re   = re.compile(r"silence_end: (?P<ts>\d+\.?\d*)")


def _detect_nonsilent_ranges(src: str, duration: float) -> List[Tuple[float, float]]:
    """ffmpeg silencedetect 로 (start, end) 비무음 구간 목록 반환"""
    cmd = [
        "ffmpeg", "-hide_banner", "-loglevel", "info",
        "-i", src,
        "-af", f"silencedetect=n={SILENCE_THRESH}dB:d={SILENCE_LEN_S}",
        "-f", "null", "-"
    ]
    res = subprocess.run(cmd, stderr=subprocess.PIPE, text=True)
    starts, ends = [], []
    for ln in res.stderr.splitlines():
        m1 = _silence_start_re.search(ln)
        m2 = _silence_end_re.search(ln)
        if m1: starts.append(float(m1.group("ts")))
        if m2: ends.append(float(m2.group("ts")))

    starts.sort(); ends.sort()
    nonsilent, prev = [], 0.0
    for s, e in zip(starts, ends):
        if s > prev:
            nonsilent.append((prev, s))
        prev = e
    if prev < duration:
        nonsilent.append((prev, duration))
    logger.info(f"Non‑silent segments detected: {len(nonsilent)}")
    return nonsilent


# ───────────────── 분할 & 패킹 ──────────────────
def _split_and_pack_ffmpeg(audio_bytes: bytes) -> List[io.BytesIO]:
    """무음 제외 구간을 추출해 25 MiB 이하 청크(BytesIO) 리스트 반환"""
    with tempfile.NamedTemporaryFile(suffix=".mp3", delete=False) as tmp:
        tmp.write(audio_bytes)
        src_path = tmp.name

    # 전체 길이
    dur = float(subprocess.check_output([
        "ffprobe", "-v", "error",
        "-show_entries", "format=duration",
        "-of", "default=noprint_wrappers=1:nokey=1", src_path
    ]).decode().strip())
    logger.info(f"Audio length: {dur:.1f}s")

    # 무음 제거 구간 목록
    try:
        segs = _detect_nonsilent_ranges(src_path, dur)
    except Exception as e:
        logger.warning(f"silencedetect 실패({e}); {SEGMENT_TIME_S}s 고정 분할 사용")
        segs = [(i, min(i + SEGMENT_TIME_S, dur)) for i in range(0, int(dur), SEGMENT_TIME_S)]

    chunks, buf, buf_size = [], io.BytesIO(), 0

    for idx, (st, ed) in enumerate(segs, 1):
        # copy 모드 추출
        seg_bytes = subprocess.check_output([
            "ffmpeg", "-hide_banner", "-loglevel", "error",
            "-ss", str(st), "-to", str(ed),
            "-i", src_path, "-c", "copy", "-f", "mp3", "pipe:1"
        ])

        # 세그먼트 자체가 한도를 넘는 경우 시간 기준으로 다시 나눔
        if len(seg_bytes) > MAX_CHUNK_BYTES:
            parts = math.ceil(len(seg_bytes) / MAX_CHUNK_BYTES)
            part_dur = (ed - st) / parts
            logger.info(f"Seg {idx} too big → split into {parts}×{part_dur:.1f}s")
            for p in range(parts):
                p_st, p_ed = st + p * part_dur, min(st + (p + 1) * part_dur, ed)
                segs.insert(idx + p, (p_st, p_ed))
            continue  # 원본 oversize 세그먼트는 스킵

        # 패킹
        if buf_size + len(seg_bytes) > MAX_CHUNK_BYTES:  # 새 청크 시작
            buf.seek(0)
            chunks.append(buf)
            logger.info(f"Chunk {len(chunks)} finalized ({buf_size} bytes)")
            buf, buf_size = io.BytesIO(), 0

        buf.write(seg_bytes)
        buf_size += len(seg_bytes)

    if buf_size > 0:
        buf.seek(0)
        chunks.append(buf)
        logger.info(f"Chunk {len(chunks)} finalized ({buf_size} bytes)")

    os.remove(src_path)
    logger.info(f"Total chunks produced: {len(chunks)}")
    return chunks


# ───────────────── Whisper 호출 ──────────────────
def transcribe_audio_filelike(
        audio_bytes: bytes,
        model: str = "whisper-1",
        response_format: str = "text",
        language: str = "ko"
) -> str:
    """무음 제거 → 25 MiB 청크 → Whisper 순차 호출 → 텍스트 병합"""
    logger.info("★ Transcription start")
    chunks = _split_and_pack_ffmpeg(audio_bytes)

    texts: List[str] = []
    for i, chunk in enumerate(chunks, 1):
        chunk.name = f"chunk_{i}.mp3"      # 확장자 전달 필수
        size = chunk.getbuffer().nbytes
        logger.info(f"→ Sending chunk {i}/{len(chunks)} ({size} bytes)")

        resp = client.audio.transcriptions.create(
            model=model,
            file=chunk,
            response_format=response_format,
            language=language
        )
        text = resp if isinstance(resp, str) else getattr(resp, "text", resp["text"])
        logger.info(f"← Chunk {i} done ({len(text)} chars)")
        texts.append(text)

    logger.info("★ Transcription finished")
    return "\n".join(texts)
