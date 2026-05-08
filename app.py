#!/usr/bin/env python3
"""
MARSHAL DECOMPILER WEB APP
Hacking Terminal Style - Powerful Marshal Payload Decoder
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
app.config['MAX_CONTENT_LENGTH'] = 8 * 1024 * 1024  # 8MB max upload

# ============== CORE DECODER ENGINE ==============

def find_marshal_payloads(source_code: str):
    """Find bytes objects passed to marshal.loads (or alias) using AST - SAFE, NO EXEC"""
    try:
        tree = ast.parse(source_code)
    except SyntaxError as e:
        return []
    
    payloads = []
    for node in ast.walk(tree):
        if isinstance(node, ast.Call):
            func = node.func
            if (isinstance(func, ast.Attribute) and 
                func.attr == 'loads' and 
                isinstance(func.value, ast.Name)):
                
                if node.args:
                    arg = node.args[0]
                    if isinstance(arg, ast.Bytes):
                        payloads.append(arg.value)
                    elif isinstance(arg, ast.Constant) and isinstance(arg.value, (bytes, bytearray)):
                        payloads.append(bytes(arg.value))
            elif isinstance(func, ast.Attribute) and func.attr == 'loads':
                if isinstance(func.value, ast.Call):
                    if (isinstance(func.value.func, ast.Name) and func.value.func.id == '__import__' and
                        func.value.args and isinstance(func.value.args[0], ast.Constant) and 
                        func.value.args[0].value == 'marshal'):
                        if node.args:
                            arg = node.args[0]
                            if isinstance(arg, ast.Bytes):
                                payloads.append(arg.value)
                            elif isinstance(arg, ast.Constant) and isinstance(arg.value, (bytes, bytearray)):
                                payloads.append(bytes(arg.value))
    return payloads


def try_unwrap(data, max_depth=12):
    """Recursively try to unwrap base64, zlib, bz2, lzma, marshal layers"""
    if not isinstance(data, (bytes, bytearray)):
        return None
    
    current = bytes(data)
    seen_hashes = set()
    
    for _ in range(max_depth):
        h = hash(current)
        if h in seen_hashes:
            break
        seen_hashes.add(h)
        
        try:
            obj = marshal.loads(current)
            if isinstance(obj, types.CodeType):
                return obj
            if isinstance(obj, (bytes, bytearray)):
                current = bytes(obj)
                continue
        except Exception:
            pass
        
        try:
            import zlib
            decom = zlib.decompress(current)
            if isinstance(decom, (bytes, bytearray)) and decom != current:
                current = bytes(decom)
                continue
        except Exception:
            pass
        
        try:
            import bz2
            decom = bz2.decompress(current)
            if isinstance(decom, (bytes, bytearray)) and decom != current:
                current = bytes(decom)
                continue
        except Exception:
            pass
        
        try:
            import lzma
            decom = lzma.decompress(current)
            if isinstance(decom, (bytes, bytearray)) and decom != current:
                current = bytes(decom)
                continue
        except Exception:
            pass
        
        try:
            import base64
            for decoder in (base64.b64decode, base64.b64decode):
                try:
                    dec = decoder(current, validate=True)
                    if isinstance(dec, (bytes, bytearray)) and dec != current and len(dec) > 0:
                        current = bytes(dec)
                        break
                except Exception:
                    continue
        except Exception:
            pass
        
        break
    
    try:
        obj = marshal.loads(current)
        if isinstance(obj, types.CodeType):
            return obj
    except Exception:
        pass
    
    return None


def extract_code_info(code_obj, depth=0, max_depth=6):
    if depth > max_depth or not isinstance(code_obj, types.CodeType):
        return None
    
    output = io.StringIO()
    dis.dis(code_obj, file=output)
    disassembly = output.getvalue()
    
    strings = []
    nested_functions = []
    
    for const in code_obj.co_consts:
        if isinstance(const, str) and const.strip():
            display = const if len(const) < 300 else const[:300] + " ... [TRUNCATED]"
            strings.append(display)
        elif isinstance(const, types.CodeType):
            nested = extract_code_info(const, depth + 1, max_depth)
            if nested:
                nested_functions.append(nested)
    
    return {
        "name": code_obj.co_name,
        "filename": code_obj.co_filename or "<unknown>",
        "first_line": code_obj.co_firstlineno,
        "argcount": code_obj.co_argcount,
        "disassembly": disassembly,
        "strings": strings,
        "varnames": list(code_obj.co_varnames),
        "names": list(code_obj.co_names),
        "nested_functions": nested_functions
    }


def generate_decoded_output(info):
    if not info:
        return "# ERROR: Could not extract code object info"
    
    lines = []
    lines.append("=" * 70)
    lines.append("     MARSHAL DECOMPILER v2.0 - DECODE REPORT")
    lines.append("=" * 70)
    lines.append("")
    lines.append(f"[+] Module Name      : {info['name']}")
    lines.append(f"[+] Filename         : {info['filename']}")
    lines.append(f"[+] First Line No    : {info['first_line']}")
    lines.append(f"[+] Arg Count        : {info['argcount']}")
    lines.append(f"[+] Total Strings    : {len(info['strings'])}")
    lines.append(f"[+] Nested Functions : {len(info['nested_functions'])}")
    lines.append("")
    
    if info['strings']:
        lines.append("--- EXTRACTED STRINGS / CONSTANTS ---")
        for i, s in enumerate(info['strings'][:30]):
            lines.append(f"    [{i:02d}] {s}")
        if len(info['strings']) > 30:
            lines.append(f"    ... and {len(info['strings']) - 30} more strings")
        lines.append("")
    
    lines.append("--- MAIN DISASSEMBLY ---")
    lines.append(info['disassembly'])
    
    for i, func in enumerate(info['nested_functions']):
        lines.append("")
        lines.append(f"--- NESTED FUNCTION #{i+1}: {func['name']} ---")
        lines.append(func['disassembly'][:2000])
    
    lines.append("")
    lines.append("=" * 70)
    lines.append("NOTE: Safe bytecode analysis. Original variable names may be lost.")
    lines.append("=" * 70)
    
    return "\n".join(lines)


def decode_file(source_code: str, filename: str = "unknown.py"):
    if not source_code or len(source_code) > 8*1024*1024:
        return {"success": False, "error": "File too large or empty"}
    
    payloads = find_marshal_payloads(source_code)
    
    if not payloads:
        return {
            "success": False, 
            "error": "No marshal.loads(b'...') pattern detected. File may use advanced obfuscation."
        }
    
    for i, payload in enumerate(payloads):
        code_obj = try_unwrap(payload)
        if code_obj:
            info = extract_code_info(code_obj)
            if info:
                decoded_text = generate_decoded_output(info)
                return {
                    "success": True,
                    "code": decoded_text,
                    "original_filename": filename,
                    "module_name": info['name'],
                    "strings_found": len(info['strings']),
                    "functions_found": len(info['nested_functions']) + 1
                }
    
    return {
        "success": False,
        "error": "Found marshal reference but failed to load valid CodeType."
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
    
    if file.filename == '':
        return jsonify({"success": False, "error": "Empty filename"}), 400
    
    if not file.filename.lower().endswith('.py'):
        return jsonify({"success": False, "error": "Only .py files are supported"}), 400
    
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
