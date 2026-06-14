const API_BASE_URL = "http://127.0.0.1:5000/api";
const registerForm = document.getElementById("registerForm");
const formMessage = document.getElementById("formMessage");
const pageContextMessage = document.getElementById("pageContextMessage");
const searchParams = new URLSearchParams(window.location.search);
const nextTarget = searchParams.get("next") || "upload.html";
const source = searchParams.get("source") || "";

if (pageContextMessage && source === "detection") {
pageContextMessage.hidden = false;
pageContextMessage.textContent = "Create your TruthShield account to unlock secure media analysis. Once registration is complete, you can sign in and continue your detection workflow.";
}

const fields = {
fullName: {
input: document.getElementById("fullName"),
error: document.getElementById("nameError")
},
email: {
input: document.getElementById("email"),
error: document.getElementById("emailError")
},
password: {
input: document.getElementById("password"),
error: document.getElementById("passwordError")
},
confirmPassword: {
input: document.getElementById("confirmPassword"),
error: document.getElementById("confirmPasswordError")
}
};

function setFieldError(fieldKey, message) {
const field = fields[fieldKey];
field.error.textContent = message;
field.input.classList.toggle("input-error", Boolean(message));
}

function clearFieldError(fieldKey) {
setFieldError(fieldKey, "");
}

function validateEmail(email) {
return /^[^\s@]+@[^\s@]+\.[^\s@]+$/.test(email);
}

function validateForm() {
let isValid = true;

const fullName = fields.fullName.input.value.trim();
const email = fields.email.input.value.trim();
const password = fields.password.input.value;
const confirmPassword = fields.confirmPassword.input.value;

Object.keys(fields).forEach(clearFieldError);
formMessage.textContent = "";
formMessage.className = "status-message";

if (fullName.length < 3) {
setFieldError("fullName", "Please enter at least 3 characters.");
isValid = false;
}

if (!validateEmail(email)) {
setFieldError("email", "Please enter a valid email address.");
isValid = false;
}

if (password.length < 8) {
setFieldError("password", "Password must be at least 8 characters long.");
isValid = false;
} else if (!/[A-Za-z]/.test(password) || !/\d/.test(password)) {
setFieldError("password", "Use both letters and numbers in the password.");
isValid = false;
}

if (confirmPassword !== password || confirmPassword === "") {
setFieldError("confirmPassword", "Passwords do not match.");
isValid = false;
}

return {
isValid,
user: {
fullName,
email,
password
}
};
}

async function submitRegistration(user) {
const response = await fetch(`${API_BASE_URL}/register`, {
method: "POST",
headers: {
"Content-Type": "application/json"
},
body: JSON.stringify(user)
});

const data = await response.json();

if (!response.ok) {
throw new Error(data.message || "Registration failed.");
}

return data;
}

registerForm.addEventListener("submit", async event => {
event.preventDefault();

const { isValid, user } = validateForm();

if (!isValid) {
formMessage.textContent = "Please correct the highlighted fields and try again.";
formMessage.className = "status-message error";
return;
}

const submitButton = registerForm.querySelector(".submit-btn");

try {
submitButton.disabled = true;
submitButton.textContent = "Creating Account...";

await submitRegistration(user);

formMessage.textContent = "Registration successful. Redirecting to login...";
formMessage.className = "status-message success";
registerForm.reset();

setTimeout(() => {
const loginUrl = new URL("login.html", window.location.href);
loginUrl.searchParams.set("next", nextTarget);
if (source) {
loginUrl.searchParams.set("source", source);
}
loginUrl.searchParams.set("message", "analysis-ready");
window.location.href = loginUrl.toString();
}, 1200);
} catch (error) {
if (error.message.toLowerCase().includes("email")) {
setFieldError("email", error.message);
}
formMessage.textContent = error.message;
formMessage.className = "status-message error";
} finally {
submitButton.disabled = false;
submitButton.textContent = "Create Account";
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
