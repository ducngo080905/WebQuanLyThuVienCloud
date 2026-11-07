(() => {
 const account=document.getElementById('readerAccount');if(!account)return;
 document.addEventListener('click',event=>{if(account.open&&!account.contains(event.target))account.open=false;});
 document.addEventListener('keydown',event=>{if(event.key==='Escape'&&account.open){account.open=false;account.querySelector('summary').focus();}});
 account.addEventListener('focusout',event=>{if(event.relatedTarget&&!account.contains(event.relatedTarget))account.open=false;});
})();
