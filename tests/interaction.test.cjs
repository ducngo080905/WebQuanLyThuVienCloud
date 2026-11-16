const {test}=require('node:test');
const assert=require('node:assert/strict');
const fs=require('node:fs');
const vm=require('node:vm');
class Element {
 constructor(){this.attributes=new Map();}
 setAttribute(key,value){this.attributes.set(key,value);}
 getAttribute(key){return this.attributes.get(key)??null;}
 removeAttribute(key){this.attributes.delete(key);}
}
class Form extends Element {constructor(){super();this.method='post';this.setAttribute('method','post');this.isConnected=true;}}
function environment(overrides={}){
 const events={},windowEvents={},tasks=[],timers=new Map();let next=0;
 vm.runInNewContext(fs.readFileSync('app/static/interaction.js','utf8'),{
  HTMLFormElement:Form,
  window:{addEventListener:(name,callback)=>windowEvents[name]=callback},
  queueMicrotask:callback=>tasks.push(callback),setTimeout:callback=>{timers.set(++next,callback);return next;},clearTimeout:id=>timers.delete(id),...overrides,
  document:{querySelector:()=>null,...overrides.document,addEventListener:(name,callback)=>events[name]=callback}
 });
 const submit=(form,button)=>{const event={target:form,submitter:button,defaultPrevented:false,preventDefault(){this.defaultPrevented=true;}};events.submit(event);return event;};
 return {submit,windowEvents,flush(){while(tasks.length)tasks.shift()();}};
}
test('pending submit prevents duplicate requests and retains submit button values',()=>{
 const env=environment(),form=new Form(),button=new Element();button.name='action';button.value='approve';
 env.submit(form,button);env.flush();
 assert.equal(form.attributes.get('aria-busy'),'true');
 assert.equal(button.name,'action');assert.equal(button.value,'approve');assert.equal(button.disabled,undefined);
 assert.equal(env.submit(form,button).defaultPrevented,true);
});
test('cancelled confirmations and AJAX forms retain their own loading lifecycle',()=>{
 const env=environment(),form=new Form(),button=new Element();const event=env.submit(form,button);event.preventDefault();env.flush();
 assert.equal(form.attributes.has('aria-busy'),false);assert.equal(env.submit(form,button).defaultPrevented,false);
});
test('back navigation restores a usable form instead of leaving it pending',()=>{
 const env=environment(),form=new Form(),button=new Element();env.submit(form,button);env.flush();env.windowEvents.pageshow();
 assert.equal(form.attributes.has('aria-busy'),false);assert.equal(button.attributes.has('aria-disabled'),false);
 assert.equal(env.submit(form,button).defaultPrevented,false);
});

for(const action of ['approve','reject'])test(`AJAX ${action} uses the form URL despite controls named action`,async()=>{
 const calls=[],feedback={replaceChildren(){}};
 const env=environment({
  location:{href:'https://library.test/admin/borrow-requests'},
  document:{querySelector:()=>null,
    getElementById:()=>feedback,createElement:()=>new Element()},
  FormData:class extends URLSearchParams{
   constructor(form,button){super({csrf_token:'test-only'});if(button?.name)this.append(button.name,button.value);}
  },URLSearchParams,
  fetch:async(url,options)=>{calls.push({url,options});return {ok:false,headers:{get:()=>null}};},
 });
 const form=new Form(),button=new Element();
 form.dataset={refresh:'borrowReview'};form.closest=()=>null;
 form.setAttribute('action','/admin/borrow-requests/7/review');
 form.action={toString:()=>'[object RadioNodeList]'};
 button.name='action';button.value=action;
 env.submit(form,button);
 await new Promise(resolve=>setImmediate(resolve));
 assert.equal(calls.length,1);
 assert.equal(calls[0].url,'/admin/borrow-requests/7/review');
 assert.equal(calls[0].options.body.get('action'),action);
 assert.equal(calls[0].options.body.get('csrf_token'),'test-only');
 assert.equal(button.disabled,false);
});
