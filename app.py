#!/usr/bin/env python3
"""
MARSHAL DECOMPILER WEB APP v2.2
Supports: .py | .so | .7z | .zip | Binary files
"""

from flask import Flask, request, jsonify, render_template
import ast
import marshal
import dis
import io
import types
import os
from datetime import datetime

app = Flask(__name__)
app.config['MAX_CONTENT_LENGTH'] = 15 * 1024 * 1024  # 15MB


# ============== CORE DECODER ==============

def find_marshal_payloads(source_code: str):
    """Find marshal payloads from .py source"""
    payloads = []
    try:
        tree = ast.parse(source_code)
        for node in ast.walk(tree):
            if isinstance(node, ast.Call):
                func = node.func
                if isinstance(func, ast.Attribute) and func.attr == 'loads' and node.args:
                    arg = node.args[0]
                    if isinstance(arg, ast.Constant) and isinstance(arg.value, (bytes, bytearray)):
                        if len(arg.value) > 50:
                            payloads.append(bytes(arg.value))
                elif isinstance(func, ast.Name) and func.id == 'loads' and node.args:
                    arg = node.args[0]
                    if isinstance(arg, ast.Constant) and isinstance(arg.value, (bytes, bytearray)):
                        if len(arg.value) > 50:
                            payloads.append(bytes(arg.value))
    except:
        pass
    return payloads


def try_unwrap(data, max_depth=10):
    if not isinstance(data, (bytes, bytearray)):
        return None
    current = bytes(data)
    for _ in range(max_depth):
        try:
            obj = marshal.loads(current)
            if isinstance(obj, types.CodeType):
                return obj
            if isinstance(obj, (bytes, bytearray)):
                current = bytes(obj)
                continue
        except:
            pass
        try:
            import zlib, base64, bz2
            for mod in [zlib, bz2]:
                try:
                    decom = mod.decompress(current)
                    if isinstance(decom, (bytes, bytearray)) and decom != current:
                        current = bytes(decom)
                        break
                except:
                    continue
            dec = base64.b64decode(current, validate=False)
            if isinstance(dec, (bytes, bytearray)) and len(dec) > 0:
                current = bytes(dec)
        except:
            pass
        break
    try:
        obj = marshal.loads(current)
        if isinstance(obj, types.CodeType):
            return obj
    except:
        pass
    return None


def extract_code_info(code_obj, depth=0, max_depth=5):
    if depth > max_depth or not isinstance(code_obj, types.CodeType):
        return None
    output = io.StringIO()
    dis.dis(code_obj, file=output)
    strings = []
    nested = []
    for const in code_obj.co_consts:
        if isinstance(const, str) and const.strip():
            display = const if len(const) < 300 else const[:300] + "..."
            strings.append(display)
        elif isinstance(const, types.CodeType):
            n = extract_code_info(const, depth + 1, max_depth)
            if n:
                nested.append(n)
    return {
        "name": code_obj.co_name,
        "disassembly": output.getvalue(),
        "strings": strings,
        "nested_functions": nested
    }


def generate_decoded_output(info):
    if not info:
        return "# ERROR"
    lines = []
    lines.append("=" * 65)
    lines.append("MARSHAL DECOMPILER v2.2 - DECODE REPORT")
    lines.append("=" * 65)
    lines.append(f"[+] Module: {info['name']}")
    lines.append(f"[+] Strings Found: {len(info['strings'])}")
    if info['strings']:
        lines.append("\n--- EXTRACTED STRINGS ---")
        for i, s in enumerate(info['strings'][:20]):
            lines.append(f"[{i}] {s}")
    lines.append("\n--- DISASSEMBLY ---")
    lines.append(info['disassembly'])
    lines.append("=" * 65)
    return "\n".join(lines)


def decode_file(source_code: str, filename: str = "unknown.py"):
    payloads = find_marshal_payloads(source_code)
    if not payloads:
        return {"success": False, "error": "No marshal payload found in this .py file."}

    for payload in payloads:
        code_obj = try_unwrap(payload)
        if code_obj:
            info = extract_code_info(code_obj)
            if info:
                return {
                    "success": True,
                    "code": generate_decoded_output(info),
                    "original_filename": filename
                }
    return {"success": False, "error": "Failed to reconstruct code object."}


# ============== BINARY FILE SUPPORT (.so, .7z, .zip) ==============

def decode_binary_file(data: bytes, filename: str):
    import py7zr
    import zipfile

    results = []
    extracted = []

    # Try direct marshal search in binary
    try:
        for start in [b'\xe3', b'\x63']:
            idx = data.find(start)
            if idx != -1:
                chunk = data[idx:idx + 400000]
                try:
                    obj = marshal.loads(chunk)
                    if isinstance(obj, types.CodeType):
                        info = extract_code_info(obj)
                        if info:
                            results.append(generate_decoded_output(info))
                except:
                    pass
    except:
        pass

    # Try extract as 7z
    try:
        with py7zr.SevenZipFile(io.BytesIO(data), mode='r') as z:
            for name, bio in z.readall().items():
                extracted.append((name, bio.read()))
    except:
        pass

    # Try extract as ZIP
    try:
        with zipfile.ZipFile(io.BytesIO(data)) as z:
            for name in z.namelist():
                extracted.append((name, z.read(name)))
    except:
        pass

    # Carve embedded archives
    if not extracted:
        for magic, ext in [(b'7z\xBC\xAF\x27\x1C', '7z'), (b'PK\x03\x04', 'zip')]:
            idx = data.find(magic)
            if idx != -1:
                try:
                    if ext == '7z':
                        with py7zr.SevenZipFile(io.BytesIO(data[idx:]), mode='r') as z:
                            for name, bio in z.readall().items():
                                extracted.append((name, bio.read()))
                    else:
                        with zipfile.ZipFile(io.BytesIO(data[idx:])) as z:
                            for name in z.namelist():
                                extracted.append((name, z.read(name)))
                except:
                    pass

    # Process extracted files
    for name, content in extracted:
        if name.endswith('.py'):
            try:
                text = content.decode('utf-8', errors='replace')
                res = decode_file(text, name)
                if res.get('success'):
                    results.append(res['code'])
            except:
                pass
        else:
            # Search marshal inside extracted binary
            try:
                for start in [b'\xe3', b'\x63']:
                    idx = content.find(start)
                    if idx != -1:
                        chunk = content[idx:idx+300000]
                        obj = marshal.loads(chunk)
                        if isinstance(obj, types.CodeType):
                            info = extract_code_info(obj)
                            if info:
                                results.append(generate_decoded_output(info))
            except:
                pass

    if results:
        return {
            "success": True,
            "code": "\n\n".join(results),
            "original_filename": filename,
            "extracted_count": len(extracted),
            "note": "Binary file processed successfully."
        }
    else:
        return {
            "success": False,
            "error": "No marshal payload or extractable archive found in this file."
        }


# ============== ROUTES ==============

@app.route('/')
def index():
    return render_template('index.html')


@app.route('/decode', methods=['POST'])
def decode_route():
    if 'file' not in request.files:
        return jsonify({"success": False, "error": "No file uploaded"}), 400

    file = request.files['file']
    if file.filename == '':
        return jsonify({"success": False, "error": "Empty filename"}), 400

    try:
        file_data = file.read()
        filename = file.filename

        if filename.lower().endswith('.py'):
            content = file_data.decode('utf-8', errors='replace')
            result = decode_file(content, filename)
        else:
            result = decode_binary_file(file_data, filename)

        result['timestamp'] = datetime.utcnow().isoformat() + 'Z'
        return jsonify(result)

    except Exception as e:
        return jsonify({"success": False, "error": f"Server error: {str(e)}"}), 500


if __name__ == '__main__':
    port = int(os.environ.get('PORT', 5000))
    app.run(host='0.0.0.0', port=port, debug=False)
