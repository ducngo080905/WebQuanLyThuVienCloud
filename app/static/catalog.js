(() => {
 const search=document.getElementById('catalogSearch'),genre=document.getElementById('catalogGenre');
 if(!search)return;
 const normalize=value=>value.toLocaleLowerCase('vi').normalize('NFD').replace(/[\u0300-\u036f]/g,'').replace(/đ/g,'d');
 const items=[...document.querySelectorAll('[data-catalog-book]')].map(node=>({node,text:normalize(node.textContent),genre:node.dataset.genre}));
 let frame;
 function filter(){
  const query=normalize(search.value.trim());let count=0;
  for(const item of items){const visible=item.text.includes(query)&&(!genre.value||item.genre===genre.value);if(item.node.hidden===visible)item.node.hidden=!visible;if(visible)count++;}
  document.getElementById('catalogEmpty').hidden=count>0||!items.length;
 }
 function schedule(){cancelAnimationFrame(frame);frame=requestAnimationFrame(filter);}
 search.addEventListener('input',schedule);genre.addEventListener('change',schedule);
})();
