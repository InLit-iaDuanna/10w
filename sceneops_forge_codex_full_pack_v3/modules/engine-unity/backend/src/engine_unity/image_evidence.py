"""Decode camera PNG evidence with macOS ImageIO, without installing image services."""
import ctypes as c
import sys
from pathlib import Path


def inspect_png(path: Path) -> dict:
    if sys.platform != 'darwin':
        raise RuntimeError('PNG decoding is currently supported only on the macOS prototype host.')
    cf = c.CDLL('/System/Library/Frameworks/CoreFoundation.framework/CoreFoundation')
    io = c.CDLL('/System/Library/Frameworks/ImageIO.framework/ImageIO')
    cg = c.CDLL('/System/Library/Frameworks/CoreGraphics.framework/CoreGraphics')
    def signature(library, name, result, args):
        function = getattr(library, name); function.restype = result; function.argtypes = args
        return function
    url_create = signature(cf, 'CFURLCreateFromFileSystemRepresentation', c.c_void_p, [c.c_void_p, c.c_char_p, c.c_long, c.c_bool])
    release = signature(cf, 'CFRelease', None, [c.c_void_p])
    source_create = signature(io, 'CGImageSourceCreateWithURL', c.c_void_p, [c.c_void_p, c.c_void_p])
    decode = signature(io, 'CGImageSourceCreateImageAtIndex', c.c_void_p, [c.c_void_p, c.c_size_t, c.c_void_p])
    width = signature(cg, 'CGImageGetWidth', c.c_size_t, [c.c_void_p])
    height = signature(cg, 'CGImageGetHeight', c.c_size_t, [c.c_void_p])
    provider = signature(cg, 'CGImageGetDataProvider', c.c_void_p, [c.c_void_p])
    pixels_copy = signature(cg, 'CGDataProviderCopyData', c.c_void_p, [c.c_void_p])
    length = signature(cf, 'CFDataGetLength', c.c_long, [c.c_void_p])
    encoded = str(path).encode('utf-8')
    owned = []
    try:
        url = url_create(None, encoded, len(encoded), False)
        if not url: raise ValueError('Image path could not be decoded')
        owned.append(url)
        source = source_create(url, None)
        if not source: raise ValueError('PNG image source is invalid')
        owned.append(source)
        image = decode(source, 0, None)
        if not image: raise ValueError('PNG pixels could not be decoded')
        owned.append(image)
        data = pixels_copy(provider(image))
        if not data: raise ValueError('PNG has no decoded pixels')
        owned.append(data)
        result = {'width': int(width(image)), 'height': int(height(image)), 'decoded_bytes': int(length(data))}
        if result['width'] <= 0 or result['height'] <= 0 or result['decoded_bytes'] <= 0:
            raise ValueError('Decoded image is empty')
        return result
    finally:
        for value in reversed(owned): release(value)
