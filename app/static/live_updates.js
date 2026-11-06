(()=>{
 const script=document.currentScript,csrf=script.dataset.csrf,phoneOverlay=document.getElementById('phoneRequiredOverlay'),toast=document.getElementById('announcementToast');
 const storageKey='library-toast-seen-'+script.dataset.userId;
 let seen;try{seen=new Set(JSON.parse(localStorage.getItem(storageKey)||'[]'));}catch{seen=new Set();}
 let phoneRequired=false,queue=[],busy=false,currentId=null,timer,previousFocus;
 const remember=id=>{seen.add(id);try{localStorage.setItem(storageKey,JSON.stringify([...seen].slice(-500)));}catch{}};
 function dismiss(){if(currentId)remember(currentId);clearTimeout(timer);currentId=null;toast.hidden=true;showNext();}
 function showNext(){if(phoneRequired||currentId)return;const item=queue.find(item=>!seen.has(item.id));if(!item)return;currentId=item.id;document.getElementById('announcementTitle').textContent=item.title;document.getElementById('announcementBody').textContent=item.body;toast.hidden=false;timer=setTimeout(dismiss,7000);}
 function render(){if(phoneOverlay.hidden===phoneRequired){if(phoneRequired){previousFocus=document.activeElement;phoneOverlay.hidden=false;phoneOverlay.querySelector('input')?.focus();}else{phoneOverlay.hidden=true;previousFocus?.focus();}}
  document.querySelector('.main').inert=phoneRequired;document.querySelector('header')?.toggleAttribute('inert',phoneRequired);document.querySelector('.sidebar')?.toggleAttribute('inert',phoneRequired);document.body.classList.toggle('live-modal-open',phoneRequired);
  if(phoneRequired){clearTimeout(timer);currentId=null;toast.hidden=true;}else showNext();
 }
 async function poll(){if(busy||document.visibilityState!=='visible')return;busy=true;try{const response=await fetch('/live-updates',{cache:'no-store',redirect:'error'});if(!response.ok)throw Error();const data=await response.json();const googleNotice=document.getElementById('googleLinkNotice');if(googleNotice)googleNotice.hidden=!data.google_link_required;phoneRequired=data.phone_required;queue=data.announcements;render();}catch{}finally{busy=false;}}
 const post=(url,values)=>fetch(url,{method:'POST',headers:{'Content-Type':'application/x-www-form-urlencoded'},body:new URLSearchParams({csrf_token:csrf,...values}),redirect:'error'});
 document.getElementById('requiredPhoneForm').addEventListener('submit',async event=>{event.preventDefault();const button=event.target.querySelector('button'),error=document.getElementById('requiredPhoneError');button.disabled=true;error.textContent='';try{const response=await post('/profile/required-phone',{phone:document.getElementById('requiredPhone').value});const data=await response.json();if(!response.ok)throw Error(data.error||'Không lưu được số điện thoại.');phoneRequired=false;render();await poll();}catch(e){error.textContent=e.message||'Mất kết nối. Vui lòng thử lại.';}finally{button.disabled=false;}});
 document.getElementById('announcementDismiss').addEventListener('click',dismiss);
 document.getElementById('announcementLink').addEventListener('click',()=>{if(currentId)remember(currentId);});
 document.addEventListener('keydown',event=>{if(phoneOverlay.hidden)return;if(event.key==='Escape'){event.preventDefault();event.stopImmediatePropagation();}if(event.key==='Tab'){const elements=[...phoneOverlay.querySelectorAll('input,button')].filter(el=>!el.disabled),first=elements[0],last=elements.at(-1);if(event.shiftKey&&document.activeElement===first){event.preventDefault();last.focus();}else if(!event.shiftKey&&document.activeElement===last){event.preventDefault();first.focus();}}},true);
 window.addEventListener('storage',event=>{if(event.key===storageKey){try{seen=new Set(JSON.parse(event.newValue||'[]'));if(seen.has(currentId))dismiss();}catch{}}});
 poll();setInterval(poll,5000);document.addEventListener('visibilitychange',poll);window.addEventListener('focus',poll);
})();
