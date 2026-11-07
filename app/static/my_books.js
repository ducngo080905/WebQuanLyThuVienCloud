(() => {
  const getShelf = () => document.getElementById('bookshelfPage');
  let selected;

  function show(id) {
    const root = getShelf();
    const panels = [...root.querySelectorAll('[data-books-panel]')];
    selected = panels.some(panel => panel.id === id) ? id : 'active-loans';
    for (const panel of panels) panel.hidden = panel.id !== selected;
    for (const link of root.querySelectorAll('.bookshelf-tabs a')) {
      if (link.dataset.booksView === selected) link.setAttribute('aria-current', 'page');
      else link.removeAttribute('aria-current');
    }
  }

  document.addEventListener('click', event => {
    const link = event.target.closest('#bookshelfPage [data-books-view]');
    if (!link || event.button !== 0 || event.ctrlKey || event.metaKey || event.shiftKey || event.altKey) return;
    event.preventDefault();
    show(link.dataset.booksView);
    history.replaceState(null, '', '#' + selected);
  });
  window.addEventListener('hashchange', () => show(location.hash.slice(1)));
  document.addEventListener('library:content-updated', () => show(selected));
  show(location.hash.slice(1) || getShelf().dataset.initialView);
})();
