"""
Mock imghdr module for compatibility with Python 3.13+ and Render.com
This module provides basic image type detection functionality that was removed from the standard library.
"""

import os
from typing import Optional, BinaryIO


def what(file: str | BinaryIO | bytes, h: bytes = None) -> Optional[str]:
    """
    Determine the type of image contained in a file or bytes.

    Args:
        file: File path, file-like object, or bytes
        h: Optional header bytes

    Returns:
        Image type as string (e.g., 'jpeg', 'png', 'gif') or None if unknown
    """
    if h is None:
        if isinstance(file, str):
            if not os.path.exists(file):
                return None
            with open(file, 'rb') as f:
                h = f.read(32)
        elif hasattr(file, 'read'):
            h = file.read(32)
            file.seek(0)  # Reset file pointer
        elif isinstance(file, bytes):
            h = file[:32]
        else:
            return None

    # Check for common image formats
    if len(h) >= 2:
        # JPEG
        if h[0:2] == b'\xff\xd8':
            return 'jpeg'

        # PNG
        if h[0:8] == b'\x89PNG\r\n\x1a\n':
            return 'png'

        # GIF
        if h[0:6] in (b'GIF87a', b'GIF89a'):
            return 'gif'

        # BMP
        if h[0:2] == b'BM':
            return 'bmp'

        # WebP
        if h[0:4] == b'RIFF' and len(h) >= 12 and h[8:12] == b'WEBP':
            return 'webp'

    return None


# Legacy function names for backward compatibility
def test_jpeg(h: bytes, f: BinaryIO = None) -> int:
    """Test if data is JPEG format."""
    return 1 if h[:2] == b'\xff\xd8' else 0


def test_png(h: bytes, f: BinaryIO = None) -> int:
    """Test if data is PNG format."""
    return 1 if h[:8] == b'\x89PNG\r\n\x1a\n' else 0


def test_gif(h: bytes, f: BinaryIO = None) -> int:
    """Test if data is GIF format."""
    return 1 if h[:6] in (b'GIF87a', b'GIF89a') else 0


def test_bmp(h: bytes, f: BinaryIO = None) -> int:
    """Test if data is BMP format."""
    return 1 if h[:2] == b'BM' else 0


def test_webp(h: bytes, f: BinaryIO = None) -> int:
    """Test if data is WebP format."""
    return 1 if h[:4] == b'RIFF' and len(h) >= 12 and h[8:12] == b'WEBP' else 0


# List of supported formats
tests = [
    ('jpeg', test_jpeg),
    ('png', test_png),
    ('gif', test_gif),
    ('bmp', test_bmp),
    ('webp', test_webp),
]