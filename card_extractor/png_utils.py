import struct
import zlib
import base64
import json
from io import BytesIO
from PIL import Image


PNG_SIGNATURE = b'\x89PNG\r\n\x1a\n'


def _read_chunks(data: bytes) -> list[tuple[int, bytes, bytes, int]]:
    """
    Parse PNG binary data into a list of chunks.
    Returns list of (offset, type, data, crc).
    """
    chunks = []
    pos = len(PNG_SIGNATURE)
    while pos < len(data):
        length = struct.unpack('>I', data[pos:pos + 4])[0]
        pos += 4
        chunk_type = data[pos:pos + 4]
        pos += 4
        chunk_data = data[pos:pos + length]
        pos += length
        crc = struct.unpack('>I', data[pos:pos + 4])[0]
        pos += 4
        chunks.append((pos - length - 12, chunk_type, chunk_data, crc))
    return chunks


def _encode_tEXt(keyword: str, text: str) -> bytes:
    raw = keyword.encode('latin-1') + b'\x00' + text.encode('latin-1')
    length = struct.pack('>I', len(raw))
    chunk = b'tEXt' + raw
    crc = struct.pack('>I', zlib.crc32(chunk) & 0xFFFFFFFF)
    return length + chunk + crc


def _decode_tEXt(data: bytes) -> tuple[str, str]:
    null_pos = data.find(b'\x00')
    if null_pos == -1:
        raise ValueError('Invalid tEXt chunk: no null separator')
    keyword = data[:null_pos].decode('latin-1')
    text = data[null_pos + 1:].decode('latin-1')
    return keyword, text


def write_character_card(image_path: str, character_json: str, output_path: str) -> None:
    """
    Embed character JSON metadata into a PNG image using tEXt chunks,
    compatible with SillyTavern's Chara Card V2/V3 format.

    Writes two tEXt chunks:
      - keyword 'chara'  : base64(V2 JSON)  [Spec V2]
      - keyword 'ccv3'   : base64(V3 JSON)  [Spec V3]
    """
    with open(image_path, 'rb') as f:
        png_data = f.read()

    if png_data[:8] != PNG_SIGNATURE:
        raise ValueError('Not a valid PNG file')

    chunks = _read_chunks(png_data)

    new_chunks = [PNG_SIGNATURE]
    for _, chunk_type, chunk_data, _ in chunks:
        if chunk_type == b'tEXt':
            try:
                keyword, _ = _decode_tEXt(chunk_data)
                if keyword.lower() in ('chara', 'ccv3'):
                    continue
            except (ValueError, UnicodeDecodeError):
                pass
        length = struct.pack('>I', len(chunk_data))
        raw = chunk_type + chunk_data
        crc = struct.pack('>I', zlib.crc32(raw) & 0xFFFFFFFF)
        new_chunks.append(length + chunk_type + chunk_data + crc)

    base64_data = base64.b64encode(character_json.encode('utf-8')).decode('ascii')
    v2_chunk = _encode_tEXt('chara', base64_data)

    try:
        card = json.loads(character_json)
        v3_card = {**card, 'spec': 'chara_card_v3', 'spec_version': '3.0'}
        v3_json = json.dumps(v3_card, ensure_ascii=False)
        v3_base64 = base64.b64encode(v3_json.encode('utf-8')).decode('ascii')
        v3_chunk = _encode_tEXt('ccv3', v3_base64)
    except (json.JSONDecodeError, Exception):
        v3_chunk = b''

    iend_index = None
    for i, chunk in enumerate(new_chunks):
        if len(chunk) > 8 and chunk[4:8] == b'IEND':
            iend_index = i
            break

    if iend_index is None:
        raise ValueError('PNG missing IEND chunk')

    new_chunks.insert(iend_index, v2_chunk)
    if v3_chunk:
        new_chunks.insert(iend_index + 1, v3_chunk)

    with open(output_path, 'wb') as f:
        f.write(b''.join(new_chunks))


def read_character_card(image_path: str) -> str | None:
    """
    Read SillyTavern character metadata from a PNG image.
    Returns the JSON string, preferring ccv3 over chara.
    Returns None if no character data found.
    """
    with open(image_path, 'rb') as f:
        png_data = f.read()

    if png_data[:8] != PNG_SIGNATURE:
        raise ValueError('Not a valid PNG file')

    chunks = _read_chunks(png_data)
    ccv3_data = None
    chara_data = None

    for _, chunk_type, chunk_data, _ in chunks:
        if chunk_type != b'tEXt':
            continue
        try:
            keyword, text = _decode_tEXt(chunk_data)
        except (ValueError, UnicodeDecodeError):
            continue
        if keyword.lower() == 'ccv3':
            ccv3_data = text
        elif keyword.lower() == 'chara':
            chara_data = text

    target = ccv3_data or chara_data
    if target is None:
        return None
    return base64.b64decode(target).decode('utf-8')


def generate_default_avatar(size: tuple[int, int] = (400, 600)) -> bytes:
    """
    Generate a simple default avatar image as PNG bytes.
    """
    img = Image.new('RGBA', size, (45, 45, 60, 255))
    buf = BytesIO()
    img.save(buf, format='PNG')
    return buf.getvalue()
