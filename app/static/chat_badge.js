(() => {
  const badges = document.querySelectorAll('[data-chat-unread]');
  if (!badges.length) return;
  let busy = false;
  async function refresh() {
    if (busy || document.hidden) return;
    busy = true;
    try {
      const response = await fetch('/chat/api/unread', {cache:'no-store', headers:{Accept:'application/json'}});
      if (!response.ok || response.redirected) return;
      const data = await response.json();
      badges.forEach(badge => { badge.hidden = !data.unread; badge.textContent = data.unread > 99 ? '99+' : data.unread; badge.setAttribute('aria-label', `${data.unread} tin nhắn chưa đọc`); });
    } catch (_) {} finally { busy = false; }
  }
  refresh(); setInterval(refresh, document.getElementById('messenger') ? 3000 : 10000);
  window.addEventListener('focus', refresh);
})();
