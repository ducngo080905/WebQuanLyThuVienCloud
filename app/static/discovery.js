(() => {
  const form=document.getElementById('discoveryFilters'),results=document.getElementById('discoveryResults'),status=document.getElementById('discoveryStatus');
  if(!form||!window.fetch||!window.AbortController)return;
  let timer,controller,version=0;
  function formUrl(){const url=new URL(form.getAttribute('action')||location.href,location.href);for(const [key,value] of new FormData(form)){if(value && !(key==='sort'&&value==='newest'))url.searchParams.set(key,value);}return url;}
  function syncForm(url){form.elements.q.value=url.searchParams.get('q')||'';form.elements.genre.value=url.searchParams.get('genre')||'';form.elements.sort.value=url.searchParams.get('sort')||'newest';for(const radio of form.elements.availability)radio.checked=radio.value===(url.searchParams.get('availability')||'');}
  async function load(url,{push=false,pagination=false}={}){
    clearTimeout(timer);controller?.abort();controller=new AbortController();const current=++version;
    results.setAttribute('aria-busy','true');status.textContent='Đang tìm sách…';delete status.dataset.error;
    const target=new URL(url);target.searchParams.set('partial','1');
    try{
      const response=await fetch(target,{signal:controller.signal,headers:{Accept:'text/html'},cache:'no-store',redirect:'error'});
      if(!response.ok)throw Error();const html=await response.text();if(current!==version)return;
      const content=new DOMParser().parseFromString(html,'text/html');if(!content.querySelector('.discovery-results-heading'))throw Error();
      results.replaceChildren(...content.body.childNodes);status.textContent='';
      if(push)history.pushState(null,'',url);else history.replaceState(null,'',url);
      if(pagination){results.querySelector('h2')?.setAttribute('tabindex','-1');results.querySelector('h2')?.focus({preventScroll:true});results.scrollIntoView({block:'start',behavior:'instant'});}
    }catch(error){if(error.name!=='AbortError'&&current===version){status.textContent='Chưa tải được kết quả. Vui lòng bấm Tìm sách để thử lại.';status.dataset.error='true';}}
    finally{if(current===version)results.removeAttribute('aria-busy');}
  }
  form.addEventListener('submit',event=>{event.preventDefault();load(formUrl());});
  // Associated sidebar fields belong to this form, although they sit outside it.
  document.addEventListener('change',event=>{if(event.target.form===form&&event.target.name!=='q')load(formUrl());});
  form.elements.q.addEventListener('input',()=>{controller?.abort();++version;clearTimeout(timer);timer=setTimeout(()=>load(formUrl()),250);});
  document.addEventListener('click',event=>{const link=event.target.closest('[data-discovery-page],[data-discovery-reset]');if(!link||event.button!==0||event.metaKey||event.ctrlKey||event.shiftKey||event.altKey)return;event.preventDefault();const url=new URL(link.href);syncForm(url);load(url,{push:true,pagination:link.hasAttribute('data-discovery-page')});});
  window.addEventListener('popstate',()=>{const url=new URL(location.href);syncForm(url);load(url);});
  window.addEventListener('pagehide',()=>{clearTimeout(timer);controller?.abort();});
})();
