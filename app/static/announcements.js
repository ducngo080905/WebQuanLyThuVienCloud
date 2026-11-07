for (const form of document.querySelectorAll('[data-notice-form]')) {
  const { body, color } = form.elements;
  const preview = form.querySelector('output');

  function updatePreview() {
    preview.textContent = body.value.trim() || 'Nội dung sẽ xuất hiện ở đây.';
    preview.style.color = color.value;
  }

  form.addEventListener('input', updatePreview);
  updatePreview();
}

const editor = document.getElementById('noticeEdit');
const editForm = editor.querySelector('form');
const saveButton = editForm.querySelector('button[type="submit"], button:not([type])');
const cancelButton = editor.querySelector('[data-close-edit]');

document.addEventListener('click', event => {
  const link = event.target.closest('#noticeHistory [data-edit]');
  if (!link || event.ctrlKey || event.metaKey || event.shiftKey || event.altKey) return;
  event.preventDefault();
  editor.querySelector('[role="alert"]')?.remove();
  for (const [name, value] of Object.entries(JSON.parse(link.dataset.edit))) {
    editForm.elements.namedItem(name).value = value;
  }
  editForm.dispatchEvent(new Event('input'));
  editor.showModal();
});

editForm.addEventListener('submit', async event => {
  event.preventDefault();
  if (saveButton.disabled) return;
  editor.querySelector('[role="alert"]')?.remove();
  saveButton.disabled = cancelButton.disabled = true;
  try {
    const response = await fetch(editForm.action, {
      method: 'POST',
      body: new URLSearchParams(new FormData(editForm)),
    });
    const page = new DOMParser().parseFromString(await response.text(), 'text/html');
    const updatedHistory = page.getElementById('noticeHistory');
    const error = page.querySelector('#noticeEdit [role="alert"]');
    if (error || !response.ok || !response.redirected || !updatedHistory) {
      throw new Error(error?.textContent || 'Không lưu được thông báo. Vui lòng thử lại.');
    }
    editor.close();
    document.getElementById('noticeHistory').replaceChildren(...updatedHistory.childNodes);
  } catch (error) {
    const message = document.createElement('p');
    message.className = 'alert alert-danger';
    message.setAttribute('role', 'alert');
    message.textContent = error.message;
    editForm.prepend(message);
  } finally {
    saveButton.disabled = cancelButton.disabled = false;
  }
});

editor.addEventListener('cancel', event => {
  if (saveButton.disabled) event.preventDefault();
});
cancelButton.addEventListener('click', () => editor.close());
if (editor.hasAttribute('data-open')) editor.showModal();
