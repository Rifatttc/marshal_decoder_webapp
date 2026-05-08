#!/usr/bin/env python3
"""
MARSHAL DECOMPILER v2.3
Supports: .py + .so + Binary files (with strings + symbols + marshal)
"""

from flask import Flask, request, jsonify, render_template
import ast
import marshal
import dis
import io
import types
import re
import os
from datetime import datetime

app = Flask(__name__)
app.config['MAX_CONTENT_LENGTH'] = 15 * 1024 * 1024


# ============== MARSHAL DECODER ==============

def find_marshal_payloads(source_code: str):
    payloads = []
    try:
        tree = ast.parse(source_code)
        for node in ast.walk(tree):
            if isinstance(node, ast.Call):
                func = node.func
                if isinstance(func, ast.Attribute) and func.attr == 'loads' and node.args:
                    arg = node.args[0]
                    if isinstance(arg, ast.Constant) and isinstance(arg.value, (bytes, bytearray)) and len(arg.value) > 50:
                        payloads.append(bytes(arg.value))
                elif isinstance(func, ast.Name) and func.id == 'loads' and node.args:
                    arg = node.args[0]
                    if isinstance(arg, ast.Constant) and isinstance(arg.value, (bytes, bytearray)) and len(arg.value) > 50:
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
                    d = mod.decompress(current)
                    if isinstance(d, (bytes, bytearray)) and d != current:
                        current = bytes(d)
                        break
                except:
                    continue
            d = base64.b64decode(current, validate=False)
            if isinstance(d, (bytes, bytearray)) and len(d) > 0:
                current = bytes(d)
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
    strings, nested = [], []
    for const in code_obj.co_consts:
        if isinstance(const, str) and const.strip():
            strings.append(const[:300] if len(const) > 300 else const)
        elif isinstance(const, types.CodeType):
            n = extract_code_info(const, depth + 1, max_depth)
            if n: nested.append(n)
    return {
        "name": code_obj.co_name,
        "disassembly": output.getvalue(),
        "strings": strings,
        "nested_functions": nested
    }


def generate_decoded_output(info):
    if not info:
        return "# ERROR"
    lines = ["=" * 65, "MARSHAL DECOMPILER v2.3", "=" * 65]
    lines.append(f"[+] Module: {info['name']}")
    if info.get('strings'):
        lines.append("\n--- STRINGS ---")
        for i, s in enumerate(info['strings'][:15]):
            lines.append(f"[{i}] {s}")
    lines.append("\n--- DISASSEMBLY ---")
    lines.append(info['disassembly'])
    return "\n".join(lines)


def decode_file(source_code: str, filename: str = "unknown.py"):
    payloads = find_marshal_payloads(source_code)
    if not payloads:
        return {"success": False, "error": "No marshal payload found."}
    for p in payloads:
        obj = try_unwrap(p)
        if obj:
            info = extract_code_info(obj)
            if info:
                return {"success": True, "code": generate_decoded_output(info), "original_filename": filename}
    return {"success": False, "error": "Failed to decode marshal payload."}


# ============== BINARY FILE HANDLER (.so / .7z etc) ==============

def decode_binary_file(data: bytes, filename: str):
    results = []
    strings_list = []

    # Extract readable strings
    try:
        found = re.findall(b'[\x20-\x7E]{8,}', data)
        strings_list = [s.decode('utf-8', errors='ignore') for s in found[:150]]
    except:
        pass

    # Search for embedded marshal
    for magic in [b'\xe3', b'\x63']:
        idx = 0
        while True:
            idx = data.find(magic, idx)
            if idx == -1:
                break
            try:
                obj = marshal.loads(data[idx:idx+400000])
                if isinstance(obj, types.CodeType):
                    info = extract_code_info(obj)
                    if info:
                        results.append(generate_decoded_output(info))
            except:
                pass
            idx += 1

    # Build output
    output = ""
    if results:
        output += "\n".join(results) + "\n\n"

    if strings_list:
        output += "=== EXTRACTED STRINGS FROM BINARY ===\n"
        output += "\n".join(strings_list)

    if output.strip():
        return {
            "success": True,
            "code": output,
            "original_filename": filename,
            "note": "Binary analysis complete (strings + marshal search)"
        }
    else:
        return {
            "success": False,
            "error": "No meaningful data found in this binary file."
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
        if file.filename.lower().endswith('.py'):
            content = file_data.decode('utf-8', errors='replace')
            result = decode_file(content, file.filename)
        else:
            result = decode_binary_file(file_data, file.filename)

        result['timestamp'] = datetime.utcnow().isoformat()
        return jsonify(result)
    except Exception as e:
        return jsonify({"success": False, "error": str(e)}), 500


if __name__ == '__main__':
    port = int(os.environ.get('PORT', 5000))
    app.run(host='0.0.0.0', port=port, debug=False)
