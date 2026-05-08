// MARSHAL DECOMPILER v2.2 - HACKING TERMINAL JS

document.addEventListener('DOMContentLoaded', () => {
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

    function handleFile(file) {
        if (file.size > 15 * 1024 * 1024) {
            alert('FILE TOO LARGE (MAX 15MB)');
            return;
        }

        currentFile = file;
        filenameDisplay.textContent = file.name;
        filesizeDisplay.textContent = `(${(file.size / 1024).toFixed(1)} KB)`;
        
        fileInfo.classList.remove('hidden');
        dropzone.style.display = 'none';
        decodeBtn.disabled = false;
    }

    // Drag & Drop + Click
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

    dropzone.addEventListener('dragleave', () => dropzone.classList.remove('dragover'));

    dropzone.addEventListener('drop', (e) => {
        e.preventDefault();
        dropzone.classList.remove('dragover');
        if (e.dataTransfer.files.length > 0) handleFile(e.dataTransfer.files[0]);
    });

    removeBtn.addEventListener('click', () => {
        currentFile = null;
        fileInfo.classList.add('hidden');
        dropzone.style.display = 'block';
        decodeBtn.disabled = true;
        fileInput.value = '';
    });

    // Decode Button
    decodeBtn.addEventListener('click', async () => {
        if (!currentFile) return;

        uploadSection.style.display = 'none';
        actionSection.style.display = 'none';
        loadingSection.classList.remove('hidden');
        resultSection.classList.add('hidden');

        progressBar.style.width = '0%';
        progressText.textContent = '00%';
        logOutput.innerHTML = '';
        statusText.textContent = 'INITIALIZING...';

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
                showError(result.error || 'Decode failed');
            }
        } catch (err) {
            await animationDone;
            showError('Network error: ' + err.message);
        }
    });

    function startLoadingAnimation() {
        return new Promise((resolve) => {
            const logs = [
                { p: 5, msg: "[BOOT] Secure analysis environment initialized" },
                { p: 15, msg: "[*] Analyzing file structure..." },
                { p: 30, msg: "[*] Searching for marshal payloads or archives..." },
                { p: 50, msg: "[*] Extracting embedded 7z/ZIP if present..." },
                { p: 70, msg: "[*] Reconstructing code objects..." },
                { p: 90, msg: "[*] Generating disassembly report..." },
                { p: 100, msg: "[SUCCESS] Analysis complete" }
            ];

            let progress = 0;
            let logIndex = 0;

            const interval = setInterval(() => {
                progress += Math.random() * 5 + 2;
                if (progress > 100) progress = 100;

                progressBar.style.width = progress + '%';
                progressText.textContent = String(Math.floor(progress)).padStart(2, '0') + '%';

                while (logIndex < logs.length && progress >= logs[logIndex].p) {
                    const line = document.createElement('div');
                    line.textContent = logs[logIndex].msg;
                    logOutput.appendChild(line);
                    logOutput.scrollTop = logOutput.scrollHeight;
                    logIndex++;
                }

                if (progress >= 100) {
                    clearInterval(interval);
                    setTimeout(() => {
                        statusText.textContent = 'DECODE SEQUENCE COMPLETE';
                        resolve();
                    }, 400);
                }
            }, 90);
        });
    }

    function showResult(result) {
        loadingSection.classList.add('hidden');
        resultSection.classList.remove('hidden');
        decodedResult = result;

        resultMeta.innerHTML = `
            <span>FILE: <strong>${result.original_filename}</strong></span> • 
            <span>STATUS: <strong>SUCCESS</strong></span>
        `;
        decodedCode.textContent = result.code || 'No output';
        resultSection.scrollIntoView({ behavior: 'smooth' });
    }

    function showError(message) {
        loadingSection.classList.add('hidden');
        resultSection.classList.remove('hidden');
        resultMeta.innerHTML = `<span style="color:#ff0033">FAILED</span>`;
        decodedCode.innerHTML = `<span style="color:#ff6666">${message}</span>`;
    }

    // Action Buttons
    copyBtn.addEventListener('click', () => {
        if (!decodedResult) return;
        navigator.clipboard.writeText(decodedResult.code).then(() => {
            const old = copyBtn.textContent;
            copyBtn.textContent = 'COPIED!';
            setTimeout(() => copyBtn.textContent = old, 1500);
        });
    });

    function downloadFile(content, filename) {
        const blob = new Blob([content], { type: 'text/plain' });
        const url = URL.createObjectURL(blob);
        const a = document.createElement('a');
        a.href = url;
        a.download = filename;
        a.click();
        URL.revokeObjectURL(url);
    }

    downloadPyBtn.addEventListener('click', () => {
        if (!decodedResult) return;
        const name = decodedResult.original_filename.replace(/\.[^/.]+$/, "") + "_decoded.py";
        downloadFile(decodedResult.code, name);
    });

    downloadTxtBtn.addEventListener('click', () => {
        if (!decodedResult) return;
        const name = decodedResult.original_filename.replace(/\.[^/.]+$/, "") + "_decoded.txt";
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
});
