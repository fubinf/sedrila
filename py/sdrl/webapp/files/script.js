function sedrila_replace() {
    const span = this;
    const data = {
      'id': span.id,
      'index': parseInt(span.dataset.index),
      'cssclass': span.className,
      'text': span.textContent
    };

    fetch('/sedrila-replace.action', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(data),
    })
        .then(response => response.json())
        .then(json => {
            span.className = json.cssclass;
            span.textContent = json.text;
      })
      .catch(console.error);
};

document.querySelectorAll('.sedrila-replace').forEach(t => {
  t.addEventListener('click', sedrila_replace);
});

// Scroll selected task into view in the sidebar
(function() {
    const sel = document.querySelector('#task-select .task-link.selected');
    if (sel) sel.scrollIntoView({ block: 'start' });
})();
