import os
import json
import tempfile
import subprocess
from pathlib import Path
from typing import List, Optional
from concurrent.futures import ThreadPoolExecutor, as_completed
from tenacity import retry, stop_after_attempt, wait_exponential, retry_if_exception

from google import genai
from google.genai import types

AI_INTEGRATIONS_GEMINI_API_KEY = os.environ.get("AI_INTEGRATIONS_GEMINI_API_KEY")
AI_INTEGRATIONS_GEMINI_BASE_URL = os.environ.get("AI_INTEGRATIONS_GEMINI_BASE_URL")

client = genai.Client(
    api_key=AI_INTEGRATIONS_GEMINI_API_KEY,
    http_options={
        'api_version': '',
        'base_url': AI_INTEGRATIONS_GEMINI_BASE_URL   
    }
)

CHUNK_SIZE_BYTES = 8 * 1024 * 1024

def is_rate_limit_error(exception: BaseException) -> bool:
    error_msg = str(exception)
    return (
        "429" in error_msg 
        or "RATELIMIT_EXCEEDED" in error_msg
        or "quota" in error_msg.lower() 
        or "rate limit" in error_msg.lower()
        or (hasattr(exception, 'status') and exception.status == 429)
    )


def chunk_media(buffer: bytes, mime_type: str) -> list[bytes]:
    if len(buffer) <= CHUNK_SIZE_BYTES:
        return [buffer]
    
    with tempfile.TemporaryDirectory(prefix='media-') as temp_dir:
        ext = mime_type.split('/')[-1] or 'mp4'
        input_path = Path(temp_dir) / f'input.{ext}'
        input_path.write_bytes(buffer)
        
        result = subprocess.run(
            [
                'ffprobe', '-v', 'error', '-show_entries', 
                'format=duration', '-of', 
                'default=noprint_wrappers=1:nokey=1', str(input_path)
            ],
            capture_output=True,
            text=True,
            check=True
        )
        duration = float(result.stdout.strip())
        
        num_chunks = (len(buffer) + CHUNK_SIZE_BYTES - 1) // CHUNK_SIZE_BYTES
        segment_duration = duration / num_chunks
        
        chunks: list[bytes] = []
        for i in range(num_chunks):
            output_path = Path(temp_dir) / f'chunk_{i}.{ext}'
            subprocess.run(
                [
                    'ffmpeg', '-i', str(input_path),
                    '-ss', str(i * segment_duration),
                    '-t', str(segment_duration),
                    '-c', 'copy',
                    '-avoid_negative_ts', '1',
                    '-y', str(output_path)
                ],
                capture_output=True,
                check=True
            )
            chunks.append(output_path.read_bytes())
        
        return chunks


class CheckpointGenerator:
    
    CHECKPOINT_PROMPT = """당신은 교육 전문가입니다. 제공된 강의 자료를 분석하여 학습 체크포인트를 생성해주세요.

각 체크포인트는 다음 형식의 JSON 배열로 반환해주세요:
[
    {
        "order": 1,
        "title": "체크포인트 제목 (20자 이내)",
        "description": "학습 목표 또는 주요 내용 설명 (100자 이내)",
        "estimated_minutes": 예상 소요 시간(분)
    }
]

규칙:
1. 체크포인트는 5-15개 사이로 생성
2. 각 체크포인트는 명확한 학습 목표를 포함
3. 순서대로 학습할 수 있도록 논리적 흐름 유지
4. 예상 시간은 현실적으로 설정 (3-15분)
5. 제목은 간결하고 명확하게
6. JSON 형식만 반환 (추가 설명 없이)

강의 내용:
"""

    TRANSCRIPTION_PROMPT = """다음 오디오/비디오 콘텐츠를 분석하고 전사해주세요.
음성 내용을 정확하게 텍스트로 변환하고, 주요 토픽과 시간대를 구분해주세요.

결과는 다음 형식으로 반환:
{
    "transcript": "전체 전사문",
    "segments": [
        {
            "time_marker": "시간 또는 순서 표시",
            "content": "해당 구간의 내용",
            "topic": "주요 주제"
        }
    ]
}
"""

    @staticmethod
    @retry(
        stop=stop_after_attempt(5),
        wait=wait_exponential(multiplier=1, min=2, max=60),
        retry=retry_if_exception(is_rate_limit_error),
        reraise=True
    )
    def generate_from_text(text: str) -> List[dict]:
        prompt = CheckpointGenerator.CHECKPOINT_PROMPT + text
        
        response = client.models.generate_content(
            model="gemini-2.5-flash",
            contents=prompt,
            config=types.GenerateContentConfig(
                response_mime_type="application/json"
            )
        )
        
        result_text = response.text or "[]"
        try:
            checkpoints = json.loads(result_text)
            return checkpoints if isinstance(checkpoints, list) else []
        except json.JSONDecodeError:
            import re
            json_match = re.search(r'\[.*\]', result_text, re.DOTALL)
            if json_match:
                return json.loads(json_match.group())
            return []

    @staticmethod
    @retry(
        stop=stop_after_attempt(5),
        wait=wait_exponential(multiplier=1, min=2, max=60),
        retry=retry_if_exception(is_rate_limit_error),
        reraise=True
    )
    def analyze_ppt(file_data: bytes, filename: str) -> dict:
        mime_type = "application/vnd.openxmlformats-officedocument.presentationml.presentation"
        if filename.endswith('.ppt'):
            mime_type = "application/vnd.ms-powerpoint"
        elif filename.endswith('.pdf'):
            mime_type = "application/pdf"
        
        prompt = """이 프레젠테이션/문서를 분석하여 다음 정보를 JSON 형식으로 반환해주세요:
{
    "title": "강의 제목",
    "summary": "전체 내용 요약 (200자 이내)",
    "slides_content": "각 슬라이드/페이지의 주요 내용을 순서대로 설명",
    "key_topics": ["주요 주제1", "주요 주제2", ...]
}"""
        
        response = client.models.generate_content(
            model="gemini-2.5-flash",
            contents=[
                prompt,
                types.Part(
                    inline_data=types.Blob(
                        mime_type=mime_type,
                        data=file_data
                    )
                )
            ],
            config=types.GenerateContentConfig(
                response_mime_type="application/json"
            )
        )
        
        result_text = response.text or "{}"
        try:
            return json.loads(result_text)
        except json.JSONDecodeError:
            return {"summary": result_text, "title": filename, "key_topics": []}

    @staticmethod
    def analyze_media(buffer: bytes, mime_type: str = "video/mp4") -> dict:
        chunks = chunk_media(buffer, mime_type)
        is_video = mime_type.startswith("video/")
        
        def process_chunk(i: int, chunk: bytes) -> tuple[int, str]:
            prompt = (
                f"이 비디오의 {i + 1}/{len(chunks)} 부분을 분석하세요: 주요 내용, 핵심 개념, 설명되는 토픽을 한국어로 작성."
                if is_video
                else f"이 오디오의 {i + 1}/{len(chunks)} 부분을 전사하세요: 음성 내용을 한국어 텍스트로 변환하고 주요 주제를 파악."
            )
            
            @retry(
                stop=stop_after_attempt(7),
                wait=wait_exponential(multiplier=1, min=2, max=128),
                retry=retry_if_exception(is_rate_limit_error),
                reraise=True
            )
            def generate_chunk_analysis() -> str:
                response = client.models.generate_content(
                    model="gemini-2.5-flash",
                    contents=[
                        prompt,
                        types.Part(
                            inline_data=types.Blob(
                                mime_type=mime_type,
                                data=chunk
                            )
                        )
                    ]
                )
                return response.text or ""
            
            return (i, generate_chunk_analysis())
        
        analyses: list[str] = [""] * len(chunks)
        with ThreadPoolExecutor(max_workers=2) as executor:
            futures = {executor.submit(process_chunk, i, chunk): i for i, chunk in enumerate(chunks)}
            for future in as_completed(futures):
                idx, analysis = future.result()
                analyses[idx] = analysis
        
        combined = "\n\n".join([f"[파트 {i + 1}]\n{a}" for i, a in enumerate(analyses)])
        
        return {
            "transcript": combined,
            "chunk_count": len(chunks),
            "is_video": is_video
        }

    @staticmethod
    def generate_checkpoints_from_ppt(file_data: bytes, filename: str) -> List[dict]:
        analysis = CheckpointGenerator.analyze_ppt(file_data, filename)
        content = f"""
강의 제목: {analysis.get('title', '')}
요약: {analysis.get('summary', '')}
슬라이드 내용: {analysis.get('slides_content', '')}
주요 주제: {', '.join(analysis.get('key_topics', []))}
"""
        return CheckpointGenerator.generate_from_text(content)

    @staticmethod
    def generate_checkpoints_from_media(buffer: bytes, mime_type: str) -> tuple[List[dict], str]:
        analysis = CheckpointGenerator.analyze_media(buffer, mime_type)
        transcript = analysis.get('transcript', '')
        checkpoints = CheckpointGenerator.generate_from_text(transcript)
        return checkpoints, transcript

    @staticmethod
    @retry(
        stop=stop_after_attempt(5),
        wait=wait_exponential(multiplier=1, min=2, max=60),
        retry=retry_if_exception(is_rate_limit_error),
        reraise=True
    )
    def analyze_slide_images(image_paths: List[str]) -> dict:
        contents = [
            """이 프레젠테이션 슬라이드 이미지들을 순서대로 분석하여 다음 정보를 JSON 형식으로 반환해주세요:
{
    "title": "강의 제목 (슬라이드 내용에서 추론)",
    "summary": "전체 내용 요약 (200자 이내)",
    "slides_content": "각 슬라이드의 주요 내용을 순서대로 설명",
    "key_topics": ["주요 주제1", "주요 주제2", ...]
}

각 슬라이드의 텍스트, 다이어그램, 이미지 내용을 최대한 상세히 분석해주세요."""
        ]

        for img_path in image_paths:
            with open(img_path, 'rb') as f:
                img_data = f.read()
            contents.append(
                types.Part(
                    inline_data=types.Blob(
                        mime_type="image/png",
                        data=img_data
                    )
                )
            )

        response = client.models.generate_content(
            model="gemini-2.5-flash",
            contents=contents,
            config=types.GenerateContentConfig(
                response_mime_type="application/json"
            )
        )

        result_text = response.text or "{}"
        try:
            return json.loads(result_text)
        except json.JSONDecodeError:
            return {"summary": result_text, "title": "", "key_topics": []}

    @staticmethod
    def generate_checkpoints_from_slide_images(image_paths: List[str]) -> List[dict]:
        analysis = CheckpointGenerator.analyze_slide_images(image_paths)
        content = f"""
강의 제목: {analysis.get('title', '')}
요약: {analysis.get('summary', '')}
슬라이드 내용: {analysis.get('slides_content', '')}
주요 주제: {', '.join(analysis.get('key_topics', []))}
"""
        return CheckpointGenerator.generate_from_text(content)

    @staticmethod
    def transcribe_audio(buffer: bytes, mime_type: str = "audio/mpeg") -> str:
        analysis = CheckpointGenerator.analyze_media(buffer, mime_type)
        return analysis.get('transcript', '')
