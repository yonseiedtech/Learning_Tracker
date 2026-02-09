import os
import subprocess
import tempfile
import shutil
from pdf2image import convert_from_path


SLIDES_BASE_DIR = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(__file__))), 'static', 'slides')


def ensure_slides_dir():
    os.makedirs(SLIDES_BASE_DIR, exist_ok=True)


def convert_pptx_to_images(pptx_file_path, deck_id):
    deck_dir = os.path.join(SLIDES_BASE_DIR, str(deck_id))
    os.makedirs(deck_dir, exist_ok=True)
    
    with tempfile.TemporaryDirectory() as tmp_dir:
        pdf_output_dir = tmp_dir
        
        result = subprocess.run([
            'libreoffice',
            '--headless',
            '--convert-to', 'pdf',
            '--outdir', pdf_output_dir,
            pptx_file_path
        ], capture_output=True, text=True, timeout=120)
        
        if result.returncode != 0:
            raise Exception(f'LibreOffice 변환 실패: {result.stderr}')
        
        pdf_files = [f for f in os.listdir(pdf_output_dir) if f.endswith('.pdf')]
        if not pdf_files:
            raise Exception('PDF 변환 결과를 찾을 수 없습니다.')
        
        pdf_path = os.path.join(pdf_output_dir, pdf_files[0])
        
        images = convert_from_path(pdf_path, dpi=150, fmt='png')
        
        max_slides = 100
        if len(images) > max_slides:
            raise Exception(f'슬라이드가 {len(images)}장입니다. 최대 {max_slides}장까지 지원됩니다.')
        
        slide_count = 0
        for i, image in enumerate(images):
            image_path = os.path.join(deck_dir, f'{i}.png')
            image.save(image_path, 'PNG', optimize=True, quality=85)
            slide_count += 1
        
        return slide_count, deck_dir


def delete_deck_images(deck_dir):
    if deck_dir and os.path.exists(deck_dir):
        shutil.rmtree(deck_dir, ignore_errors=True)
