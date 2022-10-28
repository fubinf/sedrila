document.addEventListener("click", e => {
  if (e.target.classList.contains("collapsible")) {
    e.target.classList.toggle("active");
    const content = e.target.nextElementSibling;
    if (content.style.display === "block") {
      content.style.display = "none";
    } else {
      content.style.display = "block";
    }
  }
}, false);
