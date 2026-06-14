document.addEventListener("DOMContentLoaded", () => {
const API_BASE_URL = "http://127.0.0.1:5000/api";
const currentUser = JSON.parse(localStorage.getItem("truthshieldCurrentUser") || "null");

if (!currentUser || !currentUser.isAdmin) {
window.location.href = "login.html";
return;
}

const totalUsers = document.getElementById("totalUsers");
const totalDetections = document.getElementById("totalDetections");
const flaggedDetections = document.getElementById("flaggedDetections");
const usersTableBody = document.getElementById("usersTableBody");
const recentDetectionsBody = document.getElementById("recentDetectionsBody");

function getResultClass(result) {
if (result === "Fake") {
return "result-fake";
}

if (result === "Review") {
return "result-review";
}

return "result-real";
}

function formatDate(dateText) {
const date = new Date(dateText);
return Number.isNaN(date.getTime()) ? dateText : date.toLocaleString();
}

function renderUsers(users) {
if (!users.length) {
usersTableBody.innerHTML = `
<tr>
    <td colspan="3" class="empty-state">No registered users found.</td>
</tr>
`;
return;
}

usersTableBody.innerHTML = users.map(user => `
<tr>
    <td>${user.full_name}</td>
    <td>${user.email}</td>
    <td>
        ${user.is_admin ? '<span class="role-badge">Admin</span>' : `<button type="button" class="table-action-btn" data-user-id="${user.id}">Delete</button>`}
    </td>
</tr>
`).join("");
}

function renderDetections(detections) {
if (!detections.length) {
recentDetectionsBody.innerHTML = `
<tr>
    <td colspan="7" class="empty-state">No detections have been saved yet.</td>
</tr>
`;
return;
}

recentDetectionsBody.innerHTML = detections.map(item => `
<tr>
    <td>${item.id}</td>
    <td>${item.full_name}</td>
    <td>${item.file_name}</td>
    <td>${item.media_type}</td>
    <td><span class="${getResultClass(item.result)}">${item.result}</span></td>
    <td>${item.confidence}%</td>
    <td><button type="button" class="table-action-btn" data-detection-id="${item.id}">Delete</button></td>
</tr>
`).join("");
}

async function deleteDetection(historyId) {
const response = await fetch(`${API_BASE_URL}/admin/delete-history`, {
method: "POST",
headers: {
"Content-Type": "application/json"
},
body: JSON.stringify({
user_id: currentUser.id,
history_id: historyId
})
});

const data = await response.json();

if (!response.ok) {
throw new Error(data.message || "Unable to delete detection.");
}

return data;
}

async function deleteUser(targetUserId) {
const response = await fetch(`${API_BASE_URL}/admin/delete-user`, {
method: "POST",
headers: {
"Content-Type": "application/json"
},
body: JSON.stringify({
user_id: currentUser.id,
target_user_id: targetUserId
})
});

const data = await response.json();

if (!response.ok) {
throw new Error(data.message || "Unable to delete user.");
}

return data;
}

async function loadAdminDashboard() {
try {
const response = await fetch(`${API_BASE_URL}/admin/users?user_id=${currentUser.id}`);
const data = await response.json();

if (!response.ok) {
throw new Error(data.message || "Unable to load admin dashboard.");
}

totalUsers.textContent = data.stats.totalUsers;
totalDetections.textContent = data.stats.totalDetections;
flaggedDetections.textContent = data.stats.flaggedDetections;
renderUsers(data.users || []);
renderDetections(data.recentDetections || []);
} catch (error) {
usersTableBody.innerHTML = `
<tr>
    <td colspan="3" class="empty-state">${error.message}</td>
</tr>
`;
recentDetectionsBody.innerHTML = `
<tr>
    <td colspan="7" class="empty-state">${error.message}</td>
</tr>
`;
}
}

usersTableBody.addEventListener("click", async event => {
const button = event.target.closest("[data-user-id]");
if (!button) {
return;
}

const targetUserId = button.getAttribute("data-user-id");
const confirmed = window.confirm("Delete this user and all of their saved detections?");

if (!confirmed) {
return;
}

try {
button.disabled = true;
button.textContent = "Deleting...";
await deleteUser(targetUserId);
await loadAdminDashboard();
} catch (error) {
window.alert(error.message);
button.disabled = false;
button.textContent = "Delete";
}
});

recentDetectionsBody.addEventListener("click", async event => {
const button = event.target.closest("[data-detection-id]");
if (!button) {
return;
}

const detectionId = button.getAttribute("data-detection-id");
const confirmed = window.confirm("Delete this detection record?");

if (!confirmed) {
return;
}

try {
button.disabled = true;
button.textContent = "Deleting...";
await deleteDetection(detectionId);
await loadAdminDashboard();
} catch (error) {
window.alert(error.message);
button.disabled = false;
button.textContent = "Delete";
}
});

loadAdminDashboard();
});
