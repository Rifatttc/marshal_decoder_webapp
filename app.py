# (আমি আগের মেসেজে যে প all `app.py` দিয়েছিলাম, সেটার `decode_binary_file` ফাংশনটা নতুন এই ভার্সন দিয়ে রিপ্লেস করো)

def decode_binary_file(data: bytes, filename: str):
    """Improved support for .so and encrypted binary files"""
    import py7zr
    import zipfile
    import re

    results = []
    extracted_strings = []

    # Extract readable strings (very useful for .so files)
    try:
        strings = re.findall(b'[\x20-\x7E]{8,}', data)
        extracted_strings = [s.decode('utf-8', errors='ignore') for s in strings[:150]]
    except:
        pass

    # Search for embedded marshal bytecode
    for magic in [b'\xe3', b'\x63']:
        idx = 0
        while True:
            idx = data.find(magic, idx)
            if idx == -1:
                break
            chunk = data[idx:idx+400000]
            try:
                obj = marshal.loads(chunk)
                if isinstance(obj, types.CodeType):
                    info = extract_code_info(obj)
                    if info:
                        results.append(generate_decoded_output(info))
            except:
                pass
            idx += 1

    # Try direct archive extraction
    extracted_files = []
    try:
        with py7zr.SevenZipFile(io.BytesIO(data), mode='r') as z:
            for name, bio in z.readall().items():
                extracted_files.append((name, bio.read()))
    except:
        pass

    try:
        with zipfile.ZipFile(io.BytesIO(data)) as z:
            for name in z.namelist():
                extracted_files.append((name, z.read(name)))
    except:
        pass

    # Carve archives from binary data
    for magic in [b'7z\xBC\xAF\x27\x1C', b'PK\x03\x04']:
        idx = data.find(magic)
        if idx != -1:
            try:
                chunk = data[idx:idx + 10000000]
                if magic.startswith(b'7z'):
                    with py7zr.SevenZipFile(io.BytesIO(chunk), mode='r') as z:
                        for name, bio in z.readall().items():
                            extracted_files.append((name, bio.read()))
                else:
                    with zipfile.ZipFile(io.BytesIO(chunk)) as z:
                        for name in z.namelist():
                            extracted_files.append((name, z.read(name)))
            except:
                pass

    # Process extracted content
    for name, content in extracted_files:
        if name.endswith('.py'):
            try:
                text = content.decode('utf-8', errors='replace')
                res = decode_file(text, name)
                if res.get('success'):
                    results.append(res['code'])
            except:
                pass

        # Search marshal in any extracted binary
        for magic in [b'\xe3', b'\x63']:
            idx = content.find(magic) if isinstance(content, (bytes, bytearray)) else -1
            if idx != -1:
                try:
                    obj = marshal.loads(content[idx:idx+300000])
                    if isinstance(obj, types.CodeType):
                        info = extract_code_info(obj)
                        if info:
                            results.append(generate_decoded_output(info))
                except:
                    pass

    # Build final output
    output_parts = []
    if results:
        output_parts.append("\n".join(results))

    if extracted_strings:
        output_parts.append("\n=== EXTRACTED STRINGS FROM BINARY FILE ===\n")
        output_parts.append("\n".join(extracted_strings))

    if output_parts:
        return {
            "success": True,
            "code": "\n".join(output_parts),
            "original_filename": filename,
            "note": "Binary file analyzed. Strings + Marshal extracted where possible."
        }
    else:
        return {
            "success": False,
            "error": "No meaningful marshal or readable data found in this binary file."
        }
