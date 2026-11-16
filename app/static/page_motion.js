(() => {
  // Feedback only: never intercept navigation or repeat a submitted request.
  const root = document.documentElement;
  const indicator = document.createElement('div');
  indicator.className = 'page-load-indicator';
  indicator.setAttribute('aria-hidden', 'true');
  document.body.append(indicator);
  let delay, expiry;
  function reset() {
    clearTimeout(delay); clearTimeout(expiry);
    delete root.dataset.pageLoading;
  }
  function pending(event) {
    queueMicrotask(() => {
      if (event.defaultPrevented) return;
      reset();
      delay = setTimeout(() => { root.dataset.pageLoading = ''; }, 120);
      // A cancelled browser navigation must not leave a permanent loading bar.
      expiry = setTimeout(reset, 15000);
    });
  }
  document.addEventListener('click', event => {
    if (event.button !== 0 || event.metaKey || event.ctrlKey || event.shiftKey || event.altKey) return;
    const link = event.target.closest('a[href]');
    if (!link || link.hasAttribute('download') || (link.target && link.target !== '_self')) return;
    const url = new URL(link.href, location.href);
    if (url.origin !== location.origin || !/^https?:$/.test(url.protocol)) return;
    if (url.pathname === location.pathname && url.search === location.search) return;
    if (url.pathname.startsWith('/download/') || /\.(pdf|xlsx)$/i.test(url.pathname) || url.searchParams.has('format')) return;
    pending(event);
  });
  document.addEventListener('submit', event => {
    const form = event.target;
    if (form.target && form.target !== '_self') return;
    pending(event);
  });
  window.addEventListener('pageshow', reset);
  window.addEventListener('pagehide', reset);
})();
