#!/usr/bin/env python3
"""
MARSHAL DECOMPILER v2.4
Improved support for .so and binary files
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
app.config['MAX_CONTENT_LENGTH'] = 12 * 1024 * 1024


def decode_python_file(source_code: str, filename: str):
    """Decode normal marshal obfuscated .py files"""
    try:
        payloads = []
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

        if not payloads:
            return {"success": False, "error": "No marshal payload found in this .py file."}

        for payload in payloads:
            try:
                obj = marshal.loads(payload)
                if isinstance(obj, types.CodeType):
                    output = io.StringIO()
                    dis.dis(obj, file=output)
                    return {
                        "success": True,
                        "code": output.getvalue(),
                        "original_filename": filename
                    }
            except:
                continue

        return {"success": False, "error": "Could not reconstruct code object."}
    except Exception as e:
        return {"success": False, "error": f"Error: {str(e)}"}


def decode_binary_file(data: bytes, filename: str):
    """Improved handler for .so and other binary files"""
    try:
        output_parts = []

        # === 1. Extract readable strings ===
        try:
            strings = re.findall(b'[\x20-\x7E]{8,}', data)
            string_list = [s.decode('utf-8', errors='ignore') for s in strings[:120]]
            if string_list:
                output_parts.append("=== EXTRACTED STRINGS ===\n" + "\n".join(string_list))
        except:
            pass

        # === 2. Search for embedded Python bytecode ===
        marshal_found = False
        for magic in [b'\xe3', b'\x63']:
            idx = 0
            while True:
                idx = data.find(magic, idx)
                if idx == -1:
                    break
                try:
                    obj = marshal.loads(data[idx:idx+350000])
                    if isinstance(obj, types.CodeType):
                        output = io.StringIO()
                        dis.dis(obj, file=output)
                        output_parts.append("=== EMBEDDED PYTHON BYTECODE ===\n" + output.getvalue())
                        marshal_found = True
                        break
                except:
                    pass
                idx += 1

        if output_parts:
            return {
                "success": True,
                "code": "\n\n".join(output_parts),
                "original_filename": filename,
                "note": "Binary file analyzed successfully."
            }
        else:
            return {
                "success": False,
                "error": "No meaningful strings or bytecode found in this binary file."
            }

    except Exception as e:
        return {"success": False, "error": f"Error processing binary file: {str(e)}"}


@app.route('/')
def index():
    return render_template('index.html')


@app.route('/decode', methods=['POST'])
def decode_route():
    try:
        if 'file' not in request.files:
            return jsonify({"success": False, "error": "No file uploaded"}), 400

        file = request.files['file']
        if file.filename == '':
            return jsonify({"success": False, "error": "Empty filename"}), 400

        file_data = file.read()

        if file.filename.lower().endswith('.py'):
            content = file_data.decode('utf-8', errors='replace')
            result = decode_python_file(content, file.filename)
        else:
            result = decode_binary_file(file_data, file.filename)

        result['timestamp'] = datetime.utcnow().isoformat()
        return jsonify(result)

    except Exception as e:
        return jsonify({"success": False, "error": f"Server error: {str(e)}"}), 500


if __name__ == '__main__':
    port = int(os.environ.get('PORT', 5000))
    app.run(host='0.0.0.0', port=port, debug=False)
