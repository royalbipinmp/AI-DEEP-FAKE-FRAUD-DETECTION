document.addEventListener("DOMContentLoaded", () => {
const API_BASE_URL = "http://127.0.0.1:5000/api";
const currentUser = JSON.parse(localStorage.getItem("truthshieldCurrentUser") || "null");

if (!currentUser || !currentUser.id) {
window.location.href = "login.html";
return;
}

const totalScans = document.getElementById("totalScans");
const realScans = document.getElementById("realScans");
const fakeScans = document.getElementById("fakeScans");
const historyTableBody = document.getElementById("historyTableBody");

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

function renderRows(historyItems) {
if (!historyItems.length) {
historyTableBody.innerHTML = `
<tr>
    <td colspan="7" class="empty-state">No detection history yet. Run your first scan from the Detection page.</td>
</tr>
`;
return;
}

historyTableBody.innerHTML = historyItems.map(item => `
<tr>
    <td>${item.id}</td>
    <td>${item.file_name}</td>
    <td>${item.media_type}</td>
    <td><span class="${getResultClass(item.result)}">${item.result}</span></td>
    <td>${item.confidence}%</td>
    <td>${formatDate(item.created_at)}</td>
    <td><button type="button" class="table-action-btn" data-history-id="${item.id}">Delete</button></td>
</tr>
`).join("");
}

async function deleteHistoryItem(historyId) {
const response = await fetch(`${API_BASE_URL}/history/delete`, {
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
throw new Error(data.message || "Unable to delete history item.");
}

return data;
}

async function loadHistory() {
try {
const response = await fetch(`${API_BASE_URL}/history?user_id=${currentUser.id}`);
const data = await response.json();

if (!response.ok) {
throw new Error(data.message || "Unable to load history.");
}

const historyItems = data.history || [];
const realCount = historyItems.filter(item => item.result === "Real").length;
const fakeCount = historyItems.filter(item => item.result !== "Real").length;

totalScans.textContent = historyItems.length;
realScans.textContent = realCount;
fakeScans.textContent = fakeCount;
renderRows(historyItems);
} catch (error) {
historyTableBody.innerHTML = `
<tr>
    <td colspan="7" class="empty-state">${error.message}</td>
</tr>
`;
}
}

historyTableBody.addEventListener("click", async event => {
const button = event.target.closest("[data-history-id]");
if (!button) {
return;
}

const historyId = button.getAttribute("data-history-id");
const confirmed = window.confirm("Delete this history item?");

if (!confirmed) {
return;
}

try {
button.disabled = true;
button.textContent = "Deleting...";
await deleteHistoryItem(historyId);
await loadHistory();
} catch (error) {
window.alert(error.message);
button.disabled = false;
button.textContent = "Delete";
}
});

loadHistory();
});
