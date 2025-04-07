# ConverterController.py
import io

from PyPDF2 import PdfReader
from fastapi import UploadFile, File

from service.content_preprocessor_gpt import pdf_text_processing
from fastapi import APIRouter, HTTPException, Depends, Request
from sqlalchemy.orm import Session

from controller.DatabaseController import get_db
from repository.repository import log_and_save_tokens

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


@router.post("/audio-to-string")
async def convert_audio_to_text(audioFile: UploadFile = File(...)):
    try:
        print("audioFile:", audioFile)
        return {"text": "test audio converted"}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"오디오 처리 중 오류 발생: {str(e)}")
