(() => {
  const picker = document.getElementById('profileAvatar');
  const photo = document.getElementById('profilePhoto');
  const fallback = document.getElementById('profilePhotoFallback');
  const save = document.getElementById('saveAvatar');
  const status = document.getElementById('avatarStatus');
  if (!picker || !photo) return;
  const original = photo.getAttribute('src');
  let pendingUrl = null;
  function restore() {
    if (pendingUrl) { URL.revokeObjectURL(pendingUrl); pendingUrl = null; }
    photo.hidden = !original;
    if (original) photo.src = original; else photo.removeAttribute('src');
    if (fallback) fallback.hidden = Boolean(original);
    photo.parentElement.classList.remove('account-photo-preview');
  }
  function fail(message) {
    restore(); picker.value = ''; save.disabled = true;
    status.textContent = message; status.hidden = false; status.classList.add('account-avatar-error');
  }
  picker.addEventListener('change', () => {
    const file = picker.files[0]; restore(); save.disabled = true;
    status.hidden = true; status.classList.remove('account-avatar-error');
    if (!file) return;
    if (!/\.(jpe?g|png|webp)$/i.test(file.name)) return fail('Chọn ảnh JPG, PNG hoặc WebP.');
    if (file.size > 5*1024*1024) return fail('Ảnh đại diện tối đa 5 MB.');
    const url = URL.createObjectURL(file); pendingUrl = url;
    const check = new Image();
    check.onload = () => {
      if (pendingUrl !== url) return;
      if (check.naturalWidth * check.naturalHeight > 20000000) return fail('Chọn ảnh dưới 20 triệu điểm ảnh.');
      photo.src = url; photo.hidden = false; if (fallback) fallback.hidden = true;
      photo.parentElement.classList.add('account-photo-preview');
      status.textContent = 'Đang xem trước. Bấm “Lưu ảnh” để cập nhật.'; status.hidden = false; save.disabled = false;
    };
    check.onerror = () => { if (pendingUrl === url) fail('Ảnh không hợp lệ. Vui lòng chọn ảnh khác.'); };
    check.src = url;
  });
  window.addEventListener('pagehide', () => { if (pendingUrl) URL.revokeObjectURL(pendingUrl); });
  document.querySelectorAll('[data-password]').forEach(button => button.addEventListener('click', () => {
    const field = document.getElementById(button.dataset.password);
    const show = field.type === 'password'; field.type = show ? 'text' : 'password';
    button.setAttribute('aria-pressed', String(show));
    button.querySelector('span').textContent = show ? 'visibility_off' : 'visibility';
    button.setAttribute('aria-label', (show ? 'Ẩn ' : 'Hiện ') + field.labels[0].textContent.toLowerCase());
  }));
  const password = document.getElementById('password'), confirm = document.getElementById('confirm');
  if (password && confirm) {
    const validate = () => confirm.setCustomValidity(password.value !== confirm.value ? 'Mật khẩu xác nhận chưa khớp.' : '');
    password.addEventListener('input', validate); confirm.addEventListener('input', validate);
    document.getElementById('profileDetailsForm').addEventListener('invalid', () => { document.getElementById('passwordSection').open = true; }, true);
  }
})();
