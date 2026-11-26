const {test}=require('node:test');
const assert=require('node:assert/strict');
const fs=require('node:fs');
const vm=require('node:vm');

function setup(responses){
 const timers=new Map(),events={},windowEvents={},calls=[];let number=0,replaced=0,removed=0;
 const root={dataset:{state:'issued:none',complete:'0',url:'/loans/1/live-status'}},status={},heading={};
 const document={hidden:false,getElementById:id=>id==='readerLoanLive'?root:id==='readerLoanStatus'?status:{replaceWith(){replaced++;}},
  querySelector:selector=>selector.includes('flow-qr')?{remove(){removed++;}}:heading,
  dispatchEvent(){},addEventListener:(key,fn)=>events[key]=fn};
 vm.runInNewContext(fs.readFileSync('app/static/reader_loan_live.js','utf8'),{
  document,window:{addEventListener:(key,fn)=>windowEvents[key]=fn},URL,AbortController,Event,
  location:{href:'http://localhost:5000/loans/1/return'},
  setTimeout:(fn,delay)=>{timers.set(++number,{fn,delay});return number;},clearTimeout:id=>timers.delete(id),
  DOMParser:class{parseFromString(){return {getElementById:()=>({})};}},
  fetch:async url=>{calls.push(String(url));const data=responses.shift();return {ok:true,status:200,redirected:false,headers:{get:()=> 'application/json'},json:async()=>data};}
 });
 return {root,status,heading,document,timers,calls,replaced:()=>replaced,removed:()=>removed,
  async flush(){for(let i=0;i<8;i++)await Promise.resolve();},
  async tick(){const [id,timer]=timers.entries().next().value;timers.delete(id);await timer.fn();},
  hide(){document.hidden=true;events.visibilitychange();},show(){document.hidden=false;events.visibilitychange();}};
}

test('reader replaces QR with receipt in place and stops polling once return is complete',async()=>{
 const env=setup([{state:'issued:none',status:'issued',changed:false,complete:false},
  {state:'returned:1',status:'returned',changed:true,complete:true,html:'<div id="returnDetails">Receipt</div>',heading:'Đã trả sách'}]);
 await env.flush();assert.equal(env.timers.size,1);
 await env.tick();await env.flush();
 assert.equal(env.replaced(),1);assert.equal(env.heading.textContent,'Đã trả sách');
 assert.match(env.status.textContent,/QR trả sách đã được gỡ/);assert.equal(env.timers.size,0);
});

test('polling pauses in hidden tabs and checks immediately when visible again',async()=>{
 const env=setup([{state:'issued:none',status:'issued',changed:false,complete:false},
  {state:'issued:none',status:'issued',changed:false,complete:false}]);
 await env.flush();env.hide();assert.equal(env.timers.size,0);
 env.show();await env.flush();assert.equal(env.calls.length,2);assert.equal(env.timers.size,1);
});

test('unpaid receipt remains live until the staff verifies payment',async()=>{
 const env=setup([{state:'returned:0',status:'returned',changed:true,complete:false,html:'receipt'},
  {state:'returned:1',status:'returned',changed:true,complete:true,html:'paid receipt'}]);
 await env.flush();assert.equal([...env.timers.values()][0].delay,10000);
 await env.tick();await env.flush();
 assert.match(env.calls[1],/state=returned%3A0/);assert.equal(env.replaced(),2);assert.equal(env.timers.size,0);
});
