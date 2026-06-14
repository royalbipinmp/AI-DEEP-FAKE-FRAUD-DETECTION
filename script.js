document.addEventListener("DOMContentLoaded", () => {
const cards = document.querySelectorAll("#about .card");
const flowSteps = document.querySelectorAll("#works .flow-step");
const heroItems = document.querySelectorAll(".hero-reveal");
const sections = document.querySelectorAll("section[id]");
const navLinks = document.querySelectorAll(".nav-center a");
const startDetectionBtn = document.getElementById("startDetectionBtn");
const navbar = document.querySelector(".navbar");

function getHeaderOffset() {
if (!navbar) {
 return 104;
}

const navbarTop = parseFloat(window.getComputedStyle(navbar).top) || 0;
return navbar.offsetHeight + navbarTop + 8;
}

document.querySelectorAll('a[href^="#"]').forEach(anchor => {
anchor.addEventListener("click", event => {
const href = anchor.getAttribute("href");
const target = document.querySelector(href);

if (!target) {
return;
}

event.preventDefault();

const scrollTarget = href === "#top"
? 0
: Math.max(0, target.getBoundingClientRect().top + window.scrollY - getHeaderOffset());

window.scrollTo({
top: scrollTarget,
behavior: "smooth"
});
});
});

if (startDetectionBtn) {
startDetectionBtn.addEventListener("click", () => {
window.location.href = "upload.html";
});
}

const revealTargets = [...heroItems, ...flowSteps, ...cards];

heroItems.forEach(item => item.classList.add("is-visible"));

const observer = new IntersectionObserver(entries => {
entries.forEach(entry => {
if (entry.isIntersecting) {
entry.target.classList.add("is-visible");
}
});
}, {
threshold: 0.18
});

revealTargets.forEach(item => observer.observe(item));

function updateActiveLink() {
let current = "#top";

sections.forEach(section => {
const sectionTop = section.offsetTop - 140;
if (window.scrollY >= sectionTop) {
current = `#${section.getAttribute("id")}`;
}
});

navLinks.forEach(link => {
const href = link.getAttribute("href");
const isHome = href === "#top" && current === "#top";
const isSection = href === current;

link.classList.toggle("active", isHome || isSection);
});
}

window.addEventListener("scroll", updateActiveLink, { passive: true });
window.addEventListener("load", updateActiveLink);
updateActiveLink();
});
