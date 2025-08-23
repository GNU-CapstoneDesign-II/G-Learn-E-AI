import tiktoken


def get_tokenizer_for_model(model_name: str):
    try:
        # 공식 지원 모델이면 자동 매핑
        return tiktoken.encoding_for_model(model_name)
    except KeyError:
        # 미지원 모델은 최신 GPT 계열 표준 인코딩으로 대체
        return tiktoken.get_encoding("cl100k_base")