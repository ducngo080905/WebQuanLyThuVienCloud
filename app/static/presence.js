(()=>{
 const script=document.currentScript,csrf=script.dataset.csrf;
 // Each tab has a separate ID, so hiding one tab cannot hide another visible tab.
 const tab=Array.from(crypto.getRandomValues(new Uint8Array(16)),b=>b.toString(16).padStart(2,'0')).join('');
 let busy=false;
 function body(closed=false){return new URLSearchParams({csrf_token:csrf,tab_id:tab,visible:document.visibilityState==='visible'?'1':'0',closed:closed?'1':'0'});}
 async function ping(){if(busy)return;busy=true;try{await fetch('/activity/heartbeat',{method:'POST',body:body(),redirect:'error',credentials:'same-origin'});}catch{}finally{busy=false;}}
 ping();setInterval(ping,15000);document.addEventListener('visibilitychange',ping);window.addEventListener('pageshow',ping);
 window.addEventListener('pagehide',()=>navigator.sendBeacon('/activity/heartbeat',body(true)));
})();
