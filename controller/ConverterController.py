# ConverterController.py
import io
import os
import subprocess
import tempfile

from PyPDF2 import PdfReader
from fastapi import UploadFile, File

from service.content_preprocessor_gpt import pdf_text_processing, audio_text_processing
from fastapi import APIRouter, HTTPException, Depends, Request
from sqlalchemy.orm import Session

from controller.DatabaseController import get_db
from repository.repository import log_and_save_tokens
from service.stt_service import transcribe_audio_filelike

router = APIRouter()


@router.post("/pdf-to-string")
async def convert_pdf_to_text(pdfFile: UploadFile = File(...), db: Session = Depends(get_db), request: Request = None):
    # 첨부된 파일이 PDF인지 확인
    if pdfFile.content_type != "application/pdf":
        raise HTTPException(status_code=400, detail="유효하지 않은 파일 타입입니다. PDF 파일만 허용됩니다.")
    try:
        # 파일 바이트 읽기
        contents = await pdfFile.read()
        # BytesIO로 래핑하여 PdfReader에 전달
        pdf_reader = PdfReader(io.BytesIO(contents))
        extracted_text = ""
        for page in pdf_reader.pages:
            text = page.extract_text()
            if text:
                extracted_text += text

        result = pdf_text_processing(extracted_text)

        log, usage = log_and_save_tokens(
            db=db,
            api_url=str(request.url),
            method=request.method,
            params={"pdfFile": extracted_text},
            request_tokens=result["request_tokens"],
            response_tokens=result["response_tokens"]
        )

        return {"text": result["result"]}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"PDF 처리 중 오류 발생: {str(e)}")


# 1) 최대 바이트 검사용 dependency
def max_size_200mb(request: Request):
    content_length = request.headers.get("content-length")
    if content_length is None:
        # 헤더가 없으면 일단 허용하거나, 아예 차단하고 싶으면 400/411 처리
        return
    if int(content_length) > 200 * 1024 * 1024:
        raise HTTPException(
            status_code=413,
            detail=f"Payload too large: 최대 200mb 까지 허용됩니다."
        )


def _is_mp3(upload: UploadFile) -> bool:
    """
    content‑type 헤더가 틀릴 수 있으므로 ffprobe 로 코덱을 확인
    """
    # 1) 파일을 temp 로 저장
    with tempfile.NamedTemporaryFile(delete=False) as tmp:
        tmp.write(upload.file.read())
        path = tmp.name

    try:
        codec = subprocess.check_output(
            [
                "ffprobe", "-v", "error",
                "-select_streams", "a:0",
                "-show_entries", "stream=codec_name",
                "-of", "default=noprint_wrappers=1:nokey=1",
                path,
            ]
        ).decode().strip()
        return codec == "mp3"
    finally:
        upload.file.seek(0)  # 이후 read() 위해 포인터 원위치
        os.remove(path)


# 2) 라우트에 dependencies 인자로 추가
@router.post(
    "/audio-to-string",
    dependencies=[Depends(max_size_200mb)]
)
async def convert_audio_to_text(
        audioFile: UploadFile = File(...),
        db: Session = Depends(get_db),
        request: Request = None
):
    print("Audio file received.", flush=True)
    if not _is_mp3(audioFile):
        raise HTTPException(
            status_code=415,
            detail="지원되지 않는 오디오 형식입니다. MP3 파일만 업로드해 주세요.",
        )
    # 여기는 content-length 검사 통과된 요청만 들어옵니다.
    if not audioFile.content_type.startswith("audio/"):
        raise HTTPException(400, "오디오 파일만 허용됩니다.")
    audio_bytes = await audioFile.read()
    transcript = transcribe_audio_filelike(audio_bytes)
    # 전사 결과를 정제하는 함수 호출
    result = audio_text_processing(transcript)
    log, usage = log_and_save_tokens(
        db=db,
        api_url=str(request.url),
        method=request.method,
        params={"audioFile": transcript},
        request_tokens=result["request_tokens"],
        response_tokens=result["response_tokens"]
    )

    return {"text": result["result"]}
