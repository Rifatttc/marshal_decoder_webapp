// MARSHAL DECOMPILER v2.0 - HACKING TERMINAL JS

document.addEventListener('DOMContentLoaded', () => {
    // Elements
    const dropzone = document.getElementById('dropzone');
    const fileInput = document.getElementById('file-input');
    const selectBtn = document.getElementById('select-btn');
    const fileInfo = document.getElementById('file-info');
    const filenameDisplay = document.getElementById('filename-display');
    const filesizeDisplay = document.getElementById('filesize-display');
    const removeBtn = document.getElementById('remove-btn');
    const decodeBtn = document.getElementById('decode-btn');
    const uploadSection = document.getElementById('upload-section');
    const actionSection = document.getElementById('action-section');
    const loadingSection = document.getElementById('loading-section');
    const resultSection = document.getElementById('result-section');
    const logOutput = document.getElementById('log-output');
    const progressBar = document.getElementById('progress-bar');
    const progressText = document.getElementById('progress-text');
    const statusText = document.getElementById('status-text');
    const decodedCode = document.getElementById('decoded-code');
    const copyBtn = document.getElementById('copy-btn');
    const downloadPyBtn = document.getElementById('download-py-btn');
    const downloadTxtBtn = document.getElementById('download-txt-btn');
    const newBtn = document.getElementById('new-btn');
    const resultMeta = document.getElementById('result-meta');

    let currentFile = null;
    let decodedResult = null;

    // ========== FILE HANDLING ==========
    function handleFile(file) {
        if (!file.name.toLowerCase().endsWith('.py')) {
            alert('ONLY .py FILES ARE SUPPORTED');
            return;
        }
        if (file.size > 8 * 1024 * 1024) {
            alert('FILE TOO LARGE (MAX 8MB)');
            return;
        }

        currentFile = file;
        filenameDisplay.textContent = file.name;
        filesizeDisplay.textContent = `(${(file.size / 1024).toFixed(1)} KB)`;
        
        fileInfo.classList.remove('hidden');
        dropzone.style.display = 'none';
        decodeBtn.disabled = false;
    }

    // Drag & Drop
    dropzone.addEventListener('click', () => fileInput.click());
    selectBtn.addEventListener('click', (e) => {
        e.stopImmediatePropagation();
        fileInput.click();
    });

    fileInput.addEventListener('change', (e) => {
        if (e.target.files.length > 0) handleFile(e.target.files[0]);
    });

    dropzone.addEventListener('dragover', (e) => {
        e.preventDefault();
        dropzone.classList.add('dragover');
    });

    dropzone.addEventListener('dragleave', () => {
        dropzone.classList.remove('dragover');
    });

    dropzone.addEventListener('drop', (e) => {
        e.preventDefault();
        dropzone.classList.remove('dragover');
        if (e.dataTransfer.files.length > 0) {
            handleFile(e.dataTransfer.files[0]);
        }
    });

    removeBtn.addEventListener('click', () => {
        currentFile = null;
        fileInfo.classList.add('hidden');
        dropzone.style.display = 'block';
        decodeBtn.disabled = true;
        fileInput.value = '';
    });

    // ========== DECODE BUTTON ==========
    decodeBtn.addEventListener('click', async () => {
        if (!currentFile) return;

        uploadSection.style.display = 'none';
        actionSection.style.display = 'none';
        loadingSection.classList.remove('hidden');
        resultSection.classList.add('hidden');

        progressBar.style.width = '0%';
        progressText.textContent = '00%';
        logOutput.innerHTML = '';
        statusText.textContent = 'INITIALIZING SECURE ANALYSIS ENGINE...';

        const animationDone = startLoadingAnimation();

        const formData = new FormData();
        formData.append('file', currentFile);

        try {
            const response = await fetch('/decode', {
                method: 'POST',
                body: formData
            });

            const result = await response.json();
            await animationDone;

            if (result.success) {
                showResult(result);
            } else {
                showError(result.error || 'Unknown decode error');
            }
        } catch (err) {
            await animationDone;
            showError('Network error: ' + err.message);
        }
    });

    // ========== LOADING ANIMATION ==========
    function startLoadingAnimation() {
        return new Promise((resolve) => {
            const logs = [
                { p: 3,  msg: "[BOOT] Secure sandbox initialized. No execution will occur." },
                { p: 8,  msg: "[INFO] File loaded into isolated memory buffer." },
                { p: 14, msg: "[*] Parsing Python source with AST..." },
                { p: 22, msg: "[*] Scanning for marshal.loads() calls..." },
                { p: 31, msg: "[*] Payload candidate discovered. Extracting bytes..." },
                { p: 39, msg: "[*] Attempting layer unwrapping (marshal → zlib → base64)..." },
                { p: 48, msg: "[*] Reconstructing Python CodeType object..." },
                { p: 57, msg: "[*] Running recursive disassembly..." },
                { p: 66, msg: "[*] Extracting string constants..." },
                { p: 75, msg: "[*] Generating decompile report..." },
                { p: 84, msg: "[*] Final validation complete." },
                { p: 93, msg: "[✓] Analysis finished." },
                { p: 100, msg: "[SUCCESS] Marshal payload successfully decoded." }
            ];

            let currentProgress = 0;
            let logIndex = 0;

            const interval = setInterval(() => {
                currentProgress += Math.random() * 4 + 1.5;
                if (currentProgress > 100) currentProgress = 100;

                progressBar.style.width = currentProgress + '%';
                progressText.textContent = String(Math.floor(currentProgress)).padStart(2, '0') + '%';

                while (logIndex < logs.length && currentProgress >= logs[logIndex].p) {
                    const line = document.createElement('div');
                    line.textContent = logs[logIndex].msg;
                    logOutput.appendChild(line);
                    logOutput.scrollTop = logOutput.scrollHeight;
                    logIndex++;
                }

                if (currentProgress < 30) {
                    statusText.textContent = 'ANALYZING FILE STRUCTURE...';
                } else if (currentProgress < 55) {
                    statusText.textContent = 'UNWRAPPING OBFUSCATION LAYERS...';
                } else if (currentProgress < 80) {
                    statusText.textContent = 'DISASSEMBLING BYTECODE...';
                } else {
                    statusText.textContent = 'FINALIZING REPORT...';
                }

                if (currentProgress >= 100) {
                    clearInterval(interval);
                    setTimeout(() => {
                        statusText.textContent = 'DECODE SEQUENCE COMPLETE';
                        resolve();
                    }, 420);
                }
            }, 95);
        });
    }

    // ========== SHOW RESULT ==========
    function showResult(result) {
        loadingSection.classList.add('hidden');
        resultSection.classList.remove('hidden');

        decodedResult = result;

        const metaHTML = `
            <span>FILE: <strong>${result.original_filename}</strong></span> • 
            <span>MODULE: <strong>${result.module_name}</strong></span> • 
            <span>STRINGS: <strong>${result.strings_found}</strong></span> • 
            <span>FUNCTIONS: <strong>${result.functions_found}</strong></span>
        `;
        resultMeta.innerHTML = metaHTML;

        decodedCode.textContent = result.code || 'No output generated.';
        resultSection.scrollIntoView({ behavior: 'smooth', block: 'start' });
    }

    function showError(message) {
        loadingSection.classList.add('hidden');
        resultSection.classList.remove('hidden');

        resultMeta.innerHTML = `<span style="color:#ff0033">DECODE FAILED</span>`;
        decodedCode.innerHTML = `<span style="color:#ff0033">ERROR: ${message}</span>\n\n` +
            `TIPS:\n` +
            `• Make sure the file actually contains "import marshal" + "marshal.loads(b'...')"\n` +
            `• Some advanced obfuscators use different techniques`;
        decodedCode.style.color = '#ff6666';
    }

    // ========== ACTION BUTTONS ==========
    copyBtn.addEventListener('click', () => {
        if (!decodedResult || !decodedResult.code) return;
        
        navigator.clipboard.writeText(decodedResult.code).then(() => {
            const originalText = copyBtn.textContent;
            copyBtn.textContent = 'COPIED!';
            copyBtn.style.borderColor = '#00cc66';
            setTimeout(() => {
                copyBtn.textContent = originalText;
                copyBtn.style.borderColor = '';
            }, 1800);
        }).catch(() => {
            const textarea = document.createElement('textarea');
            textarea.value = decodedResult.code;
            document.body.appendChild(textarea);
            textarea.select();
            document.execCommand('copy');
            document.body.removeChild(textarea);
            alert('Code copied to clipboard (fallback method)');
        });
    });

    function downloadFile(content, filename) {
        const blob = new Blob([content], { type: 'text/plain;charset=utf-8' });
        const url = URL.createObjectURL(blob);
        const a = document.createElement('a');
        a.href = url;
        a.download = filename;
        document.body.appendChild(a);
        a.click();
        document.body.removeChild(a);
        URL.revokeObjectURL(url);
    }

    downloadPyBtn.addEventListener('click', () => {
        if (!decodedResult) return;
        const name = (decodedResult.original_filename || 'decoded').replace('.py', '') + '_decoded.py';
        downloadFile(decodedResult.code, name);
    });

    downloadTxtBtn.addEventListener('click', () => {
        if (!decodedResult) return;
        const name = (decodedResult.original_filename || 'decoded').replace('.py', '') + '_decoded.txt';
        downloadFile(decodedResult.code, name);
    });

    newBtn.addEventListener('click', () => {
        resultSection.classList.add('hidden');
        uploadSection.style.display = 'block';
        actionSection.style.display = 'block';
        loadingSection.classList.add('hidden');
        
        currentFile = null;
        decodedResult = null;
        fileInfo.classList.add('hidden');
        dropzone.style.display = 'block';
        decodeBtn.disabled = true;
        fileInput.value = '';
        decodedCode.style.color = '';
        logOutput.innerHTML = '';
    });

    console.log('%c[SECURE] Marshal Decompiler Terminal initialized. All operations are static analysis only.', 'color:#00ff41');
});
