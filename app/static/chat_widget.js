(() => {
  const widget = document.getElementById('chatWidget'); if (!widget) return;
  const launcher = document.getElementById('chatWidgetLauncher');
  const panel = document.getElementById('chatWidgetPanel');
  const frame = document.getElementById('chatWidgetFrame');
  const loading = document.getElementById('chatWidgetLoading');
  const storageKey = 'chat-widget-open-' + widget.dataset.userId;
  let opened = false, loaded = false;
  function notify() {
    if (loaded) frame.contentWindow?.postMessage({type:'library-chat-widget-visibility', open:opened}, location.origin);
  }
  function setOpen(value) {
    opened = value;
    widget.classList.toggle('is-open', opened);
    panel.inert = !opened; panel.setAttribute('aria-hidden', String(!opened));
    launcher.setAttribute('aria-expanded', String(opened));
    launcher.setAttribute('aria-label', opened ? 'Thu nhỏ tin nhắn' : 'Mở tin nhắn');
    try { sessionStorage.setItem(storageKey, opened ? '1' : '0'); } catch (_) {}
    if (opened && !frame.getAttribute('src')) {
      let url = frame.dataset.src;
      try { const id = sessionStorage.getItem('chat-widget-thread-' + widget.dataset.userId); if (/^[1-9]\d*$/.test(id || '')) url += '&thread=' + id; } catch (_) {}
      frame.src = url;
    }
    notify();
    if (opened && loaded) frame.focus(); else if (!opened) launcher.focus({preventScroll:true});
  }
  launcher.addEventListener('click', () => setOpen(!opened));
  document.getElementById('chatWidgetMinimize').addEventListener('click', () => setOpen(false));
  frame.addEventListener('load', () => {
    if (!frame.getAttribute('src')) return;
    loaded = true;
    try {
      if (frame.contentWindow.location.pathname !== '/messenger') {
        loading.textContent = 'Phiên đăng nhập đã thay đổi. Vui lòng tải lại trang để tiếp tục.'; frame.hidden = true; return;
      }
    } catch (_) { return; }
    frame.hidden = false; loading.hidden = true; notify(); if (opened) frame.focus();
  });
  window.addEventListener('message', event => {
    if (event.origin !== location.origin || event.source !== frame.contentWindow) return;
    if (event.data?.type === 'library-chat-widget-close') setOpen(false);
  });
  document.addEventListener('keydown', event => {
    if (event.key === 'Escape' && opened && widget.contains(document.activeElement)) { event.preventDefault(); setOpen(false); }
  });
  window.addEventListener('pagehide', () => { if (loaded) frame.contentWindow?.postMessage({type:'library-chat-widget-visibility',open:false}, location.origin); });
  let restored = false; try { restored = sessionStorage.getItem(storageKey) === '1'; } catch (_) {}
  if (restored) setOpen(true);
})();
