#!/usr/bin/env python3
"""
MARSHAL DECOMPILER WEB APP v2.1
Hacking Terminal Style - More Powerful Marshal Detection
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
app.config['MAX_CONTENT_LENGTH'] = 8 * 1024 * 1024

# ============== IMPROVED CORE DECODER ==============

def find_marshal_payloads(source_code: str):
    """Much more powerful detection for different obfuscation styles"""
    try:
        tree = ast.parse(source_code)
    except SyntaxError:
        return []

    payloads = set()

    for node in ast.walk(tree):
        if not isinstance(node, ast.Call):
            continue

        func = node.func

        # Case 1: marshal.loads(...) or alias.loads(...)
        if isinstance(func, ast.Attribute) and func.attr == 'loads':
            if node.args:
                arg = node.args[0]
                val = None
                if isinstance(arg, ast.Bytes):
                    val = arg.value
                elif isinstance(arg, ast.Constant) and isinstance(arg.value, (bytes, bytearray)):
                    val = arg.value
                if val and len(val) > 50:
                    payloads.add(bytes(val))

            # __import__('marshal').loads(...)
            if isinstance(func.value, ast.Call):
                if (isinstance(func.value.func, ast.Name) and func.value.func.id == '__import__'):
                    if node.args:
                        arg = node.args[0]
                        if isinstance(arg, (ast.Bytes, ast.Constant)) and isinstance(getattr(arg, 'value', None), (bytes, bytearray)):
                            val = getattr(arg, 'value', b'')
                            if len(val) > 50:
                                payloads.add(bytes(val))

        # Case 2: from marshal import loads → loads(b'...')
        elif isinstance(func, ast.Name) and func.id == 'loads':
            if node.args:
                arg = node.args[0]
                if isinstance(arg, (ast.Bytes, ast.Constant)) and isinstance(getattr(arg, 'value', None), (bytes, bytearray)):
                    val = getattr(arg, 'value', b'')
                    if len(val) > 50:
                        payloads.add(bytes(val))

    # Powerful Fallback: Find all large byte literals (catches variable assignment cases)
    if not payloads:
        for node in ast.walk(tree):
            val = None
            if isinstance(node, ast.Bytes):
                val = node.value
            elif isinstance(node, ast.Constant) and isinstance(node.value, (bytes, bytearray)):
                val = node.value

            if val and len(val) > 80:
                # Looks like marshal code object
                if val[:1] in (b'\xe3', b'\x63', b'\x2e', b'\x0d'):
                    payloads.add(bytes(val))

    return list(payloads)


def try_unwrap(data, max_depth=12):
    """Recursively unwrap marshal + zlib + base64 + bz2 + lzma"""
    if not isinstance(data, (bytes, bytearray)):
        return None
    
    current = bytes(data)
    seen = set()

    for _ in range(max_depth):
        h = hash(current)
        if h in seen:
            break
        seen.add(h)

        # Try marshal
        try:
            obj = marshal.loads(current)
            if isinstance(obj, types.CodeType):
                return obj
            if isinstance(obj, (bytes, bytearray)):
                current = bytes(obj)
                continue
        except:
            pass

        # zlib
        try:
            import zlib
            decom = zlib.decompress(current)
            if isinstance(decom, (bytes, bytearray)) and decom != current:
                current = bytes(decom)
                continue
        except:
            pass

        # base64
        try:
            import base64
            dec = base64.b64decode(current, validate=False)
            if isinstance(dec, (bytes, bytearray)) and dec != current and len(dec) > 0:
                current = bytes(dec)
                continue
        except:
            pass

        # bz2
        try:
            import bz2
            decom = bz2.decompress(current)
            if isinstance(decom, (bytes, bytearray)) and decom != current:
                current = bytes(decom)
                continue
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


def extract_code_info(code_obj, depth=0, max_depth=6):
    if depth > max_depth or not isinstance(code_obj, types.CodeType):
        return None

    output = io.StringIO()
    dis.dis(code_obj, file=output)

    strings = []
    nested = []
    for const in code_obj.co_consts:
        if isinstance(const, str) and const.strip():
            display = const if len(const) < 300 else const[:300] + " ...[truncated]"
            strings.append(display)
        elif isinstance(const, types.CodeType):
            n = extract_code_info(const, depth + 1, max_depth)
            if n:
                nested.append(n)

    return {
        "name": code_obj.co_name,
        "filename": code_obj.co_filename or "<unknown>",
        "first_line": code_obj.co_firstlineno,
        "argcount": code_obj.co_argcount,
        "disassembly": output.getvalue(),
        "strings": strings,
        "nested_functions": nested
    }


def generate_decoded_output(info):
    if not info:
        return "# ERROR"

    lines = []
    lines.append("=" * 70)
    lines.append("     MARSHAL DECOMPILER v2.1 - DECODE REPORT")
    lines.append("=" * 70)
    lines.append("")
    lines.append(f"[+] Module Name      : {info['name']}")
    lines.append(f"[+] Total Strings    : {len(info['strings'])}")
    lines.append(f"[+] Nested Functions : {len(info['nested_functions'])}")
    lines.append("")
    
    if info['strings']:
        lines.append("--- EXTRACTED STRINGS ---")
        for i, s in enumerate(info['strings'][:25]):
            lines.append(f"    [{i:02d}] {s}")
        lines.append("")

    lines.append("--- DISASSEMBLY ---")
    lines.append(info['disassembly'])

    for i, func in enumerate(info['nested_functions']):
        lines.append(f"\n--- FUNCTION: {func['name']} ---")
        lines.append(func['disassembly'][:1500])

    lines.append("\n" + "=" * 70)
    lines.append("Safe bytecode analysis. Variable names may be lost.")
    lines.append("=" * 70)
    return "\n".join(lines)


def decode_file(source_code: str, filename: str = "unknown.py"):
    if not source_code or len(source_code) > 8*1024*1024:
        return {"success": False, "error": "File too large or empty"}

    payloads = find_marshal_payloads(source_code)

    if not payloads:
        return {
            "success": False, 
            "error": "No marshal payload detected.\n\n"
                     "Your file uses a different or more advanced obfuscation style.\n\n"
                     "Supported patterns:\n"
                     "• import marshal → marshal.loads(b'...')\n"
                     "• from marshal import loads → loads(b'...')\n"
                     "• import marshal as m → m.loads(b'...')\n"
                     "• Large byte literals in the file\n\n"
                     "Tip: Try a different file or share a small part of your obfuscated code."
        }

    for payload in payloads:
        code_obj = try_unwrap(payload)
        if code_obj:
            info = extract_code_info(code_obj)
            if info:
                return {
                    "success": True,
                    "code": generate_decoded_output(info),
                    "original_filename": filename,
                    "module_name": info['name'],
                    "strings_found": len(info['strings']),
                    "functions_found": len(info['nested_functions']) + 1
                }

    return {
        "success": False,
        "error": "Found potential payload but could not reconstruct CodeType. Possible Python version mismatch."
    }


# ============== FLASK ROUTES ==============

@app.route('/')
def index():
    return render_template('index.html')


@app.route('/decode', methods=['POST'])
def decode_route():
    if 'file' not in request.files:
        return jsonify({"success": False, "error": "No file uploaded"}), 400

    file = request.files['file']
    if file.filename == '' or not file.filename.lower().endswith('.py'):
        return jsonify({"success": False, "error": "Only .py files allowed"}), 400

    try:
        content = file.read().decode('utf-8', errors='replace')
        result = decode_file(content, file.filename)
        result['timestamp'] = datetime.utcnow().isoformat() + 'Z'
        return jsonify(result)
    except Exception as e:
        return jsonify({"success": False, "error": f"Server error: {str(e)}"}), 500


if __name__ == '__main__':
    port = int(os.environ.get('PORT', 5000))
    app.run(host='0.0.0.0', port=port, debug=False)
