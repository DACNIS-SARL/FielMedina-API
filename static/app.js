
(function () {
    'use strict';

    document.addEventListener('submit', function (e) {
        var form = e.target;
        if (!(form instanceof HTMLFormElement)) return;

        if (form.dataset.noGuard) return;

        if (form.dataset.submitting === 'true') {
            e.preventDefault();
            return;
        }

        form.dataset.submitting = 'true';

        var buttons = form.querySelectorAll('button[type="submit"], input[type="submit"]');
        buttons.forEach(function (btn) {
            btn.disabled = true;
            btn.style.opacity = '0.7';
            btn.style.cursor = 'not-allowed';

            if (btn.tagName === 'BUTTON') {
                var originalColor = window.getComputedStyle(btn).color;
                btn.dataset.originalColor = btn.style.color || '';
                btn.dataset.originalPosition = btn.style.position || '';
                btn.style.color = 'transparent';
                btn.style.position = 'relative';

                var spinner = document.createElement('span');
                spinner.className = 'submit-spinner-overlay';
                spinner.style.position = 'absolute';
                spinner.style.left = '50%';
                spinner.style.top = '50%';
                spinner.style.transform = 'translate(-50%, -50%)';
                spinner.style.display = 'inline-flex';
                spinner.style.alignItems = 'center';
                spinner.style.color = originalColor;

                var svg = document.createElementNS('http://www.w3.org/2000/svg', 'svg');
                svg.setAttribute('class', 'animate-spin w-5 h-5');
                svg.setAttribute('fill', 'none');
                svg.setAttribute('viewBox', '0 0 24 24');

                var circle = document.createElementNS('http://www.w3.org/2000/svg', 'circle');
                circle.setAttribute('class', 'opacity-25');
                circle.setAttribute('cx', '12');
                circle.setAttribute('cy', '12');
                circle.setAttribute('r', '10');
                circle.setAttribute('stroke', 'currentColor');
                circle.setAttribute('stroke-width', '4');

                var path = document.createElementNS('http://www.w3.org/2000/svg', 'path');
                path.setAttribute('class', 'opacity-75');
                path.setAttribute('fill', 'currentColor');
                path.setAttribute('d', 'M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4zm2 5.291A7.962 7.962 0 014 12H0c0 3.042 1.135 5.824 3 7.938l3-2.647z');

                svg.appendChild(circle);
                svg.appendChild(path);
                spinner.appendChild(svg);
                btn.appendChild(spinner);
            }
        });
    }, /* useCapture */ true);

    window.addEventListener('pageshow', function (e) {
        if (e.persisted) {
            document.querySelectorAll('form[data-submitting="true"]').forEach(function (form) {
                delete form.dataset.submitting;
                form.querySelectorAll('button[type="submit"], input[type="submit"]').forEach(function (btn) {
                    btn.disabled = false;
                    btn.style.opacity = '';
                    btn.style.cursor = '';
                    if (btn.tagName === 'BUTTON') {
                        var spinner = btn.querySelector('.submit-spinner-overlay');
                        if (spinner) {
                            spinner.parentNode.removeChild(spinner);
                        }
                        if (btn.dataset.originalColor !== undefined) {
                            btn.style.color = btn.dataset.originalColor;
                            delete btn.dataset.originalColor;
                        }
                        if (btn.dataset.originalPosition !== undefined) {
                            btn.style.position = btn.dataset.originalPosition;
                            delete btn.dataset.originalPosition;
                        }
                    }
                });
            });
        }
    });

    function findTokenInput(fileInput) {
        if (!fileInput.form) return null;
        const name = fileInput.name;
        if (!name) return null;
        
        // If it's a formset field (e.g. images-0-image)
        if (name.includes('-')) {
            const parts = name.split('-');
            parts.pop(); // remove last part (e.g. "image")
            const basePrefix = parts.join('-');
            
            // Try <prefix>-temp_token
            let tokenInput = fileInput.form.querySelector(`input[name="${basePrefix}-temp_token"]`);
            if (tokenInput) return tokenInput;
            
            // Try <prefix>-image_temp_token
            tokenInput = fileInput.form.querySelector(`input[name="${basePrefix}-image_temp_token"]`);
            if (tokenInput) return tokenInput;
        } else {
            // Try name_temp_token or temp_token
            let tokenInput = fileInput.form.querySelector(`input[name="${name}_temp_token"]`);
            if (tokenInput) return tokenInput;
            
            // Try cover_temp_token etc explicitly if name matches patterns
            if (name === 'cover') {
                tokenInput = fileInput.form.querySelector('input[name="cover_temp_token"]');
                if (tokenInput) return tokenInput;
            }
            if (name === 'image') {
                tokenInput = fileInput.form.querySelector('input[name="image_temp_token"]');
                if (tokenInput) return tokenInput;
            }
        }
        return null;
    }

    function getStatusIndicator(fileInput) {
        let statusIndicator = fileInput.parentNode.querySelector(".upload-status");
        if (!statusIndicator) {
            statusIndicator = document.createElement("span");
            statusIndicator.className = "upload-status text-xs font-semibold ml-2 inline-flex items-center";
            fileInput.parentNode.appendChild(statusIndicator);
        }
        return statusIndicator;
    }

    document.addEventListener("change", async function (e) {
        if (e.target && e.target.type === "file" && e.target.files && e.target.files.length > 0) {
            const fileInput = e.target;
            const files = Array.from(fileInput.files);
            const needsCompression = files.some(file => file.type.startsWith("image/") && file.size > 200 * 1024);
            
            const tokenInput = findTokenInput(fileInput);
            if (tokenInput) {
                const statusIndicator = getStatusIndicator(fileInput);
                statusIndicator.innerText = " ⏳ Uploading...";
                statusIndicator.style.color = "#e67e22";
                
                let uploadFile = files[0];
                if (uploadFile.type.startsWith("image/") && uploadFile.size > 200 * 1024) {
                    statusIndicator.innerText = " ⏳ Optimizing...";
                    try {
                        const fieldName = fileInput.name || "";
                        const isMobileField = fieldName.toLowerCase().includes("mobile");
                        const targetWidth = isMobileField ? 500 : 1920;
                        const compressedBlob = await compressImage(uploadFile, targetWidth, 80);
                        const originalNameWithoutExt = uploadFile.name.replace(/\.[^/.]+$/, "");
                        const newFileName = `${originalNameWithoutExt}.jpg`;
                        
                        uploadFile = new File([compressedBlob], newFileName, {
                            type: "image/jpeg",
                            lastModified: Date.now()
                        });
                        
                        // Update input files
                        const dataTransfer = new DataTransfer();
                        dataTransfer.items.add(uploadFile);
                        fileInput.files = dataTransfer.files;
                    } catch (compressErr) {
                        console.error("[ImageCompressor] Compression failed:", compressErr);
                    }
                }
                
                statusIndicator.innerText = " ⏳ Uploading...";
                const formData = new FormData();
                formData.append("file", uploadFile);
                
                try {
                    const response = await fetch("/api/upload-temp/", {
                        method: "POST",
                        body: formData
                    });
                    if (!response.ok) {
                        throw new Error(`HTTP error ${response.status}`);
                    }
                    const data = await response.json();
                    if (data.success && data.token) {
                        tokenInput.value = data.token;
                        statusIndicator.innerText = ` ✅ Uploaded`;
                        statusIndicator.style.color = "#27ae60";
                    } else {
                        throw new Error(data.error || "Upload response success false");
                    }
                } catch (uploadErr) {
                    console.error("[TempUpload] Upload failed:", uploadErr);
                    statusIndicator.innerText = " ❌ Upload failed";
                    statusIndicator.style.color = "#c0392b";
                }
            } else {
                // Original optimization logic fallback
                if (needsCompression) {
                    console.log(`[ImageCompressor] Processing ${files.length} file(s)`);
                    let statusIndicator = fileInput.parentNode.querySelector(".compress-status");
                    if (!statusIndicator) {
                        statusIndicator = document.createElement("span");
                        statusIndicator.className = "compress-status text-xs font-semibold ml-2 inline-flex items-center";
                        fileInput.parentNode.appendChild(statusIndicator);
                    }
                    statusIndicator.innerText = " ⏳ Optimizing...";
                    statusIndicator.style.color = "#e67e22";
                    
                    try {
                        const fieldName = fileInput.name || "";
                        const isMobileField = fieldName.toLowerCase().includes("mobile");
                        const targetWidth = isMobileField ? 500 : 1920;
                        
                        const compressedFilesPromises = files.map(async (file) => {
                            if (file.type.startsWith("image/") && file.size > 200 * 1024) {
                                const compressedBlob = await compressImage(file, targetWidth, 80);
                                const originalNameWithoutExt = file.name.replace(/\.[^/.]+$/, "");
                                const newFileName = `${originalNameWithoutExt}.jpg`;
                                return new File([compressedBlob], newFileName, {
                                    type: "image/jpeg",
                                    lastModified: Date.now()
                                });
                            }
                            return file;
                        });
                        
                        const optimizedFiles = await Promise.all(compressedFilesPromises);
                        const dataTransfer = new DataTransfer();
                        optimizedFiles.forEach(file => {
                            dataTransfer.items.add(file);
                        });
                        fileInput.files = dataTransfer.files;
                        statusIndicator.innerText = ` ✅ Optimized (${optimizedFiles.length} file(s))`;
                        statusIndicator.style.color = "#27ae60";
                    } catch (err) {
                        console.error("[ImageCompressor] Compression failed:", err);
                        statusIndicator.innerText = " ⚠️ Skipped";
                        statusIndicator.style.color = "#c0392b";
                    }
                }
            }
        }
    });

    function compressImage(file, maxWidth, quality) {
        return new Promise((resolve, reject) => {
            const reader = new FileReader();
            reader.readAsDataURL(file);
            reader.onload = function (event) {
                const img = new Image();
                img.src = event.target.result;
                img.onload = function () {
                    const canvas = document.createElement("canvas");
                    let width = img.width;
                    let height = img.height;

                    if (width > maxWidth) {
                        height = Math.round((height * maxWidth) / width);
                        width = maxWidth;
                    }

                    canvas.width = width;
                    canvas.height = height;

                    const ctx = canvas.getContext("2d");
                    ctx.fillStyle = "#FFFFFF";
                    ctx.fillRect(0, 0, width, height);
                    ctx.drawImage(img, 0, 0, width, height);

                    canvas.toBlob(function (blob) {
                        if (blob) {
                            resolve(blob);
                        } else {
                            reject(new Error("Canvas toBlob null"));
                        }
                    }, "image/jpeg", quality / 100);
                };
                img.onerror = reject;
            };
            reader.onerror = reject;
        });
    }

    function initPreloadedTokens() {
        document.querySelectorAll('input[type="file"]').forEach(fileInput => {
            const tokenInput = findTokenInput(fileInput);
            if (tokenInput && tokenInput.value) {
                const statusIndicator = getStatusIndicator(fileInput);
                statusIndicator.innerText = " ✅ Uploaded";
                statusIndicator.style.color = "#27ae60";
            }
        });
    }

    // Watch for dynamically added formset rows to clear cloned temp tokens and status elements
    const formObserver = new MutationObserver(function (mutationsList) {
        for (const mutation of mutationsList) {
            if (mutation.type === 'childList') {
                mutation.addedNodes.forEach(node => {
                    if (node.nodeType === Node.ELEMENT_NODE) {
                        const inputs = Array.from(node.querySelectorAll('input[type="hidden"]'));
                        if (node.tagName === 'INPUT' && node.type === 'hidden') {
                            inputs.push(node);
                        }
                        inputs.forEach(input => {
                            if (input.name && input.name.endsWith('temp_token')) {
                                input.value = '';
                            }
                        });
                        node.querySelectorAll('.upload-status, .compress-status').forEach(status => {
                            status.remove();
                        });
                    }
                });
            }
        }
    });

    document.addEventListener("DOMContentLoaded", function () {
        initPreloadedTokens();
        formObserver.observe(document.body, { childList: true, subtree: true });
    });
})();

var themeToggleDarkIcon = document.getElementById('theme-toggle-dark-icon');
var themeToggleLightIcon = document.getElementById('theme-toggle-light-icon');

if (localStorage.getItem('color-theme') === 'dark' || (!('color-theme' in localStorage) && window.matchMedia('(prefers-color-scheme: dark)').matches)) {
    themeToggleLightIcon.classList.remove('hidden');
} else {
    themeToggleDarkIcon.classList.remove('hidden');
}

var themeToggleBtn = document.getElementById('theme-toggle');

themeToggleBtn.addEventListener('click', function () {

    themeToggleDarkIcon.classList.toggle('hidden');
    themeToggleLightIcon.classList.toggle('hidden');

    if (localStorage.getItem('color-theme')) {
        if (localStorage.getItem('color-theme') === 'light') {
            document.documentElement.classList.add('dark');
            localStorage.setItem('color-theme', 'dark');
        } else {
            document.documentElement.classList.remove('dark');
            localStorage.setItem('color-theme', 'light');
        }

    } else {
        if (document.documentElement.classList.contains('dark')) {
            document.documentElement.classList.remove('dark');
            localStorage.setItem('color-theme', 'light');
        } else {
            document.documentElement.classList.add('dark');
            localStorage.setItem('color-theme', 'dark');
        }
    }

});
