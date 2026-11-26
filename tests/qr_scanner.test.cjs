const {test}=require('node:test');
const assert=require('node:assert/strict');
const fs=require('node:fs');
const vm=require('node:vm');

function setup(options={}) {
  const elements=new Map(),events={},windowEvents={};
  let success,resolveStart,stops=0,starts=0,gets=0,posts=0;
  const started=new Promise(resolve=>{resolveStart=resolve;});
  for(const id of ['startScan','stopScan','scanStatus','scanFile','scanCode','scanForm','qrResultDialog','qrResultContent','qrResultError','qrResultTitle','qrResultClose','qrNotice','qrNoticeText','qrNoticeLoan','qrStation'])
    elements.set(id,{disabled:false,value:'',textContent:'',files:[],events:{},dataset:{},hidden:false,open:false,childElementCount:0,
      addEventListener(name,fn){this.events[name]=fn;},getAttribute(name){return name==='action'?'/circulation/scan':null;},
      focus(){},replaceChildren(){this.innerHTML='';},showModal(){this.open=true;},close(){this.open=false;this.events.close?.();}});
  class Scanner {
    start(constraints,config,callback){starts++;success=callback;return options.deferred?started:Promise.resolve();}
    stop(){stops++;return Promise.resolve();}
    scanFile(){return Promise.resolve(options.fileCode||'LIBQR:valid-test');}
  }
  vm.runInNewContext(fs.readFileSync('app/static/qr_scanner.js','utf8'),{
    Html5Qrcode:Scanner,Html5QrcodeSupportedFormats:{QR_CODE:0},URL,URLSearchParams,Date,
    FormData:class{*[Symbol.iterator](){yield ['received','1'];}},setTimeout:()=>1,clearTimeout(){},
    location:{href:'http://localhost:5000/circulation/scan'},
    fetch:async(url,init)=>{if(init.method==='POST')posts++;else gets++;
      return {ok:!options.error,redirected:false,headers:{get:()=> 'application/json'},json:async()=>options.error?{error:'Invalid QR'}:
        init.method==='POST'?{ok:true,message:'Đã nhận sách',pending_fee:0}:{title:'Loan',html:'<p>Preview</p>'}};},
    document:{hidden:false,getElementById:id=>elements.get(id),addEventListener:(name,fn)=>events[name]=fn},
    window:{Html5Qrcode:Scanner,isSecureContext:options.secure!==false,addEventListener:(name,fn)=>windowEvents[name]=fn}
  });
  return {element:id=>elements.get(id),click:id=>elements.get(id).events.click(),resolveStart,
    decoded:text=>success(text),pagehide:()=>windowEvents.pagehide(),stops:()=>stops,starts:()=>starts,gets:()=>gets,posts:()=>posts,
    confirm:()=>elements.get('qrResultDialog').events.submit({preventDefault(){},target:{getAttribute:()=>'/loans/1/confirm-return'},submitter:{disabled:false}})};
}

test('late camera permission is stopped if user cancels while permission is pending',async()=>{
  const env=setup({deferred:true});
  const opening=env.click('startScan');
  await env.click('stopScan');
  env.resolveStart();await opening;
  assert.equal(env.stops(),1);
  assert.equal(env.element('startScan').disabled,false);
  assert.equal(env.element('stopScan').disabled,true);
});

test('leaving the page while camera is starting shuts down the eventual stream',async()=>{
  const env=setup({deferred:true});const opening=env.click('startScan');
  env.pagehide();env.resolveStart();await opening;
  assert.equal(env.stops(),1);
});

test('external QR is ignored and repeated detection opens one modal without navigation',async()=>{
  const env=setup();await env.click('startScan');
  await env.decoded('https://untrusted.example/');
  assert.equal(env.gets(),0);
  await Promise.all([env.decoded('LIBQR:signed'),env.decoded('LIBQR:signed')]);
  assert.equal(env.stops(),1);assert.equal(env.gets(),1);
  assert.equal(env.element('scanCode').value,'LIBQR:signed');
});

test('insecure origin never requests camera and retains image fallback',async()=>{
  const env=setup({secure:false});await env.click('startScan');
  assert.match(env.element('scanStatus').textContent,/HTTPS/);
  assert.equal(env.element('scanFile').disabled,false);
  env.element('scanFile').files=[{size:100}];
  await env.element('scanFile').events.change();
  assert.equal(env.gets(),1);
});


test('confirmation closes preview and resumes camera for the next distinct QR',async()=>{
 const env=setup();await env.click('startScan');await env.decoded('LIBQR:first');
 assert.equal(env.element('qrResultDialog').open,true);
 await env.confirm();await Promise.resolve();
 assert.equal(env.posts(),1);assert.equal(env.element('qrResultDialog').open,false);
 assert.equal(env.element('qrNotice').hidden,false);assert.equal(env.starts(),2);
 await env.decoded('LIBQR:first');assert.equal(env.gets(),1);
 await env.decoded('LIBQR:second');assert.equal(env.gets(),2);
});

test('lookup errors do not lock scanner or open a broken modal',async()=>{
 const env=setup({error:true});await env.click('startScan');await env.decoded('LIBQR:bad');
 assert.equal(env.element('qrResultDialog').open,false);assert.equal(env.starts(),2);
 await env.decoded('LIBQR:another');assert.equal(env.gets(),2);
});
