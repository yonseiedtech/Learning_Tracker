import os
import uuid
from datetime import timedelta
from app.firebase_init import get_bucket


def upload_file(file_data, destination_path, content_type=None):
    """Upload file bytes to Firebase Storage.

    Args:
        file_data: bytes or file-like object
        destination_path: path in the bucket (e.g. 'users/uid/profile.png')
        content_type: MIME type

    Returns:
        The storage path (same as destination_path)
    """
    bucket = get_bucket()
    blob = bucket.blob(destination_path)
    if content_type:
        blob.content_type = content_type
    if isinstance(file_data, bytes):
        blob.upload_from_string(file_data, content_type=content_type)
    else:
        blob.upload_from_file(file_data, content_type=content_type)
    return destination_path


def download_file(storage_path):
    """Download file from Firebase Storage.

    Returns:
        bytes
    """
    bucket = get_bucket()
    blob = bucket.blob(storage_path)
    return blob.download_as_bytes()


def delete_file(storage_path):
    """Delete a file from Firebase Storage."""
    bucket = get_bucket()
    blob = bucket.blob(storage_path)
    if blob.exists():
        blob.delete()


def get_signed_url(storage_path, expiration_minutes=60):
    """Get a signed URL for temporary access.

    Args:
        storage_path: path in the bucket
        expiration_minutes: URL validity in minutes

    Returns:
        Signed URL string
    """
    bucket = get_bucket()
    blob = bucket.blob(storage_path)
    if not blob.exists():
        return None
    url = blob.generate_signed_url(
        version='v4',
        expiration=timedelta(minutes=expiration_minutes),
        method='GET'
    )
    return url


def upload_profile_image(uid, file_data, ext):
    """Upload user profile image.

    Returns:
        Storage path
    """
    path = f'users/{uid}/profile.{ext}'
    content_type = f'image/{ext}' if ext != 'jpg' else 'image/jpeg'
    return upload_file(file_data, path, content_type)


def upload_video(course_id, file_data, filename):
    """Upload course video file.

    Returns:
        Storage path
    """
    path = f'courses/{course_id}/video/{filename}'
    return upload_file(file_data, path)


def upload_material(course_id, file_data, filename, content_type=None):
    """Upload course material file.

    Returns:
        Storage path
    """
    path = f'courses/{course_id}/materials/{filename}'
    return upload_file(file_data, path, content_type)


def upload_assignment(course_id, user_id, file_data, filename):
    """Upload assignment submission file.

    Returns:
        Storage path
    """
    path = f'courses/{course_id}/assignments/{user_id}/{filename}'
    return upload_file(file_data, path)


def upload_slide_image(deck_id, slide_index, image_data):
    """Upload a single slide image.

    Returns:
        Storage path
    """
    path = f'slides/{deck_id}/{slide_index}.png'
    return upload_file(image_data, path, 'image/png')


def get_slide_image_url(deck_id, slide_index, expiration_minutes=120):
    """Get signed URL for a slide image."""
    path = f'slides/{deck_id}/{slide_index}.png'
    return get_signed_url(path, expiration_minutes)


def delete_slide_deck_images(deck_id, slide_count):
    """Delete all slide images for a deck."""
    bucket = get_bucket()
    for i in range(slide_count):
        blob = bucket.blob(f'slides/{deck_id}/{i}.png')
        if blob.exists():
            blob.delete()


def upload_guide_attachment(post_id, file_data, filename, content_type=None):
    """Upload guide post attachment.

    Returns:
        Storage path
    """
    unique = uuid.uuid4().hex[:8]
    path = f'guides/{post_id}/attachments/{unique}_{filename}'
    return upload_file(file_data, path, content_type)
