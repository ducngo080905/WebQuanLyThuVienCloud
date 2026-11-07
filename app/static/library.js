const today=document.getElementById('today');if(today)today.textContent='Hôm nay: '+new Intl.DateTimeFormat('vi-VN',{timeZone:'Asia/Ho_Chi_Minh',weekday:'long',day:'2-digit',month:'2-digit',year:'numeric'}).format(new Date());
let previousFocus;
function openModal(id){previousFocus=document.activeElement;const el=document.getElementById(id);el.classList.add('open');document.body.style.overflow='hidden';el.querySelector('input,select,button')?.focus();}
function closeModal(id){document.getElementById(id).classList.remove('open');document.body.style.overflow='';previousFocus?.focus();}
function setupModals(){document.querySelectorAll('.modal-overlay:not([data-modal-ready])').forEach(el=>{el.dataset.modalReady='';const panel=el.querySelector('.modal');panel.setAttribute('role','dialog');panel.setAttribute('aria-modal','true');const heading=panel.querySelector('h3');heading.id=el.id+'Title';panel.setAttribute('aria-labelledby',heading.id);const close=document.createElement('button');close.type='button';close.className='modal-close';close.setAttribute('aria-label','Đóng');close.innerHTML='<span class="material-symbols-outlined">close</span>';close.onclick=()=>closeModal(el.id);panel.prepend(close);el.addEventListener('click',e=>{if(e.target===el)closeModal(el.id)});panel.querySelectorAll('.form-group').forEach((group,index)=>{const label=group.querySelector('label'),input=group.querySelector('input,select');if(label&&input){if(!input.id)input.id=el.id+'Field'+index;label.htmlFor=input.id;}});});}
setupModals();
document.addEventListener('library:content-updated',setupModals);
document.addEventListener('keydown',e=>{const modal=document.querySelector('.modal-overlay.open');if(!modal)return;if(e.key==='Escape')closeModal(modal.id);if(e.key==='Tab'){const focusable=[...modal.querySelectorAll('button,input,select,a[href]')].filter(el=>!el.disabled);const first=focusable[0],last=focusable.at(-1);if(e.shiftKey&&document.activeElement===first){e.preventDefault();last.focus();}else if(!e.shiftKey&&document.activeElement===last){e.preventDefault();first.focus();}}});
const normalize=s=>s.toLocaleLowerCase('vi').normalize('NFD').replace(/[\u0300-\u036f]/g,'').replace(/đ/g,'d');
const searchText=new WeakMap();
let filterFrame;
function filterTable(){
 const search=document.getElementById('tableSearch');
 if(!search)return;
 const filter=document.getElementById('tableFilter');
 const tableRows=document.querySelectorAll('[data-row]');
 const keyword=normalize(search.value.trim());let count=0;
 for(const row of tableRows){
  if(!searchText.has(row))searchText.set(row,normalize(row.textContent));
  const state=row.dataset.filter,category=!filter||!filter.value||state===filter.value||(filter.value==='issued'&&state==='overdue');
  const visible=category&&searchText.get(row).includes(keyword);
  if(row.hidden===visible)row.hidden=!visible;
  if(visible)count++;
 }
 const empty=document.getElementById('filterEmpty');if(empty)empty.hidden=count>0||!tableRows.length;
 const counter=document.getElementById('visibleCount');if(counter)counter.textContent='Hiển thị '+count+' kết quả';
}
function scheduleTableFilter(){cancelAnimationFrame(filterFrame);filterFrame=requestAnimationFrame(filterTable);}
document.addEventListener('library:row-update',event=>{searchText.delete(event.target);});
const initialSearch=document.getElementById('tableSearch');
if(initialSearch){initialSearch.value=new URLSearchParams(location.search).get('q')||'';filterTable();}
document.addEventListener('input',event=>{if(event.target.id==='tableSearch')scheduleTableFilter();});
document.addEventListener('change',event=>{if(event.target.id==='tableFilter')scheduleTableFilter();});
document.addEventListener('library:content-updated',filterTable);
