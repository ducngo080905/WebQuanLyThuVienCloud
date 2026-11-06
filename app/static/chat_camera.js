(() => {
  class LibraryChatCamera {
    constructor({context, onPhoto}) {
      this.context = context; this.onPhoto = onPhoto; this.stream = null; this.token = 0; this.file = null; this.url = null; this.facing = 'environment';
      this.$ = id => document.getElementById(id);
      this.dialog = this.$('chatCameraDialog'); this.video = this.$('chatCameraVideo');
      this.$('openChatCamera').addEventListener('click', () => this.open());
      this.$('closeChatCamera').addEventListener('click', () => this.close());
      this.dialog.addEventListener('cancel', event => { event.preventDefault(); this.close(); });
      this.dialog.addEventListener('close', () => this.cleanup());
      this.video.addEventListener('loadeddata', () => this.ready());
      this.$('takeChatPhoto').addEventListener('click', () => this.capture());
      this.$('retakeChatPhoto').addEventListener('click', () => this.start());
      this.$('switchChatCamera').addEventListener('click', () => { this.facing = this.facing === 'environment' ? 'user' : 'environment'; this.start(); });
      this.$('useChatPhoto').addEventListener('click', () => {
        if (!this.file) return;
        const file = this.file, id = this.threadId; this.close(); this.onPhoto(file, id);
      });
      this.$('chatCameraFallback').addEventListener('click', () => {
        this.fallbackThread = this.threadId; this.close(); this.$('chatCameraFile').value = ''; this.$('chatCameraFile').click();
      });
      this.$('chatCameraFile').addEventListener('change', () => {
        const file = this.$('chatCameraFile').files[0]; if (!file) return;
        if (!/\.(jpe?g|png|webp)$/i.test(file.name) || file.size > 5*1024*1024) {
          this.dialog.showModal(); this.video.hidden = true; this.$('chatCameraPlaceholder').hidden = false;
          this.$('takeChatPhoto').hidden = true; this.$('useChatPhoto').hidden = true; this.$('switchChatCamera').hidden = true; this.$('retakeChatPhoto').hidden = false;
          this.status('Chọn ảnh JPG, PNG hoặc WebP tối đa 5 MB.', true); return;
        }
        this.onPhoto(file, this.fallbackThread);
      });
      document.addEventListener('visibilitychange', () => {
        if (document.hidden && this.dialog.open && !this.file) {
          this.cleanup(); this.status('Camera đã tắt khi bạn rời trang. Bấm Chụp lại để mở lại.');
          this.$('retakeChatPhoto').hidden = false;
        }
      });
      window.addEventListener('pagehide', () => this.close());
    }
    status(text, failed = false) { const node = this.$('chatCameraStatus'); node.textContent = text; node.classList.toggle('chat-camera-error', failed); }
    stop() {
      if (this.stream) this.stream.getTracks().forEach(track => track.stop());
      this.stream = null; this.video.pause(); this.video.srcObject = null;
      this.$('takeChatPhoto').disabled = true;
    }
    clearPhoto() {
      this.file = null;
      if (this.url) URL.revokeObjectURL(this.url);
      this.url = null; this.$('chatCameraPhoto').removeAttribute('src'); this.$('chatCameraPhoto').hidden = true;
    }
    cleanup() { this.token++; this.stop(); this.clearPhoto(); }
    close() { this.cleanup(); if (this.dialog.open) this.dialog.close(); }
    open() {
      const context = this.context(); if (!context.allowed) return;
      this.threadId = context.id; this.dialog.showModal(); this.start();
    }
    ready() {
      if (!this.stream || !this.dialog.open || !this.video.videoWidth || !this.video.videoHeight) return;
      this.$('takeChatPhoto').disabled = false; this.$('chatCameraPlaceholder').hidden = true;
      this.status('Căn khung hình rồi bấm Chụp ảnh.');
    }
    async start() {
      const token = ++this.token; this.stop(); this.clearPhoto();
      this.video.hidden = false; this.$('chatCameraPlaceholder').hidden = false;
      this.$('takeChatPhoto').hidden = false; this.$('useChatPhoto').hidden = true; this.$('retakeChatPhoto').hidden = true;
      this.$('switchChatCamera').hidden = false; this.$('switchChatCamera').disabled = true;
      this.status('Đang mở camera…');
      if (!window.isSecureContext || !navigator.mediaDevices?.getUserMedia) {
        this.status('Trình duyệt cần HTTPS hoặc localhost để mở camera. Bạn có thể chọn ảnh từ thiết bị bên dưới.', true);
        this.$('switchChatCamera').hidden = true; return;
      }
      try {
        const stream = await navigator.mediaDevices.getUserMedia({audio:false, video:{facingMode:{ideal:this.facing}, width:{ideal:1280}, height:{ideal:960}}});
        if (token !== this.token || !this.dialog.open) { stream.getTracks().forEach(track => track.stop()); return; }
        this.stream = stream; this.video.srcObject = stream; await this.video.play();
        if (token !== this.token) return;
        this.$('switchChatCamera').disabled = false; this.ready();
      } catch (error) {
        if (token !== this.token) return;
        this.stop();
        const reasons = {NotAllowedError:'Bạn chưa cho phép truy cập camera. Hãy bật quyền camera cho website rồi thử lại.', NotFoundError:'Không tìm thấy camera trên thiết bị này.', NotReadableError:'Camera đang được ứng dụng khác sử dụng hoặc không thể mở.', SecurityError:'Trình duyệt đang chặn truy cập camera.'};
        this.status(reasons[error.name] || 'Không mở được camera. Hãy thử lại hoặc chọn ảnh từ thiết bị.', true);
        this.$('retakeChatPhoto').hidden = false; this.$('switchChatCamera').hidden = true;
      }
    }
    async capture() {
      if (!this.stream || !this.video.videoWidth || !this.video.videoHeight) return;
      this.$('takeChatPhoto').disabled = true; const token = this.token;
      const canvas = document.createElement('canvas');
      const ratio = Math.min(1, 1600/Math.max(this.video.videoWidth, this.video.videoHeight));
      canvas.width = Math.max(1, Math.round(this.video.videoWidth*ratio)); canvas.height = Math.max(1, Math.round(this.video.videoHeight*ratio));
      try {
        canvas.getContext('2d').drawImage(this.video, 0, 0, canvas.width, canvas.height);
        const blob = await new Promise(resolve => canvas.toBlob(resolve, 'image/jpeg', 0.86));
        if (token !== this.token || !this.dialog.open) return;
        if (!blob || blob.size > 5*1024*1024) throw new Error('photo');
        this.file = new File([blob], 'anh-chup-'+new Date().toISOString().replace(/[:.]/g,'-')+'.jpg', {type:'image/jpeg'});
        this.url = URL.createObjectURL(this.file); this.$('chatCameraPhoto').src = this.url; this.$('chatCameraPhoto').hidden = false;
        this.stop(); this.video.hidden = true; this.$('chatCameraPlaceholder').hidden = true;
        this.$('takeChatPhoto').hidden = true; this.$('switchChatCamera').hidden = true;
        this.$('retakeChatPhoto').hidden = false; this.$('useChatPhoto').hidden = false;
        this.status('Kiểm tra ảnh. Chọn Dùng ảnh này để đưa vào khung chat.');
      } catch (_) { if (token === this.token) { this.$('takeChatPhoto').disabled = false; this.status('Chưa chụp được ảnh. Vui lòng thử lại.', true); } }
    }
  }
  window.LibraryChatCamera = LibraryChatCamera;
})();
