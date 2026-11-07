(() => {
  // Keep normal navigation and form serialization (including clicked button values).
  const pending = new Map();
  let refreshing = false;
  let feedbackTimer;

  function feedback(nodes, duration = 7000) {
    const region = document.getElementById('actionFeedback');
    region.replaceChildren(...nodes);
    clearTimeout(feedbackTimer);
    feedbackTimer = setTimeout(() => region.replaceChildren(), duration);
  }

  async function refresh(form, button) {
    const ids = form.dataset.refresh.split(/\s+/);
    const modal = form.closest('.modal-overlay.open');
    const values = new FormData(form, button || undefined);
    const body = form.enctype === 'multipart/form-data' ? values : new URLSearchParams(values);
    refreshing = true;
    form.setAttribute('aria-busy', 'true');
    if (button) button.disabled = true;
    try {
      const response = await fetch(form.action, {
        method: 'POST', body, cache: 'no-store',
        headers: {'X-Library-Page': location.pathname + location.search},
      });
      if (!response.ok) {
        const result = response.headers.get('Content-Type')?.includes('application/json') ? await response.json() : null;
        throw new Error(result?.error || '');
      }
      if (new URL(response.url).pathname !== location.pathname) {
        if (response.redirected) { location.assign(response.url); return; }
        throw new Error();
      }
      const page = new DOMParser().parseFromString(await response.text(), 'text/html');
      const validation = page.querySelector('[data-refresh] [data-notice-error]');
      if (validation) throw new Error(validation.textContent);
      const pairs = ids.map(id => [document.getElementById(id), page.getElementById(id)]);
      if (pairs.some(([current, next]) => !current || !next)) throw new Error();
      const messages = [...page.querySelectorAll('#pageFlashes > .alert')];
      const position = {top: window.scrollY, left: window.scrollX, behavior: 'instant'};
      document.getElementById('pageFlashes').replaceChildren();
      if (messages.some(message => message.classList.contains('alert-danger'))) {
        // An open dialog can cover page feedback, so show validation next to its form.
        if (modal) {
          form.querySelector('[data-action-error]')?.remove();
          const message = messages.find(node => node.classList.contains('alert-danger'));
          message.setAttribute('data-action-error', '');
          form.prepend(message);
        } else feedback(messages);
        return;
      }
      if (modal) closeModal(modal.id);
      const fieldValues = ['tableSearch', 'tableFilter'].map(id => [id, document.getElementById(id)?.value]);
      for (const [current, next] of pairs) {
        const scroll = [...current.querySelectorAll('.table-wrap')].map(table => table.scrollLeft);
        const open = [...current.querySelectorAll('details')].map(item => item.open);
        current.replaceWith(next);
        next.querySelectorAll('.table-wrap').forEach((table, index) => { table.scrollLeft = scroll[index] ?? 0; });
        next.querySelectorAll('details').forEach((item, index) => { if (open[index] !== undefined) item.open = open[index]; });
      }
      for (const [id, value] of fieldValues) {
        const field = document.getElementById(id);
        if (field && value !== undefined) {
          field.value = value;
          if (field.selectedIndex === -1) field.selectedIndex = 0;
        }
      }
      if (form.isConnected) {
        form.querySelector('[data-action-error]')?.remove();
        if (messages.some(message => message.classList.contains('alert-success'))) {
          form.reset();
          form.dispatchEvent(new Event('input', {bubbles: true}));
        }
      }
      document.dispatchEvent(new Event('library:content-updated'));
      feedback(messages, Number(form.dataset.feedbackMs) || undefined);
      window.scrollTo(position);
    } catch (error) {
      const message = document.createElement('p');
      message.className = 'alert alert-danger';
      message.setAttribute('role', 'alert');
      message.textContent = error.message || 'Không xác nhận được kết quả. Hãy kiểm tra lại danh sách trước khi thử lại.';
      if (modal?.classList.contains('open')) {
        form.querySelector('[data-action-error]')?.remove();
        message.setAttribute('data-action-error', '');
        form.prepend(message);
      } else feedback([message]);
    } finally {
      refreshing = false;
      form.removeAttribute('aria-busy');
      if (button) button.disabled = false;
    }
  }
  function reset(form) {
    const state = pending.get(form); if (!state) return;
    clearTimeout(state.timer); form.removeAttribute('aria-busy');
    if (state.button) state.button.removeAttribute('aria-disabled');
    pending.delete(form);
  }
  document.addEventListener('submit', event => {
    const form = event.target;
    if (!(form instanceof HTMLFormElement) || form.method.toLowerCase() !== 'post') return;
    if (event.defaultPrevented) return;
    if (form.dataset?.refresh) {
      event.preventDefault();
      if (!refreshing) void refresh(form, event.submitter);
      return;
    }
    if (pending.has(form)) { event.preventDefault(); return; }
    // AJAX handlers own their loading/errors. Confirm dialogs may cancel submission.
    queueMicrotask(() => {
      if (event.defaultPrevented || !form.isConnected) return;
      form.setAttribute('aria-busy','true');
      event.submitter?.setAttribute('aria-disabled','true');
      pending.set(form, {button:event.submitter,timer:setTimeout(() => reset(form),30000)});
    });
  });
  window.addEventListener('pageshow', () => { for (const form of pending.keys()) reset(form); });
  // Preserve the sidebar's scroll position between full navigations.
  const nav = document.querySelector('.sidebar .nav');
  if (nav) {
    try { nav.scrollTop = Number(sessionStorage.getItem('library-nav-scroll')) || 0; } catch (_) {}
    window.addEventListener('pagehide', () => { try { sessionStorage.setItem('library-nav-scroll',String(nav.scrollTop)); } catch (_) {} });
  }
})();
