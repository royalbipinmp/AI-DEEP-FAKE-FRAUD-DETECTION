const API_BASE_URL = "http://127.0.0.1:5000/api/attendance";

const cameraPreview = document.getElementById("cameraPreview");
const captureCanvas = document.getElementById("captureCanvas");
const startCameraBtn = document.getElementById("startCameraBtn");
const stopCameraBtn = document.getElementById("stopCameraBtn");
const cameraStateBadge = document.getElementById("cameraStateBadge");

const employeeName = document.getElementById("employeeName");
const employeeCode = document.getElementById("employeeCode");
const registerFile = document.getElementById("registerFile");
const registerFromCameraBtn = document.getElementById("registerFromCameraBtn");
const registerFromFileBtn = document.getElementById("registerFromFileBtn");
const registerStatus = document.getElementById("registerStatus");

const attendanceFile = document.getElementById("attendanceFile");
const markFromCameraBtn = document.getElementById("markFromCameraBtn");
const markFromFileBtn = document.getElementById("markFromFileBtn");
const attendanceStatus = document.getElementById("attendanceStatus");
const attendanceResult = document.getElementById("attendanceResult");
const matchedEmployee = document.getElementById("matchedEmployee");
const matchSimilarity = document.getElementById("matchSimilarity");

const registeredEmployees = document.getElementById("registeredEmployees");
const attendanceToday = document.getElementById("attendanceToday");
const presentToday = document.getElementById("presentToday");
const recentLogs = document.getElementById("recentLogs");
const refreshLogsBtn = document.getElementById("refreshLogsBtn");

let cameraStream = null;

function setCameraState(text, active = false) {
    cameraStateBadge.textContent = text;
    cameraStateBadge.style.color = active ? "#b7f7dc" : "";
}

function setMessage(element, message, type = "info") {
    element.textContent = message;
    element.className = `status-text status-${type}`;
}

function setAttendanceCard(title, message, tag = "Waiting") {
    attendanceResult.innerHTML = `
        <span class="result-tag">${tag}</span>
        <h4>${title}</h4>
        <p>${message}</p>
    `;
}

async function startCamera() {
    if (cameraStream) {
        return;
    }

    try {
        cameraStream = await navigator.mediaDevices.getUserMedia({
            video: { facingMode: "user", width: { ideal: 1280 }, height: { ideal: 720 } },
            audio: false
        });
        cameraPreview.srcObject = cameraStream;
        setCameraState("Camera live", true);
    } catch (error) {
        setCameraState("Camera blocked", false);
        setMessage(registerStatus, `Camera access failed: ${error.message}`, "error");
    }
}

function stopCamera() {
    if (!cameraStream) {
        return;
    }

    cameraStream.getTracks().forEach(track => track.stop());
    cameraStream = null;
    cameraPreview.srcObject = null;
    setCameraState("Camera offline", false);
}

function fileToBlob(file) {
    return new Blob([file], { type: file.type || "image/jpeg" });
}

function captureFrameBlob() {
    return new Promise((resolve, reject) => {
        if (!cameraStream || !cameraPreview.videoWidth || !cameraPreview.videoHeight) {
            reject(new Error("Start the camera before capturing a frame."));
            return;
        }

        captureCanvas.width = cameraPreview.videoWidth;
        captureCanvas.height = cameraPreview.videoHeight;
        const context = captureCanvas.getContext("2d");
        context.drawImage(cameraPreview, 0, 0, captureCanvas.width, captureCanvas.height);
        captureCanvas.toBlob(blob => {
            if (!blob) {
                reject(new Error("Unable to capture the current frame."));
                return;
            }
            resolve(blob);
        }, "image/jpeg", 0.92);
    });
}

async function postMultipart(url, fileBlob, fileName, fields = {}) {
    const formData = new FormData();
    Object.entries(fields).forEach(([key, value]) => formData.append(key, value));
    formData.append("file", fileBlob, fileName);

    const response = await fetch(url, {
        method: "POST",
        body: formData
    });
    const data = await response.json();
    if (!response.ok) {
        throw new Error(data.message || "Request failed.");
    }
    return data;
}

function renderLogs(logs) {
    if (!logs.length) {
        recentLogs.innerHTML = `
            <article class="log-empty">
                <h4>No attendance logs yet</h4>
                <p>Register at least one employee and mark attendance to populate this list.</p>
            </article>
        `;
        return;
    }

    recentLogs.innerHTML = logs.map(log => `
        <article class="log-card">
            <div class="log-title">
                <h4>${log.fullName}</h4>
                <span class="result-tag log-badge">${log.status}</span>
            </div>
            <p>Employee code ${log.employeeCode} was matched and recorded successfully.</p>
            <div class="log-meta">
                <div>
                    <span>Similarity</span>
                    <strong>${log.similarity}%</strong>
                </div>
                <div>
                    <span>Captured file</span>
                    <strong>${log.capturedImagePath}</strong>
                </div>
                <div>
                    <span>Recorded at</span>
                    <strong>${new Date(log.createdAt).toLocaleString()}</strong>
                </div>
            </div>
        </article>
    `).join("");
}

async function loadSummary() {
    try {
        const response = await fetch(`${API_BASE_URL}/summary`);
        const data = await response.json();
        if (!response.ok) {
            throw new Error(data.message || "Unable to load attendance summary.");
        }

        registeredEmployees.textContent = data.stats.registeredEmployees;
        attendanceToday.textContent = data.stats.attendanceToday;
        presentToday.textContent = data.stats.presentToday;
        renderLogs(data.recentLogs || []);
    } catch (error) {
        renderLogs([]);
        setMessage(attendanceStatus, error.message, "error");
    }
}

async function handleRegistration(source) {
    const fullName = employeeName.value.trim();
    const employeeCodeValue = employeeCode.value.trim().toUpperCase();

    if (fullName.length < 3) {
        setMessage(registerStatus, "Enter a full name with at least 3 characters.", "error");
        return;
    }

    if (employeeCodeValue.length < 3) {
        setMessage(registerStatus, "Enter an employee code with at least 3 characters.", "error");
        return;
    }

    let blob;
    let fileName;

    try {
        if (source === "camera") {
            blob = await captureFrameBlob();
            fileName = `${employeeCodeValue.toLowerCase()}-camera.jpg`;
        } else {
            const file = registerFile.files[0];
            if (!file) {
                throw new Error("Choose a reference image before registering from file.");
            }
            blob = fileToBlob(file);
            fileName = file.name;
        }

        setMessage(registerStatus, "Registering face profile...", "info");
        const data = await postMultipart(`${API_BASE_URL}/register-face`, blob, fileName, {
            full_name: fullName,
            employee_code: employeeCodeValue
        });

        setMessage(registerStatus, `${data.profile.fullName} registered successfully.`, "success");
        employeeName.value = "";
        employeeCode.value = "";
        registerFile.value = "";
        await loadSummary();
    } catch (error) {
        setMessage(registerStatus, error.message, "error");
    }
}

async function handleAttendance(source) {
    let blob;
    let fileName;

    try {
        if (source === "camera") {
            blob = await captureFrameBlob();
            fileName = "attendance-camera.jpg";
        } else {
            const file = attendanceFile.files[0];
            if (!file) {
                throw new Error("Choose an attendance image before uploading from file.");
            }
            blob = fileToBlob(file);
            fileName = file.name;
        }

        setMessage(attendanceStatus, "Matching face and recording attendance...", "info");
        const data = await postMultipart(`${API_BASE_URL}/mark`, blob, fileName);
        matchedEmployee.textContent = `${data.match.fullName} (${data.match.employeeCode})`;
        matchSimilarity.textContent = `${data.match.similarity}%`;
        setAttendanceCard(
            "Attendance Marked",
            `${data.match.fullName} was recognized and marked present successfully.`,
            "Present"
        );
        setMessage(attendanceStatus, `Matched with ${data.match.detectedFaces} detected face region(s).`, "success");
        attendanceFile.value = "";
        await loadSummary();
    } catch (error) {
        matchedEmployee.textContent = "--";
        matchSimilarity.textContent = "--";
        setAttendanceCard("Match Not Completed", error.message, "Retry");
        setMessage(attendanceStatus, error.message, "error");
    }
}

startCameraBtn.addEventListener("click", startCamera);
stopCameraBtn.addEventListener("click", stopCamera);
registerFromCameraBtn.addEventListener("click", () => handleRegistration("camera"));
registerFromFileBtn.addEventListener("click", () => handleRegistration("file"));
markFromCameraBtn.addEventListener("click", () => handleAttendance("camera"));
markFromFileBtn.addEventListener("click", () => handleAttendance("file"));
refreshLogsBtn.addEventListener("click", loadSummary);

window.addEventListener("beforeunload", stopCamera);

setAttendanceCard("No attendance scan yet", "Use the camera or upload a clear employee image to mark attendance.", "Waiting");
loadSummary();
