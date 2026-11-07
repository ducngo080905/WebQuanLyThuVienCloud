(() => {
  const csrf = document.currentScript.dataset.csrf;
  const phoneOverlay = document.getElementById('phoneRequiredOverlay');
  const phoneForm = document.getElementById('requiredPhoneForm');
  const ticker = document.getElementById('noticeTicker');
  const tickerWindow = ticker?.querySelector('.notice-ticker-window');
  const track = ticker?.querySelector('.notice-ticker-track');
  const lists = ticker?.querySelectorAll('.notice-ticker-list');
  let previousFocus;
  let phoneRequired = false;
  let busy = false;
  let lastNotices = '';

  function sizeTicker() {
    track.style.setProperty('--notice-window', `${tickerWindow.clientWidth}px`);
    track.style.setProperty('--notice-duration', `${Math.max(10, lists[0].scrollWidth / 55)}s`);
  }

  if (tickerWindow) new ResizeObserver(sizeTicker).observe(tickerWindow);

  function renderNotices(notices) {
    if (!ticker) return;
    const signature = JSON.stringify(notices);
    if (lastNotices === signature) return;
    lastNotices = signature;
    ticker.hidden = notices.length === 0;
    const items = notices.map(notice => {
      const item = document.createElement('li');
      if (notice.color) item.style.color = notice.color;
      if (notice.title) {
        const title = document.createElement('strong');
        title.textContent = notice.title;
        item.append(title, ' · ');
      }
      item.append(notice.body);
      return item;
    });
    lists[0].replaceChildren(...items);
    lists[1].replaceChildren(...items.map(item => item.cloneNode(true)));
    sizeTicker();
  }

  function renderPhone() {
    if (phoneOverlay.hidden !== phoneRequired) return;
    if (phoneRequired) previousFocus = document.activeElement;
    phoneOverlay.hidden = !phoneRequired;
    for (const selector of ['.main', '.reader-navigation', 'header', '.sidebar']) {
      document.querySelector(selector)?.toggleAttribute('inert', phoneRequired);
    }
    document.body.classList.toggle('live-modal-open', phoneRequired);
    if (phoneRequired) phoneForm.querySelector('input').focus();
    else previousFocus?.focus();
  }

  async function poll() {
    if (busy || document.visibilityState !== 'visible') return;
    busy = true;
    try {
      const response = await fetch('/live-updates', {cache: 'no-store', redirect: 'error'});
      if (!response.ok) return;
      const data = await response.json();
      const googleNotice = document.getElementById('googleLinkNotice');
      if (googleNotice) googleNotice.hidden = !data.google_link_required;
      phoneRequired = data.phone_required;
      renderPhone();
      renderNotices(data.announcements);
    } catch {
      // Keep the last successfully fetched notices during a temporary network outage.
    } finally {
      busy = false;
    }
  }

  phoneForm.addEventListener('submit', async event => {
    event.preventDefault();
    const button = phoneForm.querySelector('button');
    const error = document.getElementById('requiredPhoneError');
    button.disabled = true;
    error.textContent = '';
    try {
      const response = await fetch('/profile/required-phone', {
        method: 'POST',
        body: new URLSearchParams({csrf_token: csrf, phone: phoneForm.elements.phone.value}),
        redirect: 'error',
      });
      const data = await response.json();
      if (!response.ok) throw Error(data.error || 'Không lưu được số điện thoại.');
      phoneRequired = false;
      renderPhone();
      await poll();
    } catch (failure) {
      error.textContent = failure.message || 'Mất kết nối. Vui lòng thử lại.';
    } finally {
      button.disabled = false;
    }
  });

  document.addEventListener('keydown', event => {
    if (phoneOverlay.hidden) return;
    if (event.key === 'Escape') {
      event.preventDefault();
      event.stopImmediatePropagation();
    }
    if (event.key !== 'Tab') return;
    const elements = [...phoneOverlay.querySelectorAll('input,button')].filter(element => !element.disabled);
    const first = elements[0];
    const last = elements.at(-1);
    if (event.shiftKey && document.activeElement === first) {
      event.preventDefault();
      last.focus();
    } else if (!event.shiftKey && document.activeElement === last) {
      event.preventDefault();
      first.focus();
    }
  }, true);

  poll();
  setInterval(poll, 5000);
  document.addEventListener('visibilitychange', poll);
  window.addEventListener('focus', poll);
})();
