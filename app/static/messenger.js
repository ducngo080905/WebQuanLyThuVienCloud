(() => {
  const root = document.getElementById('messenger');
  if (!root) return;
  const $ = id => document.getElementById(id);
  const me = Number(root.dataset.me);
  const isAdmin = root.dataset.admin === '1';
  const isEmbedded = document.body.classList.contains('chat-embed');
  let embeddedPaused = isEmbedded, embeddedStarted = false;
  const widgetThreadKey = 'chat-widget-thread-' + me;
  let blockedPeople = [], currentPeer = null, deletingThread = null, groupReads = [], groupInfo = null, groupInfoThread = null;
  const pickedGroupMembers = new Set();
  const csrf = root.dataset.csrf;
  $('contactSearch').placeholder = isAdmin ? 'Tìm tên hoặc vai trò…' : 'Tìm trong bạn bè đã thêm…';
  let threads = [], contacts = [], selected = null, generation = 0, records = [], peerRead = 0;
  let fetching = false, overviewBusy = false, sending = false, readThrough = 0, acknowledged = 0, lastTyping = 0;
  let typingTimer, lastList = '', retry = null, sendError = false;
  let changeCursor = 0, replyTarget = null, editing = null, editDraft = '', stagedFile = null, previewUrl = null, recalling = null, searchVersion = 0, searchBefore = null;
  const composeStates = new Map();
  const summary = message => message.deleted ? 'Tin nhắn đã thu hồi' : (message.body || message.attachment?.filename || 'Tin nhắn');
  const fileSize = size => size >= 1048576 ? (size / 1048576).toFixed(1) + ' MB' : Math.ceil(size / 1024) + ' KB';
  const stream = $('chatStream'), input = $('chatInput'), dialog = $('contactDialog');
  const normalize = s => s.normalize('NFD').replace(/[\u0300-\u036f]/g, '').replace(/đ/gi, 'd').toLowerCase();
  const initials = name => name.trim().split(/\s+/).slice(-2).map(part => part[0]).join('').toUpperCase();
  const timeLabel = value => new Date(value).toLocaleTimeString('vi-VN', {hour: '2-digit', minute: '2-digit'});
  const dateLabel = value => new Date(value).toLocaleDateString('vi-VN', {day: 'numeric', month: 'long', year: 'numeric'});
  const pinned = () => stream.scrollHeight - stream.scrollTop - stream.clientHeight < 100;
  const error = message => { $('chatError').textContent = message || ''; $('chatError').hidden = !message; };
  function el(tag, cls, text) { const node = document.createElement(tag); if (cls) node.className = cls; if (text !== undefined) node.textContent = text; return node; }
  async function api(path, data) {
    const response = await fetch('/chat/api/' + path, {method: data ? 'POST' : 'GET', credentials: 'same-origin', cache: 'no-store', headers: {Accept: 'application/json'}, body: data instanceof FormData ? (data.set('csrf_token', csrf), data) : data ? new URLSearchParams({...data, csrf_token: csrf}) : undefined});
    if (response.redirected || !response.headers.get('content-type')?.includes('application/json')) throw new Error('Phiên đăng nhập đã thay đổi. Vui lòng tải lại trang.');
    const result = await response.json();
    if (!response.ok) { const error = new Error(result.error || 'Chưa kết nối được. Vui lòng thử lại.'); error.status = response.status; throw error; }
    return result;
  }
  function fillAvatar(node, peer) {
    node.className = 'chat-avatar' + (peer.kind === 'group' ? ' group-avatar' : '') + (peer.online ? ' online' : '');
    if (node.dataset.avatar === (peer.avatar || '') && node.dataset.name === peer.name && node.dataset.kind === peer.kind) return;
    node.dataset.kind = peer.kind; node.dataset.avatar = peer.avatar || ''; node.dataset.name = peer.name; node.replaceChildren();
    if (peer.kind === 'group') { node.append(el('span','material-symbols-outlined','groups')); return; }
    if (peer.avatar) { const image = el('img'); image.src = peer.avatar; image.alt = ''; image.addEventListener('error', () => { image.remove(); node.textContent = initials(peer.name); }, {once:true}); node.append(image); } else node.textContent = initials(peer.name);
  }
  function avatar(peer) { const node = el('span', 'chat-avatar'); fillAvatar(node, peer); node.setAttribute('aria-hidden', 'true'); return node; }
  function updatePeer(peer) {
    currentPeer = peer;
    $('peerName').textContent = peer.name;
    $('peerRole').textContent = peer.role;
    $('peerStatus').textContent = peer.blocked_by_me ? 'Bạn đã chặn người này' : !peer.can_send ? (peer.active && !peer.is_contact && !isAdmin ? 'Thêm bạn bằng email để nhắn tin' : 'Hiện không thể nhắn tin') : (peer.online ? 'Đang hoạt động' : 'Hiện không hoạt động');
    if (peer.kind === 'group') $('peerStatus').textContent = peer.can_send ? `${peer.member_count} thành viên` : 'Không thể gửi tin. Kiểm tra thành viên đã chặn.';
    $('manageGroup').hidden = peer.kind !== 'group'; $('toggleBlock').hidden = peer.kind === 'group'; $('deleteChatContact').hidden = peer.kind === 'group';
    fillAvatar($('peerAvatar'), peer);
    $('toggleBlock').textContent = peer.blocked_by_me ? 'Bỏ chặn người này' : 'Chặn người này';
    input.disabled = !peer.can_send;
    $('chatSend').disabled = sending || !peer.can_send || (!input.value.trim() && !(editing ? editing.attachment : stagedFile));
  }
  function renderThreads(force = false) {
    const query = normalize($('chatSearch').value.trim());
    const signature = JSON.stringify([threads, query, selected]);
    if (!force && signature === lastList) return;
    lastList = signature;
    const list = $('threadList'); list.replaceChildren();
    const filtered = threads.filter(thread => normalize(thread.peer.name).includes(query));
    $('chatTotal').textContent = threads.length;
    for (const thread of filtered) {
      const button = el('button', 'chat-thread' + (thread.id === selected ? ' selected' : '') + (thread.unread ? ' unread' : ''));
      button.type = 'button'; button.setAttribute('aria-pressed', String(thread.id === selected));
      button.append(avatar(thread.peer));
      const copy = el('div', 'chat-thread-copy'); copy.append(el('strong', '', thread.peer.name));
      copy.append(el('p', '', thread.last ? (thread.last.sender_id === me ? 'Bạn: ' : '') + summary(thread.last) : 'Bắt đầu cuộc trò chuyện'));
      const meta = el('div', 'chat-thread-meta');
      if (thread.last) {
        const date = new Date(thread.last.created_at), today = new Date();
        const time = el('time', '', date.toDateString() === today.toDateString() ? timeLabel(thread.last.created_at) : date.toLocaleDateString('vi-VN', {day:'numeric',month:'numeric'}));
        time.dateTime = thread.last.created_at; meta.append(time);
      }
      if (thread.unread) { const unread = el('span', 'chat-unread', thread.unread > 99 ? '99+' : thread.unread); unread.setAttribute('aria-label', `${thread.unread} tin chưa đọc`); meta.append(unread); }
      button.append(copy, meta); button.addEventListener('click', () => selectThread(thread.id)); list.append(button);
    }
    if (!filtered.length) list.append(el('p', 'chat-list-empty', query ? 'Không tìm thấy cuộc trò chuyện.' : 'Chưa có cuộc trò chuyện. Bấm nút soạn để nhắn tin mới.'));
  }
  async function refreshOverview() {
    if (overviewBusy || embeddedPaused) return;
    overviewBusy = true;
    try {
      const data = await api('overview'); threads = data.threads; contacts = data.contacts; blockedPeople = data.blocked || [];
      if ($('blockedDialog').open) renderBlocked();
      renderThreads();
      const thread = threads.find(item => item.id === selected); if (thread) { updatePeer(thread.peer); updateContext(); }
      if (dialog.open && !$('contactSearch').value) renderContacts();
    } catch (err) { if (selected) error(err.message); else if (!threads.length) $('threadList').textContent = err.message; }
    finally { overviewBusy = false; }
  }
  function iconButton(icon, label, action) {
    const button = el('button', 'chat-message-action'); button.type = 'button'; button.title = label; button.setAttribute('aria-label', label);
    button.append(el('span', 'material-symbols-outlined', icon)); button.addEventListener('click', action); return button;
  }
  function setReply(message) {
    if (editing) cancelEdit();
    replyTarget = message; updateContext(); input.focus();
  }
  function updateContext() {
    $('composeContext').hidden = !replyTarget && !editing;
    $('composeContextTitle').textContent = editing ? 'Chỉnh sửa tin nhắn' : (replyTarget?.sender_id === me ? 'Trả lời chính bạn' : 'Trả lời ' + (replyTarget?.sender_name || $('peerName').textContent));
    $('composeContextBody').textContent = editing ? 'Lưu thay đổi hoặc bấm × để hủy.' : replyTarget ? summary(replyTarget) : '';
    $('attachFile').disabled = Boolean(editing) || input.disabled;
    $('openChatCamera').disabled = Boolean(editing) || input.disabled;
    $('stagedFile').hidden = !stagedFile || Boolean(editing);
    $('chatSend').setAttribute('aria-label', editing ? 'Lưu chỉnh sửa' : 'Gửi tin nhắn');
    $('chatSend').querySelector('span').textContent = editing ? 'check' : 'send';
  }
  function startEdit(message) {
    if (editing) cancelEdit();
    editDraft = input.value; editing = message; input.value = message.body; replyTarget = null;
    updateContext(); resizeInput(); input.focus();
  }
  function cancelEdit() {
    if (editing) { editing = null; input.value = editDraft; editDraft = ''; }
    updateContext(); resizeInput();
  }
  function setFile(file) {
    stagedFile = file; $('chatFile').value = '';
    if (previewUrl) { URL.revokeObjectURL(previewUrl); previewUrl = null; }
    $('stagedFile').hidden = !file;
    $('stagedImage').hidden = true; $('stagedFileIcon').hidden = false;
    if (file) {
      $('stagedFileName').textContent = file.name; $('stagedFileSize').textContent = fileSize(file.size);
      if (file.type.startsWith('image/')) { previewUrl = URL.createObjectURL(file); $('stagedImage').src = previewUrl; $('stagedImage').hidden = false; $('stagedFileIcon').hidden = true; }
    }
    resizeInput();
  }
  async function applyAction(message, action, values = {}) {
    const version = generation;
    try {
      const data = await api(`messages/${message.id}/${action}`, values);
      if (version !== generation) return;
      updateMessages([data.message]);
      refreshOverview();
    } catch (err) { if (version === generation) { sendError = true; error(err.message); } }
  }
  function readLabel(id) {
    if (currentPeer?.kind === 'group') { const count = groupReads.filter(row => row.last_read >= id).length; return count ? `${count} người đã xem` : 'Đã gửi'; }
    return id <= peerRead ? 'Đã xem' : 'Đã gửi';
  }
  function messageNode(message) {
    const mine = message.sender_id === me;
    const row = el('div', 'chat-message' + (mine ? ' mine' : '') + (message.deleted ? ' recalled' : '')); row.dataset.messageId = message.id;
    if (currentPeer?.kind === 'group' && !mine) { row.classList.add('has-sender'); row.append(el('strong','chat-sender-name',message.sender_name)); }
    const bubble = el('div', 'chat-bubble');
    if (message.reply) {
      const quote = el('button', 'chat-reply-quote'); quote.type = 'button';
      quote.append(el('strong', '', message.reply.sender_id === me ? 'Bạn' : (message.reply.sender_name || $('peerName').textContent)), el('span', '', message.reply.body));
      quote.addEventListener('click', () => jumpToMessage(message.reply.id)); bubble.append(quote);
    }
    if (message.deleted) bubble.append(el('span', '', 'Tin nhắn đã thu hồi'));
    else {
      if (message.attachment) {
        const file = message.attachment;
        const link = el('a', file.image ? 'chat-image-link' : 'chat-file-link'); link.href = file.url; link.target = '_blank'; link.rel = 'noopener';
        if (file.image) { const image = el('img', 'chat-image'); image.src = file.url; image.alt = file.filename; image.loading = 'lazy'; image.addEventListener('load', () => { if (pinned()) stream.scrollTop = stream.scrollHeight; }); link.append(image); }
        else { link.append(el('span', 'material-symbols-outlined', 'description')); const text = el('span', ''); text.append(el('strong', '', file.filename), el('small', '', fileSize(file.size) + ' · Tải xuống')); link.append(text); }
        bubble.append(link);
      }
      if (message.body) bubble.append(el('span', 'chat-message-text', message.body));
    }
    row.append(bubble);
    if (message.reactions?.length && !message.deleted) {
      const reactions = el('div', 'chat-reactions');
      message.reactions.forEach(reaction => {
        const button = el('button', 'chat-reaction' + (reaction.mine ? ' mine' : ''), reaction.emoji + ' ' + reaction.count);
        button.type = 'button'; button.title = reaction.mine ? 'Bỏ cảm xúc của bạn' : 'Thả cảm xúc'; button.setAttribute('aria-pressed', String(reaction.mine));
        button.addEventListener('click', () => applyAction(message, 'react', {emoji:reaction.mine ? '' : reaction.emoji})); reactions.append(button);
      }); row.append(reactions);
    }
    const meta = el('div', 'chat-message-meta'); const time = el('time', '', timeLabel(message.created_at)); time.dateTime = message.created_at;
    meta.append(time);
    if (message.edited_at && !message.deleted) meta.append(el('span', '', 'Đã chỉnh sửa'));
    if (mine) { const read = el('span', 'read-state', readLabel(message.id)); read.dataset.readId = message.id; meta.append(read); }
    row.append(meta);
    if (!message.deleted) {
      const tools = el('div', 'chat-message-tools');
      tools.append(iconButton('reply', 'Trả lời', () => setReply(message)));
      const reactionsMenu = el('details', 'chat-action-menu');
      const trigger = el('summary', 'chat-message-action'); trigger.setAttribute('aria-label', 'Thả cảm xúc'); trigger.title = 'Thả cảm xúc'; trigger.append(el('span', 'material-symbols-outlined', 'add_reaction'));
      const choices = el('div', 'chat-reaction-choices');
      ['👍','❤️','😂','😮','😢','🙏'].forEach(emoji => { const button = el('button', '', emoji); button.type = 'button'; button.setAttribute('aria-label', emoji); button.addEventListener('click', () => { reactionsMenu.open = false; applyAction(message, 'react', {emoji}); }); choices.append(button); });
      reactionsMenu.append(trigger, choices); tools.append(reactionsMenu);
      if (mine) {
        const menu = el('details', 'chat-action-menu'); const more = el('summary', 'chat-message-action'); more.title = 'Thao tác khác'; more.setAttribute('aria-label', 'Thao tác tin nhắn'); more.append(el('span', 'material-symbols-outlined', 'more_horiz'));
        const options = el('div', 'chat-more-options');
        if (Date.now() - new Date(message.created_at).getTime() <= 15*60*1000) {
          const edit = el('button', '', 'Chỉnh sửa'); edit.type = 'button'; edit.addEventListener('click', () => { menu.open = false; startEdit(message); }); options.append(edit);
        }
        const recall = el('button', 'chat-recall-option', 'Thu hồi với mọi người'); recall.type = 'button'; recall.addEventListener('click', () => { menu.open = false; recalling = message; $('recallDialog').showModal(); }); options.append(recall);
        menu.append(more, options); tools.append(menu);
      }
      row.append(tools);
    }
    return row;
  }
  function updateMessages(updates) {
    updates.forEach(message => {
      $('messageSearchResults').querySelectorAll(`[data-search-message-id="${message.id}"]`).forEach(result => {
        if (message.deleted) result.remove(); else result.querySelector('span').textContent = summary(message);
      });
      const index = records.findIndex(item => item.id === message.id);
      if (index !== -1) {
        records[index] = message;
        const old = $('messageList').querySelector(`[data-message-id="${message.id}"]`);
        if (old) old.replaceWith(messageNode(message));
      }
      records.forEach(item => {
        if (item.reply?.id !== message.id) return;
        item.reply.body = summary(message).slice(0,200); item.reply.deleted = message.deleted;
        const old = $('messageList').querySelector(`[data-message-id="${item.id}"]`); if (old) old.replaceWith(messageNode(item));
      });
      if (replyTarget?.id === message.id) { replyTarget = message.deleted ? null : message; updateContext(); }
      if (editing?.id === message.id && message.deleted) cancelEdit();
    });
  }
  async function jumpToMessage(id) {
    const version = generation;
    let row = $('messageList').querySelector(`[data-message-id="${id}"]`);
    if (!row) {
      try {
        const data = await api(`threads/${selected}?around=${id}&changes=${changeCursor}`);
        if (version !== generation) return;
        peerRead = data.peer_read; appendMessages(data.messages, true); updateMessages(data.updates);
        changeCursor = data.changes; $('loadOlder').hidden = !data.has_older;
        row = $('messageList').querySelector(`[data-message-id="${id}"]`);
      } catch (err) { error(err.message); return; }
    }
    if (row) { row.scrollIntoView({block:'center', behavior:'smooth'}); row.classList.add('chat-highlight'); setTimeout(() => row.classList.remove('chat-highlight'), 2000); }
  }
  function appendMessages(rows, replace = false) {
    const list = $('messageList');
    if (replace) { list.replaceChildren(); records = []; }
    for (const row of rows) {
      if (records.some(item => item.id === row.id)) { updateMessages([row]); continue; }
      const previous = records[records.length - 1];
      if (!previous || dateLabel(previous.created_at) !== dateLabel(row.created_at)) list.append(el('div', 'chat-date-divider', dateLabel(row.created_at)));
      records.push(row); list.append(messageNode(row));
    }
    $('chatEmpty').hidden = records.length > 0;
    list.querySelectorAll('[data-read-id]').forEach(node => { node.textContent = readLabel(Number(node.dataset.readId)); });
  }
  function saveDraft() { if (selected && !editing) { try { sessionStorage.setItem(`chat-draft-${me}-${selected}`, input.value); } catch (_) {} } }
  function resizeInput() { input.style.height = 'auto'; input.style.height = Math.min(input.scrollHeight, 140) + 'px'; $('chatCharCount').textContent = `${input.value.length.toLocaleString('vi-VN')} / 4.000`; $('chatSend').disabled = sending || input.disabled || (!input.value.trim() && !(editing ? editing.attachment : stagedFile)); }
  async function selectThread(id) {
    if (editing) cancelEdit();
    if (selected) composeStates.set(selected, {file:stagedFile, reply:replyTarget});
    saveDraft(); selected = id; generation++; fetching = false; sendError = false; records = []; readThrough = 0; acknowledged = 0; peerRead = 0; changeCursor = 0; replyTarget = composeStates.get(id)?.reply || null; setFile(composeStates.get(id)?.file || null); updateContext();
    $('messageSearchPanel').hidden = true; $('messageSearchToggle').setAttribute('aria-expanded', 'false'); searchVersion++;
    root.classList.add('has-thread'); $('chatWelcome').hidden = true; $('chatActive').hidden = false;
    $('messageList').replaceChildren(); $('chatEmpty').hidden = true; $('loadOlder').hidden = true; $('chatTyping').textContent = ''; error('');
    try { input.value = sessionStorage.getItem(`chat-draft-${me}-${id}`) || ''; } catch (_) { input.value = ''; }
    const thread = threads.find(item => item.id === id); if (thread) updatePeer(thread.peer);
    resizeInput(); renderThreads();
    history.replaceState(null, '', '/messenger?' + (isEmbedded ? 'embed=1&' : '') + 'thread=' + id);
    if (isEmbedded) { try { sessionStorage.setItem(widgetThreadKey, String(id)); } catch (_) {} }
    await pollMessages(true);
  }
  async function markRead() {
    if (embeddedPaused || !selected || !records.length || document.hidden || dialog.open || $('recallDialog').open || $('blockedDialog').open || $('deleteContactDialog').open || $('chatCameraDialog').open || $('createGroupDialog').open || $('groupInfoDialog').open || !document.hasFocus() || !pinned()) return;
    const last = records[records.length - 1].id;
    if (last <= readThrough) return;
    const id = selected, version = generation; readThrough = last;
    try {
      await api(`threads/${id}/read`, {message_id:last});
      if (version !== generation) return;
      acknowledged = last;
      const thread = threads.find(item => item.id === id); if (thread) { thread.unread = 0; renderThreads(); }
    } catch (_) { if (version === generation) readThrough = acknowledged; }
  }
  async function pollMessages(initial = false) {
    if (embeddedPaused || !selected || (fetching && !initial)) return;
    const id = selected, version = generation; fetching = true;
    const after = initial ? 0 : records.at(-1)?.id || 0;
    try {
      const data = await api(`threads/${id}?after=${after}&changes=${changeCursor}`);
      if (version !== generation) return;
      const bottom = initial || pinned(); peerRead = data.peer_read; groupReads = data.group_reads || []; updatePeer(data.peer);
      appendMessages(data.messages, initial); updateMessages(data.updates); changeCursor = data.changes;
      updatePeer(data.peer); updateContext(); $('chatTyping').textContent = data.typing ? `${data.typing_names?.length ? data.typing_names.slice(0,2).join(', ') : data.peer.name} đang nhập…` : '';
      if (initial) $('loadOlder').hidden = !data.has_older;
      if (bottom) stream.scrollTop = stream.scrollHeight;
      if (!sending && !sendError) error('');
      markRead();
    } catch (err) { if (version === generation) { if (currentPeer?.kind === 'group' && err.status === 404) { exitGroupConversation(); refreshOverview(); } else error(err.message); } }
    finally { if (version === generation) fetching = false; }
  }
  $('loadOlder').addEventListener('click', async () => {
    if (!records.length) return;
    const version = generation, id = selected, height = stream.scrollHeight, top = stream.scrollTop;
    $('loadOlder').disabled = true;
    try {
      const data = await api(`threads/${id}?before=${records[0].id}`);
      if (generation !== version) return;
      appendMessages([...data.messages, ...records], true);
      $('loadOlder').hidden = !data.has_older;
      stream.scrollTop = top + stream.scrollHeight - height;
    } catch (err) { error(err.message); }
    finally { $('loadOlder').disabled = false; }
  });
  function renderContacts() {
    const query = normalize($('contactSearch').value.trim());
    const list = $('contactList'); list.replaceChildren();
    contacts.filter(person => normalize(person.name + ' ' + person.role).includes(query)).forEach(person => {
      const button = el('button', 'chat-contact'); button.type = 'button'; button.append(avatar(person));
      const copy = el('div', 'chat-contact-copy'); copy.append(el('strong', '', person.name), el('small', '', person.role + (person.online ? ' · Đang hoạt động' : '')));
      button.append(copy, el('span', 'material-symbols-outlined', 'chevron_right'));
      button.addEventListener('click', async () => {
        button.disabled = true; $('contactError').hidden = true;
        try { const data = await api('threads', {user_id:person.id}); await refreshOverview(); dialog.close(); await selectThread(data.id); }
        catch (err) { $('contactError').textContent = err.message; $('contactError').hidden = false; }
        finally { button.disabled = false; }
      }); list.append(button);
    });
    if (!list.childElementCount) list.append(el('p', 'chat-list-empty', isAdmin ? 'Không có tài khoản phù hợp.' : 'Chưa có bạn bè phù hợp. Nhập đúng email ở trên để thêm bạn.'));
  }
  function openContacts() { $('contactSearch').value = ''; $('contactError').hidden = true; $('contactError').classList.remove('chat-contact-success'); renderContacts(); dialog.showModal(); $('contactSearch').focus(); refreshOverview(); }
  $('newChat').addEventListener('click', openContacts); $('welcomeNewChat').addEventListener('click', openContacts);
  function exitGroupConversation() {
    if (selected) { composeStates.delete(selected); try { sessionStorage.removeItem(`chat-draft-${me}-${selected}`); } catch (_) {} }
    generation++; selected = null; currentPeer = null; fetching = false; records = []; editing = null; replyTarget = null; input.value = ''; setFile(null);
    $('messageList').replaceChildren(); chatCamera.close(); if ($('groupInfoDialog').open) $('groupInfoDialog').close();
    root.classList.remove('has-thread'); $('chatActive').hidden = true; $('chatWelcome').hidden = false;
    history.replaceState(null, '', '/messenger' + (isEmbedded ? '?embed=1' : ''));
    if (isEmbedded) { try { sessionStorage.removeItem(widgetThreadKey); } catch (_) {} }
  }
  function renderGroupPicker() {
    const list = $('groupContactList'); list.replaceChildren(); const query = normalize($('groupContactSearch').value.trim());
    contacts.filter(peer => peer.can_send && normalize(peer.name).includes(query)).forEach(peer => {
      const label = el('label', 'chat-group-pick'); const check = el('input'); check.type = 'checkbox'; check.checked = pickedGroupMembers.has(peer.id);
      check.addEventListener('change', () => { if (check.checked) pickedGroupMembers.add(peer.id); else pickedGroupMembers.delete(peer.id); updateGroupCount(); });
      label.append(check, avatar(peer), el('strong','',peer.name)); list.append(label);
    });
    if (!list.childElementCount) list.append(el('p','chat-list-empty','Không có người phù hợp. Bạn cần thêm bạn bè bằng email trước.'));
    updateGroupCount();
  }
  function updateGroupCount() { $('groupPickCount').textContent = `${pickedGroupMembers.size} người được chọn · tối thiểu 1, tối đa 49`; $('submitCreateGroup').disabled = pickedGroupMembers.size < 1 || pickedGroupMembers.size > 49; }
  $('newGroup').addEventListener('click', async () => {
    pickedGroupMembers.clear(); $('newGroupName').value = ''; $('groupContactSearch').value = ''; $('createGroupError').hidden = true;
    renderGroupPicker(); $('createGroupDialog').showModal(); $('newGroupName').focus(); await refreshOverview(); renderGroupPicker();
  });
  $('closeCreateGroup').addEventListener('click', () => $('createGroupDialog').close());
  $('groupContactSearch').addEventListener('input', renderGroupPicker);
  $('createGroupForm').addEventListener('submit', async event => {
    event.preventDefault(); $('submitCreateGroup').disabled = true; $('createGroupError').hidden = true;
    try {
      const data = await api('groups',{name:$('newGroupName').value.trim(),member_ids:[...pickedGroupMembers].join(',')});
      $('createGroupDialog').close(); await refreshOverview(); await selectThread(data.id);
    } catch (err) { $('createGroupError').textContent = err.message; $('createGroupError').hidden = false; }
    finally { updateGroupCount(); }
  });
  async function loadGroupInfo() {
    if (!selected || currentPeer?.kind !== 'group') return;
    const id = selected, data = await api(`threads/${id}/group`); if (selected !== id) return;
    groupInfo = data; groupInfoThread = id;
    $('groupInfoTitle').textContent = data.name; $('groupInfoDescription').textContent = `${data.members.length} thành viên · ${data.owner ? 'Bạn là trưởng nhóm' : 'Bạn là thành viên'}`;
    $('groupOwnerTools').hidden = !data.owner; $('renameGroupName').value = data.name;
    const invite = $('inviteGroupMember'); invite.replaceChildren(el('option','','Chọn người để thêm…')); invite.firstChild.value = '';
    contacts.filter(peer => peer.can_send && !data.members.some(member => member.id === peer.id)).forEach(peer => { const option = el('option','',peer.name); option.value = peer.id; invite.append(option); });
    const list = $('groupMemberList'); list.replaceChildren();
    data.members.forEach(member => {
      const row = el('div','chat-group-member'); row.append(avatar({...member,online:false}));
      const copy = el('div'); copy.append(el('strong','',member.name + (member.id === me ? ' (Bạn)' : '')),el('small','',member.owner ? 'Trưởng nhóm' : (member.active ? 'Thành viên' : 'Tài khoản đang khóa'))); row.append(copy);
      if (data.owner && member.id !== me) {
        const actions = el('div','chat-group-member-actions');
        if (member.active) { const transfer = el('button','','Chuyển quyền'); transfer.type = 'button'; transfer.addEventListener('click', () => { if (transfer.dataset.confirm !== '1') { transfer.dataset.confirm='1';transfer.textContent='Xác nhận chuyển';return; } groupAction('transfer',{user_id:member.id}); }); actions.append(transfer); }
        const remove = el('button','','Xóa'); remove.type = 'button'; remove.addEventListener('click', () => { if (remove.dataset.confirm !== '1') { remove.dataset.confirm='1';remove.textContent='Xác nhận xóa';return; } groupAction('remove',{user_id:member.id}); }); actions.append(remove); row.append(actions);
      }
      list.append(row);
    });
  }
  async function groupAction(action, values={}) {
    const id = groupInfoThread; $('groupInfoError').hidden = true;
    try {
      const data = await api(`threads/${id}/group`,{action,...values});
      if (selected !== id) return;
      if (data.left) { exitGroupConversation(); await refreshOverview(); }
      else { await refreshOverview(); await loadGroupInfo(); }
    } catch (err) { $('groupInfoError').textContent = err.message; $('groupInfoError').hidden = false; }
  }
  $('manageGroup').addEventListener('click', async () => {
    document.querySelector('.chat-peer-menu').open = false; $('groupInfoError').hidden = true; $('groupLeaveConfirm').hidden = true; $('groupMemberList').replaceChildren();
    $('groupInfoDialog').showModal(); try { await loadGroupInfo(); } catch (err) { $('groupInfoError').textContent=err.message; $('groupInfoError').hidden=false; }
  });
  $('closeGroupInfo').addEventListener('click', () => $('groupInfoDialog').close());
  $('renameGroupForm').addEventListener('submit', event => { event.preventDefault(); groupAction('rename',{name:$('renameGroupName').value.trim()}); });
  $('addGroupMemberForm').addEventListener('submit', event => { event.preventDefault(); groupAction('add',{user_id:$('inviteGroupMember').value}); });
  $('leaveGroup').addEventListener('click', () => { $('groupLeaveConfirm').hidden = false; });
  $('cancelLeaveGroup').addEventListener('click', () => { $('groupLeaveConfirm').hidden = true; });
  $('confirmLeaveGroup').addEventListener('click', () => groupAction('leave'));
  $('addContactForm').addEventListener('submit', async event => {
    event.preventDefault(); $('addContactSubmit').disabled = true; $('contactError').hidden = true;
    $('contactError').classList.remove('chat-contact-success');
    try {
      const data = await api('contacts/add', {email:$('contactEmail').value.trim()});
      await refreshOverview(); $('contactSearch').value = ''; renderContacts();
      $('contactEmail').value = ''; $('contactError').textContent = 'Đã thêm ' + data.peer.name + '. Chọn người này bên dưới để nhắn tin.';
      $('contactError').classList.add('chat-contact-success'); $('contactError').hidden = false;
    } catch (err) { $('contactError').textContent = err.message; $('contactError').hidden = false; }
    finally { $('addContactSubmit').disabled = false; }
  });
  async function changeBlock(peer, shouldBlock) {
    try {
      await api(`contacts/${peer.id}/block`, {blocked:shouldBlock ? '1' : '0'});
      await refreshOverview(); if (selected) await pollMessages();
    } catch (err) { sendError = true; error(err.message); }
  }
  $('toggleBlock').addEventListener('click', () => { if (!currentPeer) return; document.querySelector('.chat-peer-menu').open = false; changeBlock(currentPeer, !currentPeer.blocked_by_me); });
  function renderBlocked() {
    const list = $('blockedList'); list.replaceChildren();
    blockedPeople.forEach(peer => {
      const row = el('div', 'chat-blocked-row'); row.append(avatar(peer), el('strong', '', peer.name));
      const button = el('button', 'btn btn-sm', 'Bỏ chặn'); button.type = 'button'; button.addEventListener('click', async () => { button.disabled = true; await changeBlock(peer, false); button.disabled = false; }); row.append(button); list.append(row);
    });
    if (!blockedPeople.length) list.append(el('p', 'chat-list-empty', 'Bạn chưa chặn người nào.'));
  }
  $('openBlocked').addEventListener('click', () => { renderBlocked(); $('blockedDialog').showModal(); refreshOverview(); });
  $('closeBlocked').addEventListener('click', () => $('blockedDialog').close());
  $('deleteChatContact').addEventListener('click', () => { deletingThread = selected; document.querySelector('.chat-peer-menu').open = false; $('deleteContactDialog').showModal(); });
  $('cancelDeleteContact').addEventListener('click', () => { deletingThread = null; $('deleteContactDialog').close(); });
  $('confirmDeleteContact').addEventListener('click', async () => {
    const id = deletingThread; if (!id) return; $('confirmDeleteContact').disabled = true;
    try {
      await api(`threads/${id}/remove-contact`, {});
      composeStates.delete(id); try { sessionStorage.removeItem(`chat-draft-${me}-${id}`); } catch (_) {}
      if (selected === id) {
        generation++; selected = null; currentPeer = null; fetching = false; records = []; editing = null; replyTarget = null; input.value = ''; setFile(null);
        root.classList.remove('has-thread'); $('chatActive').hidden = true; $('chatWelcome').hidden = false; history.replaceState(null, '', '/messenger' + (isEmbedded ? '?embed=1' : '')); if (isEmbedded) { try { sessionStorage.removeItem(widgetThreadKey); } catch (_) {} }
      }
      deletingThread = null; $('deleteContactDialog').close(); await refreshOverview();
    } catch (err) { $('deleteContactDialog').close(); error(err.message); }
    finally { $('confirmDeleteContact').disabled = false; }
  });
  $('closeContacts').addEventListener('click', () => dialog.close());
  $('contactSearch').addEventListener('input', renderContacts); $('chatSearch').addEventListener('input', () => renderThreads(true));
  $('chatBack').addEventListener('click', () => { if (editing) cancelEdit(); composeStates.set(selected, {file:stagedFile, reply:replyTarget}); saveDraft(); generation++; selected = null; fetching = false; root.classList.remove('has-thread'); $('chatActive').hidden = true; $('chatWelcome').hidden = false; history.replaceState(null, '', '/messenger' + (isEmbedded ? '?embed=1' : '')); if (isEmbedded) { try { sessionStorage.removeItem(widgetThreadKey); } catch (_) {} } renderThreads(); });
  async function typing(active) { if (!selected) return; try { await api(`threads/${selected}/typing`, {typing:active ? '1' : '0'}); } catch (_) {} }
  input.addEventListener('input', () => {
    resizeInput(); saveDraft();
    if (Date.now() - lastTyping > 3000) { lastTyping = Date.now(); typing(Boolean(input.value.trim())); }
    clearTimeout(typingTimer); typingTimer = setTimeout(() => typing(false), 1800);
  });
  input.addEventListener('keydown', event => { if (event.key === 'Enter' && !event.shiftKey && !event.isComposing) { event.preventDefault(); if (!sending && (input.value.trim() || (editing ? editing.attachment : stagedFile))) $('chatSendForm').requestSubmit(); } });
  $('chatSendForm').addEventListener('submit', async event => {
    event.preventDefault(); const body = input.value.trim(); if (!selected || sending || (!body && !stagedFile && !editing?.attachment)) return;
    if (input.disabled) return;
    const id = selected, version = generation, file = stagedFile, replyId = replyTarget?.id, editedMessage = editing;
    const clientId = retry?.body === body && retry?.thread === id && retry?.file === file && retry?.reply === replyId ? retry.id : Array.from(crypto.getRandomValues(new Uint8Array(16)), byte => byte.toString(16).padStart(2, '0')).join('');
    retry = {body, thread:id, id:clientId, file, reply:replyId}; sending = true; sendError = false; resizeInput(); error('');
    try {
      let data;
      if (editedMessage) data = await api(`messages/${editedMessage.id}/edit`, {body});
      else {
        const payload = new FormData(); payload.set('body', body); payload.set('client_id', clientId);
        if (file) payload.set('attachment', file); if (replyId) payload.set('reply_id', replyId);
        data = await api(`threads/${id}/send`, payload);
      }
      retry = null;
      if (version === generation) {
        if (editedMessage) { updateMessages([data.message]); cancelEdit(); }
        else {
          if (input.value.trim() === body) { input.value = ''; saveDraft(); }
          if (stagedFile === file) setFile(null); replyTarget = null; updateContext();
          await pollMessages(); stream.scrollTop = stream.scrollHeight; markRead();
        }
        resizeInput(); input.focus();
      } else if (!editedMessage) {
        composeStates.delete(id);
        try { if (sessionStorage.getItem(`chat-draft-${me}-${id}`)?.trim() === body) sessionStorage.removeItem(`chat-draft-${me}-${id}`); } catch (_) {}
      }
      await refreshOverview();
    } catch (err) { if (version === generation) { sendError = true; error(err.message + ' Nội dung vẫn được giữ để bạn gửi lại.'); } }
    finally { sending = false; resizeInput(); }
  });
  $('cancelContext').addEventListener('click', () => { if (editing) cancelEdit(); else { replyTarget = null; updateContext(); } });
  const chatCamera = new window.LibraryChatCamera({
    context: () => ({id:selected, allowed:Boolean(selected && !editing && currentPeer?.can_send)}),
    onPhoto: (file, threadId) => {
      if (selected !== threadId || editing || !currentPeer?.can_send) { error('Cuộc trò chuyện đã thay đổi hoặc không thể gửi ảnh. Vui lòng chụp lại trong cuộc trò chuyện cần gửi.'); return; }
      setFile(file); error(''); input.focus();
    }
  });
  $('attachFile').addEventListener('click', () => $('chatFile').click());
  $('chatFile').addEventListener('change', () => {
    const file = $('chatFile').files[0]; if (!file) return;
    const image = /\.(jpe?g|png|webp)$/i.test(file.name);
    if (!/\.(jpe?g|png|webp|pdf|txt)$/i.test(file.name)) { error('Chọn ảnh JPG, PNG, WebP hoặc tệp PDF, TXT.'); $('chatFile').value=''; return; }
    if (file.size > (image ? 5 : 10)*1024*1024) { error(image ? 'Ảnh tối đa 5 MB.' : 'Tệp tối đa 10 MB.'); $('chatFile').value=''; return; }
    setFile(file); error('');
  });
  $('removeFile').addEventListener('click', () => setFile(null));
  $('cancelRecall').addEventListener('click', () => { recalling = null; $('recallDialog').close(); });
  $('confirmRecall').addEventListener('click', async () => { if (!recalling) return; const message = recalling; recalling = null; $('recallDialog').close(); await applyAction(message, 'recall'); });
  let searchTimer;
  async function searchMessages(more = false) {
    const query = $('messageSearchInput').value.trim(), version = ++searchVersion, thread = selected;
    if (!more) { searchBefore = null; $('messageSearchResults').replaceChildren(); }
    $('searchMore').hidden = true;
    if (!query || !thread) return;
    try {
      const data = await api(`threads/${thread}/search?q=${encodeURIComponent(query)}${more && searchBefore ? '&before='+searchBefore : ''}`);
      if (version !== searchVersion || thread !== selected) return;
      for (const message of data.messages) {
        const button = el('button', 'chat-search-result'); button.type = 'button'; button.dataset.searchMessageId = message.id;
        button.append(el('strong', '', message.sender_id === me ? 'Bạn' : (message.sender_name || $('peerName').textContent)), el('span', '', summary(message)), el('small', '', dateLabel(message.created_at) + ' · ' + timeLabel(message.created_at)));
        button.addEventListener('click', () => jumpToMessage(message.id)); $('messageSearchResults').append(button);
      }
      searchBefore = data.messages.at(-1)?.id || searchBefore; $('searchMore').hidden = !data.has_more;
      if (!$('messageSearchResults').childElementCount) $('messageSearchResults').append(el('p', 'chat-list-empty', 'Không tìm thấy tin nhắn.'));
    } catch (err) { if (version === searchVersion) error(err.message); }
  }
  $('messageSearchToggle').addEventListener('click', () => { const show = $('messageSearchPanel').hidden; $('messageSearchPanel').hidden = !show; $('messageSearchToggle').setAttribute('aria-expanded', String(show)); if (show) { $('messageSearchInput').focus(); searchMessages(); } });
  $('messageSearchClose').addEventListener('click', () => { $('messageSearchPanel').hidden = true; $('messageSearchToggle').setAttribute('aria-expanded', 'false'); searchVersion++; });
  $('messageSearchInput').addEventListener('input', () => { clearTimeout(searchTimer); searchVersion++; searchTimer = setTimeout(() => searchMessages(), 300); });
  $('searchMore').addEventListener('click', () => searchMessages(true));
  $('emojiToggle').addEventListener('click', () => { $('emojiPicker').hidden = !$('emojiPicker').hidden; $('emojiToggle').setAttribute('aria-expanded', String(!$('emojiPicker').hidden)); });
  $('emojiPicker').querySelectorAll('[data-emoji]').forEach(button => button.addEventListener('click', () => {
    if (input.value.length + button.dataset.emoji.length > 4000) return;
    input.setRangeText(button.dataset.emoji, input.selectionStart, input.selectionEnd, 'end'); input.dispatchEvent(new Event('input')); input.focus();
    $('emojiPicker').hidden = true; $('emojiToggle').setAttribute('aria-expanded', 'false');
  }));
  document.addEventListener('click', event => { document.querySelectorAll('.chat-action-menu[open], .chat-peer-menu[open]').forEach(menu => { if (!menu.contains(event.target)) menu.open = false; }); if (!event.target.closest('.chat-emoji-wrap')) { $('emojiPicker').hidden = true; $('emojiToggle').setAttribute('aria-expanded', 'false'); } });
  stream.addEventListener('scroll', markRead);
  window.addEventListener('focus', () => { refreshOverview(); pollMessages(); markRead(); });
  document.addEventListener('visibilitychange', () => { if (!document.hidden && !embeddedPaused) { refreshOverview(); pollMessages(); } });
  setInterval(() => { if (!document.hidden && !embeddedPaused) { refreshOverview(); pollMessages(); } }, 2500);
  function initialConversation() {
    return refreshOverview().then(() => { const id = Number(new URLSearchParams(location.search).get('thread')); if (threads.some(item => item.id === id)) selectThread(id); });
  }
  if (isEmbedded) {
    window.addEventListener('message', event => {
      if (event.origin !== location.origin || event.source !== window.parent || event.data?.type !== 'library-chat-widget-visibility') return;
      embeddedPaused = event.data.open !== true;
      if (embeddedPaused) { chatCamera.close(); typing(false); }
      else if (!embeddedStarted) { embeddedStarted = true; initialConversation(); }
      else { refreshOverview(); pollMessages(); }
    });
    document.addEventListener('keydown', event => {
      if (event.key === 'Escape' && !document.querySelector('dialog[open]')) {
        window.parent.postMessage({type:'library-chat-widget-close'}, location.origin);
      }
    });
  } else initialConversation();
})();
