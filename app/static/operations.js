(() => {
 const script=document.currentScript || document.querySelector('script[data-version]');if(!script)return;
 const version=script.dataset.version,onMaintenance=script.dataset.maintenancePage==='1',login=script.dataset.login==='1',preview=script.dataset.preview==='1';
 const nativeFetch=window.fetch.bind(window);let busy=false,leaving=false,dismissedVersion='',notice,lastMaintenance,pollTimer;
 function lock(){
  if(leaving||login||onMaintenance)return;leaving=true;
  try{sessionStorage.setItem('library-maintenance-return',location.pathname+location.search+location.hash);}catch(_){}
  const cover=document.createElement('div');cover.className='operations-lock';cover.setAttribute('role','alert');cover.textContent='Thư viện đang chuyển sang chế độ bảo trì…';document.body.append(cover);document.querySelector('main')?.setAttribute('inert','');
  location.replace('/maintenance');
 }
 // A rejected request triggers the maintenance screen without waiting for polling.
 window.fetch=async(...args)=>{const response=await nativeFetch(...args);if(response.headers.get('X-Library-Maintenance')==='1')lock();return response;};
 function resume(){let target='/';try{const stored=sessionStorage.getItem('library-maintenance-return');sessionStorage.removeItem('library-maintenance-return');if(stored&&stored.startsWith('/')&&!stored.startsWith('//')&&!stored.startsWith('/maintenance')&&!stored.startsWith('/auth/')&&!stored.startsWith('/logout'))target=stored;}catch(_){}location.replace(target);}
 function unsaved(){return [...document.forms].some(form=>form.method.toLowerCase()==='post'&&[...form.elements].some(field=>!field.disabled&&field.type!=='hidden'&&field.type!=='submit'&&field.type!=='button'&&((field.type==='file'&&field.files?.length)||(['checkbox','radio'].includes(field.type)?field.checked!==field.defaultChecked:field.value!==undefined&&field.defaultValue!==undefined&&field.value!==field.defaultValue))));}
 function showRelease(next){
  if(onMaintenance||next===version||next===dismissedVersion||notice)return;
  notice=document.createElement('aside');notice.className='release-notice';notice.setAttribute('role','status');
  const title=document.createElement('strong');title.textContent='Đã có phiên bản mới';const description=document.createElement('p');description.textContent='Cập nhật để sử dụng bản mới. Bạn có thể hoàn tất thao tác đang làm trước.';
  const actions=document.createElement('div');actions.className='release-notice-actions';const apply=document.createElement('button');apply.className='release-apply';apply.textContent='Cập nhật';const later=document.createElement('button');later.textContent='Để sau';
  apply.addEventListener('click',()=>{if(unsaved()&&!confirm('Bạn có nội dung hoặc tệp chưa lưu. Tải lại trang sẽ bỏ các thay đổi đó. Bạn vẫn muốn cập nhật?'))return;location.reload();});
  later.addEventListener('click',()=>{dismissedVersion=next;notice.remove();notice=null;});actions.append(apply,later);notice.append(title,description,actions);document.body.append(notice);
 }
 let countdownEnd = null;
 function renderCountdown(){
  const timer=document.getElementById('maintenanceCountdown');
  if(!timer)return;
  timer.hidden=countdownEnd===null;
  if(countdownEnd===null)return;
  const seconds=Math.max(0,Math.ceil((countdownEnd-Date.now())/1000));
  if(!seconds){timer.textContent='Đã hết thời gian dự kiến. Vui lòng chờ quản trị viên mở lại web.';return;}
  const hours=Math.floor(seconds/3600);
  const minutes=Math.floor(seconds/60)%60;
  timer.textContent='Còn khoảng '+hours+' giờ '+minutes+' phút '+seconds%60+' giây';
 }
 async function check(){
  if(busy||leaving)return;busy=true;
  try{const response=await nativeFetch('/system/status',{cache:'no-store',redirect:'error',headers:{Accept:'application/json'}});if(!response.ok)return;const data=await response.json();
   document.querySelectorAll('[data-system-label]').forEach(node=>{const text=data.maintenance?'● Đang bảo trì':'● Hoạt động';if(node.textContent!==text)node.textContent=text;});
   if(lastMaintenance!==data.maintenance){lastMaintenance=data.maintenance;
    document.querySelectorAll('.maintenance-toggle').forEach(button=>button.textContent=data.maintenance?'Tắt bảo trì':'Bật bảo trì');
    const dialog=document.getElementById('maintenanceDialog');if(dialog){const save=dialog.querySelector('[data-maintenance-save]');save.hidden=save.disabled=!data.maintenance;dialog.querySelector('[name=enabled]').value=data.maintenance?'0':'1';dialog.querySelector('[data-maintenance-title]').textContent=data.maintenance?'Mở lại thư viện?':'Bật chế độ bảo trì?';dialog.querySelector('[data-maintenance-description]').hidden=!data.maintenance;dialog.querySelector('[data-maintenance-current]').hidden=!data.maintenance;dialog.querySelector('[data-maintenance-confirm]').textContent=data.maintenance?'Mở lại web':'Bật bảo trì';}
   }
   const label=data.expected_end ? data.expected_end : 'Chưa xác định';
   document.querySelectorAll('#maintenanceEstimateValue,[data-maintenance-current-value]').forEach(estimate=>{
    if(estimate.textContent!==label)estimate.textContent=label;
   });
   if(onMaintenance){
    countdownEnd=Number.isFinite(data.remaining_seconds)?Date.now()+data.remaining_seconds*1000:null;
    renderCountdown();
    if(preview)return;if(!data.maintenance||data.admin)resume();return;}
   if(data.maintenance&&!data.admin&&!login){lock();return;}showRelease(data.version);
  }catch(_){const feedback=document.getElementById('maintenanceFeedback');if(feedback)feedback.textContent='Chưa kết nối được máy chủ. Trang sẽ tự kiểm tra lại.';}finally{busy=false;}
 }
 function start(){if(!pollTimer)pollTimer=setInterval(()=>{renderCountdown();check();},1000);}
 check();start();
 document.addEventListener('visibilitychange',()=>{if(!document.hidden)check();});window.addEventListener('pageshow',()=>{start();check();});window.addEventListener('pagehide',()=>{clearInterval(pollTimer);pollTimer=null;});
})();
