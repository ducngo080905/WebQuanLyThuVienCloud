(() => {
  const title = document.getElementById('messageTitle');
  const body = document.getElementById('messageBody');
  const audience = document.getElementById('audience');
  const target = document.getElementById('targetId');
  const update = () => {
    document.getElementById('titleCount').textContent = `${title.value.length} / 150`;
    document.getElementById('bodyCount').textContent = `${body.value.length.toLocaleString('vi-VN')} / 5.000`;
    document.getElementById('previewTitle').textContent = title.value.trim() || 'Tiêu đề thông báo';
    document.getElementById('previewBody').textContent = body.value.trim() || 'Nội dung bạn nhập sẽ xuất hiện tại đây.';
    const one = audience.value === 'one';
    document.getElementById('targetAccount').hidden = !one;
    target.required = one;
    const options = Array.from(target.options).filter(option => option.value);
    const count = one ? Number(Boolean(target.value)) : options.filter(option => audience.value === 'all' || option.dataset.role === audience.value).length;
    document.getElementById('recipientCount').textContent = `${count} tài khoản sẽ nhận thông báo`;
    document.getElementById('sendNotice').disabled = !count;
  };
  [title, body].forEach(field => field.addEventListener('input', update));
  [audience, target].forEach(field => field.addEventListener('change', update));
  update();
  const normalize = value => value.normalize('NFD').replace(/[\u0300-\u036f]/g, '').replace(/đ/g, 'd').replace(/Đ/g, 'D').toLowerCase();
  document.getElementById('noticeSearch').addEventListener('input', event => {
    const query = normalize(event.target.value.trim());
    const rows = Array.from(document.querySelectorAll('.notice-history-item'));
    rows.forEach(row => { row.hidden = !normalize(row.textContent).includes(query); });
    document.getElementById('noticeSearchEmpty').hidden = !rows.length || rows.some(row => !row.hidden);
  });
  document.querySelectorAll('.notice-history-meta time').forEach(time => {
    const date = new Date(time.dateTime);
    if (!Number.isNaN(date.valueOf())) time.textContent = new Intl.DateTimeFormat('vi-VN', {dateStyle: 'short', timeStyle: 'short', timeZone: 'Asia/Ho_Chi_Minh'}).format(date) + ' (VN)';
  });
})();
