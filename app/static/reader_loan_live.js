(() => {
  const root=document.getElementById('readerLoanLive');
  if(!root)return;
  const status=document.getElementById('readerLoanStatus');
  let state=root.dataset.state,complete=root.dataset.complete==='1',timer,controller,generation=0;
  function stop(){clearTimeout(timer);generation++;controller?.abort();controller=null;}
  async function check(){
    if(document.hidden||complete)return;
    stop();const version=generation;controller=new AbortController();
    const url=new URL(root.dataset.url,location.href);url.searchParams.set('state',state);
    let delay=3000;
    try{
      const response=await fetch(url,{cache:'no-store',signal:controller.signal,headers:{Accept:'application/json'}});
      if(version!==generation)return;
      if(response.redirected||[401,403,404].includes(response.status)){
        document.querySelector('#returnDetails .flow-qr')?.remove();
        status.textContent='Phiên đăng nhập đã thay đổi. Vui lòng đăng nhập lại để xem phiếu.';complete=true;return;
      }
      if(!response.ok||!response.headers.get('Content-Type')?.includes('application/json'))throw Error();
      const data=await response.json();if(version!==generation)return;
      if(data.changed){
        const page=new DOMParser().parseFromString(data.html,'text/html');
        const next=page.getElementById('returnDetails');if(!next)throw Error();
        document.getElementById('returnDetails').replaceWith(next);
        document.querySelector('.flow-heading h1').textContent=data.heading;
        document.dispatchEvent(new Event('library:content-updated'));
      }
      state=data.state;complete=data.complete;
      status.textContent=data.status==='returned'?'Thư viện đã xác nhận trả sách. QR trả sách đã được gỡ.':'Tự cập nhật khi thủ thư xác nhận nhận sách.';
      delay=data.status==='returned'?10000:3000;
    }catch(err){
      if(err.name==='AbortError'||version!==generation)return;
      status.textContent='Chưa kiểm tra được trạng thái. Đang thử kết nối lại…';delay=10000;
    }finally{
      if(version===generation){controller=null;if(!complete&&!document.hidden)timer=setTimeout(check,delay);}
    }
  }
  document.addEventListener('visibilitychange',()=>{if(document.hidden)stop();else void check();});
  window.addEventListener('pagehide',stop);
  window.addEventListener('pageshow',()=>{void check();});
  window.addEventListener('online',()=>{void check();});
  void check();
})();
