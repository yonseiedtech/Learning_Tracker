import os
import subprocess
import tempfile
import shutil
from pdf2image import convert_from_path
from app.services.storage import upload_slide_image


ALLOWED_EXTENSIONS = {'.pptx', '.ppt', '.pdf'}


def is_pdf(file_path):
    return file_path.lower().endswith('.pdf')


def convert_file_to_images(file_path, deck_id):
    with tempfile.TemporaryDirectory() as tmp_dir:
        if is_pdf(file_path):
            pdf_path = file_path
        else:
            result = subprocess.run([
                'libreoffice',
                '--headless',
                '--convert-to', 'pdf',
                '--outdir', tmp_dir,
                file_path
            ], capture_output=True, text=True, timeout=120)

            if result.returncode != 0:
                raise Exception(f'LibreOffice 변환 실패: {result.stderr}')

            pdf_files = [f for f in os.listdir(tmp_dir) if f.endswith('.pdf')]
            if not pdf_files:
                raise Exception('PDF 변환 결과를 찾을 수 없습니다.')

            pdf_path = os.path.join(tmp_dir, pdf_files[0])

        images = convert_from_path(pdf_path, dpi=150, fmt='png')

        max_slides = 100
        if len(images) > max_slides:
            raise Exception(f'슬라이드가 {len(images)}장입니다. 최대 {max_slides}장까지 지원됩니다.')

        slide_count = 0
        for i, image in enumerate(images):
            image_path = os.path.join(tmp_dir, f'{i}.png')
            image.save(image_path, 'PNG', optimize=True, quality=85)
            with open(image_path, 'rb') as f:
                upload_slide_image(deck_id, i, f.read())
            slide_count += 1

    return slide_count


def convert_pptx_to_images(file_path, deck_id):
    return convert_file_to_images(file_path, deck_id)
