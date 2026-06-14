document.addEventListener("DOMContentLoaded", () => {
const currentUser = JSON.parse(localStorage.getItem("truthshieldCurrentUser") || "null");
const historyNavLink = document.getElementById("historyNavLink");
const adminNavLink = document.getElementById("adminNavLink");
const guestActions = document.getElementById("guestActions");
const userActions = document.getElementById("userActions");
const navUserName = document.getElementById("navUserName");
const logoutBtn = document.getElementById("logoutBtn");

if (currentUser) {
if (guestActions) {
guestActions.classList.add("hidden-nav");
}

if (userActions) {
userActions.classList.remove("hidden-nav");
}

if (historyNavLink) {
historyNavLink.classList.remove("hidden-nav");
}

if (navUserName) {
navUserName.textContent = currentUser.isAdmin ? "Admin" : currentUser.fullName;
}

if (currentUser.isAdmin && adminNavLink) {
adminNavLink.classList.remove("hidden-nav");
}
} else {
if (guestActions) {
guestActions.classList.remove("hidden-nav");
}

if (userActions) {
userActions.classList.add("hidden-nav");
}
}

if (logoutBtn) {
logoutBtn.addEventListener("click", () => {
localStorage.removeItem("truthshieldCurrentUser");
window.location.href = "index.html";
});
}
});
