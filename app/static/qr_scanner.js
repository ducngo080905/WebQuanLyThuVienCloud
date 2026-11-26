(() => {
  const start=document.getElementById('startScan'),stop=document.getElementById('stopScan');
  if(!start||!window.Html5Qrcode)return;
  const status=document.getElementById('scanStatus'),file=document.getElementById('scanFile'),form=document.getElementById('scanForm');
  const dialog=document.getElementById('qrResultDialog'),content=document.getElementById('qrResultContent'),errorBox=document.getElementById('qrResultError');
  const scanner=new Html5Qrcode('qrReader',{formatsToSupport:[Html5QrcodeSupportedFormats.QR_CODE]},false);
  let running=false,starting=false,cancelled=false,submitted=false,resumeCamera=false,posting=false;
  let lastCode='',ignoreCode='',cooldown=0,noticeTimer,requestVersion=0;
  function error(message){errorBox.textContent=message;errorBox.hidden=!message;}
  async function shutdown(){
    cancelled=true;
    if(running){try{await scanner.stop();}catch(_){}running=false;}
    stop.disabled=true;start.disabled=starting;file.disabled=starting;
  }
  async function begin(){
    if(running||starting||dialog.open||submitted)return;
    if(!window.isSecureContext){status.textContent='Camera cần HTTPS hoặc localhost. Bạn vẫn có thể chọn ảnh QR.';return;}
    starting=true;cancelled=false;start.disabled=true;stop.disabled=false;file.disabled=true;
    status.textContent='Đang xin quyền camera…';
    try{
      await scanner.start({facingMode:'environment'},{fps:8,qrbox:(w,h)=>({width:Math.min(w,h,260)*.8,height:Math.min(w,h,260)*.8})},decoded,()=>{});
      running=true;
      if(cancelled||document.hidden)await shutdown();
      else status.textContent='Đưa QR thẻ độc giả hoặc QR trả sách vào khung.';
    }catch(_){status.textContent='Không mở được camera. Kiểm tra quyền truy cập hoặc chọn ảnh QR.';}
    finally{starting=false;start.disabled=running;stop.disabled=!running;file.disabled=running;}
  }
  async function jsonResponse(response){
    if(response.redirected||!response.headers.get('Content-Type')?.includes('application/json'))throw Error('Phiên đăng nhập đã thay đổi. Hãy mở lại trạm và đăng nhập.');
    const data=await response.json();
    if(!response.ok)throw Error(data.error||'Chưa xử lý được yêu cầu. Hãy thử lại.');
    return data;
  }
  async function showResult(url){
    const version=++requestVersion;
    if(!dialog.open){resumeCamera=running||starting;await shutdown();}
    status.textContent='Đang kiểm tra QR…';
    try{
      const data=await jsonResponse(await fetch(url,{cache:'no-store',headers:{'X-QR-Dialog':'1'}}));
      if(version!==requestVersion)return;
      error('');document.getElementById('qrResultTitle').textContent=data.title;
      content.innerHTML=data.html;
      if(!dialog.open)dialog.showModal();
      status.textContent='Kiểm tra và xác nhận trong hộp thoại. Đóng để quét tiếp.';
    }catch(err){
      if(version!==requestVersion)return;
      if(dialog.open)error(err.message);else status.textContent=err.message;
      submitted=false;cooldown=Date.now()+3000;
      if(resumeCamera&&!dialog.open&&!document.hidden){resumeCamera=false;void begin();}
    }
  }
  async function decoded(text){
    if(submitted||dialog.open||text===ignoreCode||(text===lastCode&&Date.now()<cooldown))return;
    if(!text.startsWith('LIBQR:')||text.length>2000){status.textContent='Mã này không phải QR thư viện. Hãy thử lại.';return;}
    submitted=true;lastCode=text;document.getElementById('scanCode').value=text;
    const url=new URL(form.getAttribute('action'),location.href);url.searchParams.set('code',text);
    await showResult(url);
  }
  form.addEventListener('submit',event=>{
    event.preventDefault();if(submitted||posting||dialog.open)return;
    const code=document.getElementById('scanCode').value.trim();
    ignoreCode='';cooldown=0;void decoded(code);
  });
  start.addEventListener('click',begin);
  stop.addEventListener('click',async()=>{resumeCamera=false;await shutdown();status.textContent='Đã tắt camera.';});
  file.addEventListener('change',async()=>{
    const image=file.files[0];if(!image||starting||running||dialog.open)return;
    if(image.size>10*1024*1024){status.textContent='Chọn ảnh QR nhỏ hơn 10 MB.';file.value='';return;}
    start.disabled=true;file.disabled=true;ignoreCode='';cooldown=0;
    try{await decoded(await scanner.scanFile(image,true));}
    catch(_){status.textContent='Không đọc được QR trong ảnh. Chọn ảnh rõ nét, đủ cả bốn góc.';}
    finally{file.value='';if(!running&&!starting){start.disabled=false;file.disabled=false;}}
  });
  document.getElementById('qrResultClose').addEventListener('click',()=>{if(!posting)dialog.close();});
  dialog.addEventListener('cancel',event=>{if(posting)event.preventDefault();});
  dialog.addEventListener('close',()=>{
    ++requestVersion;submitted=false;cooldown=Date.now()+3000;error('');content.replaceChildren();
    document.getElementById('scanCode').value='';file.value='';status.textContent='Sẵn sàng quét mã tiếp theo.';
    if(location.search){const url=new URL(location.href);if(url.searchParams.has('loan')){url.searchParams.delete('loan');window.history.replaceState(null,'',url);}}
    const resume=resumeCamera;resumeCamera=false;
    if(resume&&!document.hidden)void begin();
    else start.focus({preventScroll:true});
  });
  dialog.addEventListener('click',event=>{
    const link=event.target.closest('[data-qr-loan]');
    if(link&&!posting){event.preventDefault();void showResult(link.href);}
  });
  dialog.addEventListener('submit',async event=>{
    event.preventDefault();if(posting)return;
    const target=event.target,button=event.submitter;
    posting=true;error('');document.getElementById('qrResultClose').disabled=true;if(button)button.disabled=true;
    try{
      const data=await jsonResponse(await fetch(target.getAttribute('action'),{method:'POST',body:new URLSearchParams(new FormData(target)),headers:{'X-QR-Dialog':'1'},cache:'no-store'}));
      if(!data.ok)throw Error(data.error||'Chưa xác nhận được kết quả.');
      ignoreCode=lastCode;
      const notice=document.getElementById('qrNotice'),loanButton=document.getElementById('qrNoticeLoan');
      document.getElementById('qrNoticeText').textContent=data.message;notice.hidden=false;
      loanButton.hidden=!data.pending_fee;loanButton.dataset.url=data.loan_url||'';
      clearTimeout(noticeTimer);noticeTimer=setTimeout(()=>{notice.hidden=true;},data.pending_fee?10000:3500);
      posting=false;dialog.close();
    }catch(err){error(err.message);}
    finally{posting=false;document.getElementById('qrResultClose').disabled=false;if(button)button.disabled=false;}
  });
  document.getElementById('qrNoticeLoan').addEventListener('click',event=>{if(event.currentTarget.dataset.url)void showResult(event.currentTarget.dataset.url);});
  const initial=document.getElementById('qrStation')?.dataset.initialLoan;
  if(initial)void showResult(initial);
  else if(content.childElementCount){document.getElementById('qrResultTitle').textContent='Thẻ độc giả';dialog.showModal();}
  document.addEventListener('visibilitychange',()=>{if(document.hidden){resumeCamera=false;void shutdown();}});
  window.addEventListener('pagehide',()=>{++requestVersion;clearTimeout(noticeTimer);void shutdown();});
})();
