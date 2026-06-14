const API_BASE_URL = "http://127.0.0.1:5000/api";
const loginForm = document.getElementById("loginForm");
const formMessage = document.getElementById("formMessage");
const pageContextMessage = document.getElementById("pageContextMessage");
const searchParams = new URLSearchParams(window.location.search);
const nextTarget = searchParams.get("next") || "upload.html";
const source = searchParams.get("source") || "";
const loginMessage = searchParams.get("message") || "";

if (pageContextMessage) {
if (source === "detection" && loginMessage === "analysis-ready") {
pageContextMessage.hidden = false;
pageContextMessage.textContent = "Your account is ready. Sign in to continue with secure media analysis.";
} else if (source === "detection") {
pageContextMessage.hidden = false;
pageContextMessage.textContent = "Sign in to continue your detection workflow and save the result to your secure history.";
}
}

const fields = {
email: {
input: document.getElementById("email"),
error: document.getElementById("emailError")
},
password: {
input: document.getElementById("password"),
error: document.getElementById("passwordError")
}
};

function setFieldError(fieldKey, message) {
const field = fields[fieldKey];
field.error.textContent = message;
field.input.classList.toggle("input-error", Boolean(message));
}

function clearErrors() {
Object.keys(fields).forEach(fieldKey => setFieldError(fieldKey, ""));
formMessage.textContent = "";
formMessage.className = "status-message";
}

function validateEmail(email) {
return /^[^\s@]+@[^\s@]+\.[^\s@]+$/.test(email);
}

async function loginUser(credentials) {
const response = await fetch(`${API_BASE_URL}/login`, {
method: "POST",
headers: {
"Content-Type": "application/json"
},
body: JSON.stringify(credentials)
});

const data = await response.json();

if (!response.ok) {
throw new Error(data.message || "Login failed.");
}

return data.user;
}

loginForm.addEventListener("submit", async event => {
event.preventDefault();
clearErrors();

const email = fields.email.input.value.trim();
const password = fields.password.input.value;
let isValid = true;

if (!validateEmail(email)) {
setFieldError("email", "Please enter a valid email address.");
isValid = false;
}

if (password.length < 8) {
setFieldError("password", "Please enter your registered password.");
isValid = false;
}

if (!isValid) {
formMessage.textContent = "Please correct the highlighted fields and try again.";
formMessage.className = "status-message error";
return;
}

const submitButton = loginForm.querySelector(".submit-btn");

try {
submitButton.disabled = true;
submitButton.textContent = "Signing In...";

const user = await loginUser({ email, password });
localStorage.setItem("truthshieldCurrentUser", JSON.stringify(user));

formMessage.textContent = user.isAdmin
? "Admin login successful. Redirecting to the dashboard..."
: "Login successful. Redirecting to detection...";
formMessage.className = "status-message success";
loginForm.reset();

setTimeout(() => {
window.location.href = user.isAdmin ? "admin.html" : nextTarget;
}, 1000);
} catch (error) {
setFieldError("email", "No matching account found.");
setFieldError("password", "Password or email is incorrect.");
formMessage.textContent = error.message;
formMessage.className = "status-message error";
} finally {
submitButton.disabled = false;
submitButton.textContent = "Login";
}
});

Object.values(fields).forEach(field => {
field.input.addEventListener("input", () => {
field.input.classList.remove("input-error");
field.error.textContent = "";
if (formMessage.classList.contains("error")) {
formMessage.textContent = "";
formMessage.className = "status-message";
}
});
});
