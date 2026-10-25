"""Bounded child-process parser for synthetic PDFs; not a malware scanner or OCR."""

import io
import json
import resource
import sys

from pypdf import PdfReader
from pypdf.generic import ArrayObject, DictionaryObject, IndirectObject

MAX_UPLOAD = 2 * 1024 * 1024


def extract(content):
    if not 0 < len(content) <= MAX_UPLOAD or not content.startswith(b"%PDF-"):
        raise ValueError("Invalid PDF")
    reader = PdfReader(io.BytesIO(content), strict=True)
    if reader.is_encrypted or not 1 <= len(reader.pages) <= 20:
        raise ValueError("Unsupported PDF")
    denied = {
        "/JS",
        "/JavaScript",
        "/AA",
        "/OpenAction",
        "/Launch",
        "/EmbeddedFiles",
        "/AcroForm",
        "/XFA",
        "/RichMedia",
        "/A",
    }
    visited = set()

    def inspect(obj, depth=0):
        if depth > 60 or len(visited) > 20000:
            raise ValueError("PDF complexity limit")
        if isinstance(obj, IndirectObject):
            key = (obj.idnum, obj.generation)
            if key in visited:
                return
            visited.add(key)
            inspect(obj.get_object(), depth + 1)
        elif isinstance(obj, DictionaryObject):
            if denied.intersection(obj):
                raise ValueError("Active content is unsupported")
            for value in obj.values():
                inspect(value, depth + 1)
        elif isinstance(obj, ArrayObject):
            for value in obj:
                inspect(value, depth + 1)

    inspect(reader.trailer)
    pages = []
    for page in reader.pages:
        stream = page.get_contents()
        if stream and len(stream.get_data()) > 4 * 1024 * 1024:
            raise ValueError("PDF content limit")
        pages.append(page.extract_text() or "")
        if sum(map(len, pages)) > 100000:
            raise ValueError("PDF text limit")
    text = "\n\n".join(pages).strip()
    return {
        "state": "extracted" if text else "needs_manual_extraction",
        "text": text,
        "pages": len(pages),
    }


def main():
    memory = 256 * 1024**2
    # Linux containers enforce address-space and data limits. macOS rejects
    # these limits; direct host tests retain CPU/wall/input bounds only.
    if sys.platform == "linux":
        resource.setrlimit(resource.RLIMIT_DATA, (memory, memory))
        resource.setrlimit(resource.RLIMIT_AS, (memory, memory))
    resource.setrlimit(resource.RLIMIT_CPU, (5, 5))
    resource.setrlimit(resource.RLIMIT_FSIZE, (0, 0))
    try:
        result = extract(sys.stdin.buffer.read(MAX_UPLOAD + 1))
        print(json.dumps(result))
    except Exception:
        print('{"state":"rejected","text":"","pages":0}')


if __name__ == "__main__":
    main()
