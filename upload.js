document.addEventListener("DOMContentLoaded", () => {
    const API_URL = "http://127.0.0.1:5000/api/detect";
    const MIN_ANALYSIS_DURATION_MS = 30000;
    const currentUser = JSON.parse(localStorage.getItem("truthshieldCurrentUser") || "null");

    const fileInput = document.getElementById("fileInput");
    const browseBtn = document.getElementById("browseBtn");
    const dropZone = document.getElementById("dropZone");
    const analyzeBtn = document.getElementById("analyzeBtn");

    const fileName = document.getElementById("fileName");
    const fileMeta = document.getElementById("fileMeta");
    const fileTypeBadge = document.getElementById("fileTypeBadge");
    const statusMessage = document.getElementById("statusMessage");

    const previewPanel = document.getElementById("previewPanel");
    const previewArea = document.getElementById("previewArea");

    const resultState = document.getElementById("resultState");
    const resultTag = document.getElementById("resultTag");
    const resultTitle = document.getElementById("resultTitle");
    const resultSummary = document.getElementById("resultSummary");
    const confidenceValue = document.getElementById("confidenceValue");
    const mediaTypeValue = document.getElementById("mediaTypeValue");
    const fileSizeValue = document.getElementById("fileSizeValue");
    const notesValue = document.getElementById("notesValue");

    const signalChart = document.getElementById("signalChart");
    const signalList = document.getElementById("signalList");
    const chartCaption = document.getElementById("chartCaption");

    let selectedFile = null;
    let previewUrl = null;
    let analysisStageTimer = null;

    function formatBytes(bytes) {
        if (bytes < 1024) return `${bytes} B`;
        if (bytes < 1024 * 1024) return `${(bytes / 1024).toFixed(1)} KB`;
        if (bytes < 1024 * 1024 * 1024) return `${(bytes / (1024 * 1024)).toFixed(1)} MB`;
        return `${(bytes / (1024 * 1024 * 1024)).toFixed(1)} GB`;
    }

    function getMediaType(file) {
        if (!file || !file.type) return "Unknown";
        const family = file.type.split("/")[0];

        if (family === "image") return "Image";
        if (family === "video") return "Video";
        if (family === "audio") return "Audio";
        return "Unsupported";
    }

    function setStatus(message, type = "") {
        statusMessage.textContent = message;
        statusMessage.className = `status-message ${type}`.trim();
    }

    function clearAnalysisStageTimer() {
        if (analysisStageTimer) {
            window.clearTimeout(analysisStageTimer);
            analysisStageTimer = null;
        }
    }

    function startAnalysisStatusFlow() {
        const stages = [
            { delay: 0, message: "Preparing secure analysis session..." },
            { delay: 5000, message: "Reading uploaded media and extracting verification signals..." },
            { delay: 12000, message: "Comparing facial, scene, and motion patterns..." },
            { delay: 20000, message: "Building confidence summary and final screening result..." },
            { delay: 27000, message: "Finalizing analysis report..." }
        ];

        const runStage = index => {
            if (index >= stages.length) {
                analysisStageTimer = null;
                return;
            }

            setStatus(stages[index].message);
            const nextStage = stages[index + 1];

            if (!nextStage) {
                analysisStageTimer = null;
                return;
            }

            analysisStageTimer = window.setTimeout(() => {
                runStage(index + 1);
            }, nextStage.delay - stages[index].delay);
        };

        clearAnalysisStageTimer();
        runStage(0);
    }

    function clearChart() {
        if (!signalChart) {
            return;
        }

        const context = signalChart.getContext("2d");
        context.clearRect(0, 0, signalChart.width, signalChart.height);
        context.fillStyle = "rgba(148, 163, 184, 0.18)";
        context.beginPath();
        context.arc(signalChart.width / 2, signalChart.height / 2, 78, 0, Math.PI * 2);
        context.fill();

        context.fillStyle = "#dbeafe";
        context.font = "600 16px Poppins";
        context.textAlign = "center";
        context.fillText("No Data", signalChart.width / 2, signalChart.height / 2 + 6);
    }

    function drawPieChart(chartData) {
        if (!signalChart) {
            return;
        }

        const context = signalChart.getContext("2d");
        const width = signalChart.width;
        const height = signalChart.height;
        const centerX = width / 2;
        const centerY = height / 2;
        const radius = 84;
        const innerRadius = 46;
        const segments = chartData?.segments || [];
        const total = segments.reduce((sum, segment) => sum + segment.score, 0) || 1;
        const centerValue = chartData?.centerValue ?? 0;
        const centerLabel = chartData?.centerLabel || "Confidence";

        context.clearRect(0, 0, width, height);

        let startAngle = -Math.PI / 2;
        segments.forEach(segment => {
            const sliceAngle = (segment.score / total) * Math.PI * 2;
            context.beginPath();
            context.moveTo(centerX, centerY);
            context.arc(centerX, centerY, radius, startAngle, startAngle + sliceAngle);
            context.closePath();
            context.fillStyle = segment.color || "#38bdf8";
            context.fill();
            startAngle += sliceAngle;
        });

        context.beginPath();
        context.fillStyle = "#081121";
        context.arc(centerX, centerY, innerRadius, 0, Math.PI * 2);
        context.fill();

        context.fillStyle = "#f8fbff";
        context.font = "700 28px Poppins";
        context.textAlign = "center";
        context.fillText(`${centerValue}%`, centerX, centerY - 2);
        context.fillStyle = "#93c5fd";
        context.font = "500 11px Poppins";
        context.fillText(centerLabel, centerX, centerY + 20);
    }

    function renderSignalBreakdown(analysis) {
        const signals = analysis?.signals || [];
        const chart = analysis?.chart || null;

        if (!signals.length) {
            chartCaption.textContent = "Your result breakdown will appear here after analysis.";
            signalList.innerHTML = `<div class="signal-empty">No signal breakdown available yet.</div>`;
            clearChart();
            return;
        }

        chartCaption.textContent = analysis.scope || "Your result breakdown is shown below.";
        if (chart) {
            drawPieChart(chart);
        } else {
            clearChart();
        }

        signalList.innerHTML = signals.map(signal => `
            <article class="signal-item">
                <div class="signal-row">
                    <strong>${signal.label}</strong>
                    <span class="signal-score">${signal.score}/100</span>
                </div>
                <p>${signal.explanation}</p>
            </article>
        `).join("");
    }

    function resetResultPanel() {
        resultState.className = "result-state";
        resultTag.textContent = "Waiting";
        resultTitle.textContent = "No analysis yet";
        resultSummary.textContent = "Upload a file and run detection to generate a summary.";
        confidenceValue.textContent = "--";
        mediaTypeValue.textContent = "--";
        fileSizeValue.textContent = "--";
        notesValue.textContent = "A short explanation will appear here after the scan finishes.";
        renderSignalBreakdown(null);
    }

    function clearPreview() {
        if (previewUrl) {
            URL.revokeObjectURL(previewUrl);
            previewUrl = null;
        }

        previewArea.innerHTML = "";
        previewPanel.hidden = true;
    }

    function showPreviewFallback(title, description) {
        previewArea.innerHTML = `
            <div class="preview-fallback">
                <h4>${title}</h4>
                <p>${description}</p>
            </div>
        `;
        previewPanel.hidden = false;
    }

    function createPreviewStatus(title, description, chipLabel) {
        const statusCard = document.createElement("div");
        statusCard.className = "preview-status-card";
        statusCard.innerHTML = `
            <div>
                <strong>${title}</strong>
                <p>${description}</p>
            </div>
            <span class="preview-status-chip">${chipLabel}</span>
        `;
        return statusCard;
    }

    function renderPreview(file) {
        clearPreview();

        const mediaType = getMediaType(file);
        if (mediaType === "Unsupported") {
            return;
        }

        previewUrl = URL.createObjectURL(file);
        const previewContent = document.createElement("div");
        previewContent.className = "preview-content";

        if (mediaType === "Image") {
            previewContent.appendChild(
                createPreviewStatus(
                    "Image selected",
                    "Your image preview is shown below before analysis starts.",
                    "Image"
                )
            );

            const frame = document.createElement("div");
            frame.className = "preview-media-frame";

            const image = document.createElement("img");
            image.src = previewUrl;
            image.alt = file.name;
            image.addEventListener("error", () => {
                showPreviewFallback(
                    "Preview not available",
                    "This image could not be shown in the preview area, but you can still run analysis."
                );
            });

            const badge = document.createElement("div");
            badge.className = "preview-badge";
            badge.textContent = "Image Preview";

            frame.appendChild(image);
            frame.appendChild(badge);
            previewContent.appendChild(frame);
        } else if (mediaType === "Video") {
            previewContent.appendChild(
                createPreviewStatus(
                    "Video selected",
                    "If the first frame looks dark, use the player controls below to move through the clip.",
                    "Video"
                )
            );

            const thumbnailCard = document.createElement("div");
            thumbnailCard.className = "preview-thumbnail-card";
            thumbnailCard.innerHTML = `
                <h4>Video Snapshot</h4>
                <p>A frame preview will appear here when the browser can capture one from the uploaded clip.</p>
            `;

            const thumbnailShell = document.createElement("div");
            thumbnailShell.className = "preview-thumbnail-shell";
            thumbnailShell.innerHTML = `
                <div class="preview-thumbnail-placeholder">
                    Preparing a visible frame preview for this video.
                </div>
            `;
            thumbnailCard.appendChild(thumbnailShell);
            previewContent.appendChild(thumbnailCard);

            const frame = document.createElement("div");
            frame.className = "preview-media-frame preview-video-frame";

            const video = document.createElement("video");
            video.src = previewUrl;
            video.controls = true;
            video.preload = "metadata";
            video.playsInline = true;
            video.muted = true;

            let previewResolved = false;
            let thumbnailRendered = false;

            const badge = document.createElement("div");
            badge.className = "preview-badge";
            badge.textContent = "Video Preview";

            const overlay = document.createElement("div");
            overlay.className = "preview-overlay";
            overlay.innerHTML = `
                <strong>Preview ready</strong>
                If the first frame looks dark, press play to check the visible scene.
            `;

            function renderVideoThumbnail() {
                try {
                    const canvas = document.createElement("canvas");
                    const width = video.videoWidth || 640;
                    const height = video.videoHeight || 360;
                    canvas.width = width;
                    canvas.height = height;
                    const context = canvas.getContext("2d");
                    context.drawImage(video, 0, 0, width, height);
                    thumbnailShell.innerHTML = "";
                    thumbnailShell.appendChild(canvas);
                    thumbnailRendered = true;
                } catch (error) {
                    thumbnailShell.innerHTML = `
                        <div class="preview-thumbnail-placeholder">
                            A separate frame preview could not be created for this video, but the player below is still ready to use.
                        </div>
                    `;
                }
            }

            video.addEventListener("loadedmetadata", () => {
                previewResolved = true;
                if (video.duration && video.duration > 0.2) {
                    try {
                        video.currentTime = Math.min(0.2, video.duration / 4);
                    } catch (error) {
                        // Keep default first frame if seeking is blocked by the browser.
                    }
                }
            });

            video.addEventListener("seeked", () => {
                renderVideoThumbnail();
            });

            video.addEventListener("loadeddata", () => {
                if (!thumbnailRendered) {
                    renderVideoThumbnail();
                }
            });

            video.addEventListener("error", () => {
                previewResolved = true;
                thumbnailShell.innerHTML = `
                    <div class="preview-thumbnail-placeholder">
                        A visible frame preview is not available for this file in this browser.
                    </div>
                `;
                showPreviewFallback(
                    "Video preview not available",
                    "Your file can still be analyzed, but the browser could not render a visible preview for this video."
                );
            });

            window.setTimeout(() => {
                if (!previewResolved && previewArea.contains(frame)) {
                    overlay.innerHTML = `
                        <strong>Preview limited</strong>
                        The browser is not showing a frame yet. You can still press play or run analysis normally.
                    `;
                }

                if (!thumbnailRendered && previewArea.contains(frame)) {
                    thumbnailShell.innerHTML = `
                        <div class="preview-thumbnail-placeholder">
                            The browser has not provided a frame preview yet. You can still use the video player below and run analysis normally.
                        </div>
                    `;
                }
            }, 1800);

            frame.appendChild(video);
            frame.appendChild(badge);
            frame.appendChild(overlay);
            previewContent.appendChild(frame);
        } else if (mediaType === "Audio") {
            previewContent.appendChild(
                createPreviewStatus(
                    "Audio selected",
                    "You can listen to the uploaded audio below before analysis starts.",
                    "Audio"
                )
            );

            const card = document.createElement("div");
            card.className = "preview-audio-card";

            const title = document.createElement("h4");
            title.textContent = "Audio Preview";

            const description = document.createElement("p");
            description.textContent = "You can listen to the uploaded audio here before running analysis.";

            const audio = document.createElement("audio");
            audio.src = previewUrl;
            audio.controls = true;
            audio.addEventListener("error", () => {
                showPreviewFallback(
                    "Audio preview not available",
                    "Your file can still be analyzed, but the browser could not play this audio preview."
                );
            });

            card.appendChild(title);
            card.appendChild(description);
            card.appendChild(audio);
            previewContent.appendChild(card);
        }

        previewArea.appendChild(previewContent);
        previewPanel.hidden = false;
    }

    function updateFileUI(file) {
        const mediaType = getMediaType(file);

        fileName.textContent = file.name;
        fileMeta.textContent = `${mediaType} | ${formatBytes(file.size)}`;
        fileTypeBadge.textContent = mediaType;
        mediaTypeValue.textContent = mediaType;
        fileSizeValue.textContent = formatBytes(file.size);
        analyzeBtn.disabled = false;

        renderPreview(file);
        resetResultPanel();
        setStatus(`${mediaType} file ready for analysis.`, "success");
    }

    function selectFile(file) {
        if (!file) return;

        const mediaType = getMediaType(file);
        if (mediaType === "Unsupported") {
            setStatus("Please upload an image, video, or audio file.", "error");
            return;
        }

        selectedFile = file;
        updateFileUI(file);
    }

    function applyResultState(result, summary) {
        if (result === "Fake") {
            resultState.className = "result-state alert";
            resultTag.textContent = "Flagged";
            resultTitle.textContent = "Technical screen found strong irregularities";
            resultSummary.textContent = summary;
            return;
        }

        resultState.className = "result-state safe";
        resultTag.textContent = "Likely Authentic";
        resultTitle.textContent = "No strong irregularities detected";
        resultSummary.textContent = summary;
    }

    async function runDetection() {
        if (!currentUser || !currentUser.id) {
            setStatus(
                "Registration is required before secure media analysis can begin. Redirecting you to account setup...",
                "error"
            );
            window.setTimeout(() => {
                window.location.href = "register.html?source=detection&next=upload.html";
            }, 700);
            return;
        }

        if (!selectedFile) {
            setStatus("Choose a file before running detection.", "error");
            return;
        }

        analyzeBtn.disabled = true;
        startAnalysisStatusFlow();

        const formData = new FormData();
        formData.append("file", selectedFile);
        formData.append("user_id", currentUser.id);
        const analysisStartTime = Date.now();

        try {
            const [response] = await Promise.all([
                fetch(API_URL, {
                    method: "POST",
                    body: formData
                }),
                new Promise(resolve => window.setTimeout(resolve, MIN_ANALYSIS_DURATION_MS))
            ]);

            const data = await response.json();

            if (!response.ok) {
                throw new Error(data.message || "Detection request failed.");
            }

            const mediaType = getMediaType(selectedFile);
            const confidence = typeof data.confidence === "number"
                ? `${data.confidence}%`
                : (data.confidence || "--");

            applyResultState(data.result, data.summary || "Backend analysis completed.");

            confidenceValue.textContent = confidence;
            mediaTypeValue.textContent = mediaType;
            fileSizeValue.textContent = formatBytes(selectedFile.size);
            notesValue.textContent = data.notes || "Detection completed by the backend.";
            renderSignalBreakdown(data.analysis);

            setStatus("Detection completed successfully and saved to your history.", "success");
        } catch (error) {
            resultState.className = "result-state alert";
            resultTag.textContent = "Error";
            resultTitle.textContent = "Detection service unavailable";
            resultSummary.textContent = "The upload page could not get a usable response from the backend.";
            notesValue.textContent = error.message;
            renderSignalBreakdown(null);
            setStatus(error.message, "error");
        } finally {
            clearAnalysisStageTimer();
            analyzeBtn.disabled = false;
        }
    }

    browseBtn.addEventListener("click", () => fileInput.click());

    dropZone.addEventListener("click", event => {
        if (event.target.tagName !== "BUTTON") {
            fileInput.click();
        }
    });

    dropZone.addEventListener("keydown", event => {
        if (event.key === "Enter" || event.key === " ") {
            event.preventDefault();
            fileInput.click();
        }
    });

    fileInput.addEventListener("change", event => {
        selectFile(event.target.files[0]);
    });

    ["dragenter", "dragover"].forEach(eventName => {
        dropZone.addEventListener(eventName, event => {
            event.preventDefault();
            dropZone.classList.add("drag-over");
        });
    });

    ["dragleave", "drop"].forEach(eventName => {
        dropZone.addEventListener(eventName, event => {
            event.preventDefault();
            dropZone.classList.remove("drag-over");
        });
    });

    dropZone.addEventListener("drop", event => {
        const droppedFile = event.dataTransfer.files[0];
        selectFile(droppedFile);
    });

    analyzeBtn.addEventListener("click", runDetection);

    analyzeBtn.disabled = true;
    resetResultPanel();
    clearChart();

    if (currentUser && currentUser.fullName) {
        setStatus(`Ready for detection, ${currentUser.fullName}.`, "success");
    }

    window.addEventListener("beforeunload", clearPreview);
    window.addEventListener("beforeunload", clearAnalysisStageTimer);
});
