#!/usr/bin/env python3
"""
MARSHAL DECOMPILER v2.3 - Stable Version
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


def safe_decode_file(source_code, filename):
    """Safe wrapper for .py files"""
    try:
        payloads = []
        tree = ast.parse(source_code)
        for node in ast.walk(tree):
            if isinstance(node, ast.Call):
                func = node.func
                if (isinstance(func, ast.Attribute) and func.attr == 'loads' and node.args):
                    arg = node.args[0]
                    if isinstance(arg, ast.Constant) and isinstance(arg.value, (bytes, bytearray)):
                        if len(arg.value) > 50:
                            payloads.append(bytes(arg.value))
                elif (isinstance(func, ast.Name) and func.id == 'loads' and node.args):
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

        return {"success": False, "error": "Failed to decode marshal payload."}
    except Exception as e:
        return {"success": False, "error": f"Error processing .py file: {str(e)}"}


def safe_decode_binary(data, filename):
    """Safe wrapper for .so and binary files"""
    try:
        # Extract strings
        strings = re.findall(b'[\x20-\x7E]{8,}', data)
        string_list = [s.decode('utf-8', errors='ignore') for s in strings[:100]]

        # Search for marshal
        marshal_output = ""
        for magic in [b'\xe3', b'\x63']:
            idx = data.find(magic)
            if idx != -1:
                try:
                    obj = marshal.loads(data[idx:idx+300000])
                    if isinstance(obj, types.CodeType):
                        output = io.StringIO()
                        dis.dis(obj, file=output)
                        marshal_output = output.getvalue()
                        break
                except:
                    pass

        output = ""
        if marshal_output:
            output += "=== EMBEDDED PYTHON BYTECODE ===\n" + marshal_output + "\n\n"

        if string_list:
            output += "=== EXTRACTED STRINGS ===\n" + "\n".join(string_list)

        if output.strip():
            return {
                "success": True,
                "code": output,
                "original_filename": filename
            }
        else:
            return {"success": False, "error": "No useful data found in binary file."}

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
            result = safe_decode_file(content, file.filename)
        else:
            result = safe_decode_binary(file_data, file.filename)

        result['timestamp'] = datetime.utcnow().isoformat()
        return jsonify(result)

    except Exception as e:
        return jsonify({"success": False, "error": f"Server error: {str(e)}"}), 500


if __name__ == '__main__':
    port = int(os.environ.get('PORT', 5000))
    app.run(host='0.0.0.0', port=port, debug=False)
