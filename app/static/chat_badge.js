(() => {
  const badges = document.querySelectorAll('[data-chat-unread]');
  if (!badges.length) return;
  function render(unread) {
    if (!Number.isFinite(unread) || unread < 0) return;
    badges.forEach(badge => {
      const text = String(unread > 99 ? '99+' : unread);
      if(badge.textContent !== text)badge.textContent=text;
      if(badge.hidden === Boolean(unread))badge.hidden=!unread;
      const label=`${unread} tin nhắn chưa đọc`;if(badge.getAttribute('aria-label')!==label)badge.setAttribute('aria-label',label);
    });
  }
  document.addEventListener('library:chat-unread',event=>render(event.detail.unread));
  window.addEventListener('message',event=>{
    const frame=document.getElementById('chatWidgetFrame');
    if(frame && event.origin===location.origin && event.source===frame.contentWindow && event.data?.type==='library-chat-unread')render(event.data.unread);
  });
  // Messenger already receives unread counts with its overview. Avoid duplicate polling.
  if(document.getElementById('messenger'))return;
  let busy = false;
  async function refresh() {
    if (busy || document.hidden || document.querySelector('.chat-widget.is-open')) return;
    busy = true;
    try {
      const response = await fetch('/chat/api/unread', {cache:'no-store', headers:{Accept:'application/json'}});
      if (!response.ok || response.redirected) return;
      render((await response.json()).unread);
    } catch (_) {} finally { busy = false; }
  }
  refresh(); setInterval(refresh,10000);
  window.addEventListener('focus',refresh);
  document.addEventListener('visibilitychange',refresh);
})();
