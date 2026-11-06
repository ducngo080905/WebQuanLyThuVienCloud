(()=>{
 let busy=false;const indicator=document.getElementById('presenceUpdate');
 const format=value=>value?new Intl.DateTimeFormat('vi-VN',{timeZone:'Asia/Ho_Chi_Minh',dateStyle:'short',timeStyle:'medium'}).format(new Date(value)):'Chưa ghi nhận';
 async function update(){if(busy||document.visibilityState!=='visible')return;busy=true;try{
  const response=await fetch('/admin/accounts/presence',{cache:'no-store',redirect:'error'});if(!response.ok)throw new Error();
  const data=await response.json();
  data.accounts.forEach(account=>{const row=document.querySelector('[data-account-id="'+account.id+'"]');if(!row)return;
   const status=row.querySelector('[data-presence-status]');status.textContent=!account.active?'Đã khóa':account.online?(account.viewing?'● Đang xem web':'● Đang mở web · tab nền'):'Ngoại tuyến';status.className='badge '+(account.online?'badge-success':!account.active?'badge-danger':'badge-info');
   row.querySelector('[data-presence-last]').textContent=format(account.last_seen);
   const devices=row.querySelector('[data-presence-devices]');devices.replaceChildren();
   account.devices.forEach(device=>{const entry=document.createElement('div'),name=document.createElement('strong'),ip=document.createElement('small');name.textContent=device.name;ip.textContent='IP: '+device.ip;entry.append(name,ip);devices.append(entry);});if(!account.devices.length)devices.textContent='Chưa ghi nhận';
  });indicator.textContent='Cập nhật lúc '+new Date().toLocaleTimeString('vi-VN',{timeZone:'Asia/Ho_Chi_Minh'});
 }catch{indicator.textContent='Mất kết nối cập nhật · sẽ tự thử lại';document.querySelectorAll('[data-presence-status]').forEach(status=>{status.textContent='Chưa xác định';status.className='badge badge-warn';});}finally{busy=false;}}
 update();setInterval(update,5000);document.addEventListener('visibilitychange',update);
})();
