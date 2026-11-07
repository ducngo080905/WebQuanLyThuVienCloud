const {test}=require('node:test');
const assert=require('node:assert/strict');
const fs=require('node:fs');
const vm=require('node:vm');
class Element {
 constructor(){this.attributes=new Map();}
 setAttribute(key,value){this.attributes.set(key,value);}
 removeAttribute(key){this.attributes.delete(key);}
}
class Form extends Element {constructor(){super();this.method='post';this.isConnected=true;}}
function environment(){
 const events={},windowEvents={},tasks=[],timers=new Map();let next=0;
 vm.runInNewContext(fs.readFileSync('app/static/interaction.js','utf8'),{
  HTMLFormElement:Form,document:{addEventListener:(name,callback)=>events[name]=callback,querySelector:()=>null},
  window:{addEventListener:(name,callback)=>windowEvents[name]=callback},
  queueMicrotask:callback=>tasks.push(callback),setTimeout:callback=>{timers.set(++next,callback);return next;},clearTimeout:id=>timers.delete(id)
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
