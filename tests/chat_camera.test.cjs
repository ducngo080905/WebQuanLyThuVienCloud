const {test} = require('node:test');
const assert = require('node:assert/strict');
const fs = require('node:fs');
const vm = require('node:vm');
const flush = () => new Promise(resolve => setImmediate(resolve));
function setup(getUserMedia, secure = true) {
  class Node {
    constructor() { this.listeners={}; this.hidden=false; this.disabled=false; this.open=false; this.videoWidth=1920; this.videoHeight=1080; this.classList={toggle(){}}; }
    addEventListener(type, callback) { (this.listeners[type] ||= []).push(callback); }
    fire(type, event={}) { for(const callback of this.listeners[type] || []) callback(event); }
    showModal() { this.open=true; }
    close() { this.open=false; this.fire('close'); }
    pause() {}
    play() { return Promise.resolve(); }
    removeAttribute(name) { delete this[name]; }
    click() { this.fire('click'); }
  }
  const nodes=new Map(); const get=id => { if(!nodes.has(id)) nodes.set(id,new Node()); return nodes.get(id); };
  const doc=new Node(); doc.getElementById=get; const canvases=[];
  doc.createElement=() => { const canvas={getContext:()=>({drawImage(){}}),toBlob(callback,type,quality){ this.type=type;this.quality=quality;callback(new Blob(['jpeg'],{type})); }};canvases.push(canvas);return canvas; };
  const win=new Node();win.isSecureContext=secure;
  const urls={created:[],revoked:[],createObjectURL(file){this.created.push(file);return 'blob:photo';},revokeObjectURL(url){this.revoked.push(url);}};
  class PhotoFile extends Blob {constructor(parts,name,opts){super(parts,opts);this.name=name;}}
  vm.runInNewContext(fs.readFileSync('app/static/chat_camera.js','utf8'),{window:win,document:doc,navigator:{mediaDevices:{getUserMedia}},URL:urls,File:PhotoFile,Date,Promise});
  const photos=[];const camera=new win.LibraryChatCamera({context:()=>({id:42,allowed:true}),onPhoto:(...args)=>photos.push(args)});
  return {camera,get,doc,win,urls,canvases,photos};
}
function stream() { const track={stopped:false,stop(){this.stopped=true;}};return {track,getTracks:()=>[track]}; }

test('does not access camera until requested and releases a late permission result',async()=>{
  let requests=0,resolve; const media=stream();
  const env=setup(()=>{requests++;return new Promise(done=>resolve=done);});
  assert.equal(requests,0);env.camera.open();assert.equal(requests,1);
  env.camera.close();resolve(media);await flush();
  assert.equal(media.track.stopped,true);assert.equal(env.camera.stream,null);assert.equal(env.photos.length,0);
});
test('captures a bounded JPEG, stops camera, and waits for explicit photo selection',async()=>{
  const media=stream();const env=setup(async constraints=>{assert.equal(constraints.audio,false);return media;});
  env.camera.open();await flush();assert.equal(env.get('takeChatPhoto').disabled,false);
  await env.camera.capture();assert.equal(media.track.stopped,true);
  assert.equal(env.canvases[0].width,1600);assert.equal(env.canvases[0].height,900);assert.equal(env.canvases[0].type,'image/jpeg');
  assert.equal(env.photos.length,0);assert.equal(env.get('useChatPhoto').hidden,false);
  env.get('useChatPhoto').click();assert.equal(env.photos.length,1);assert.equal(env.photos[0][0].type,'image/jpeg');assert.equal(env.photos[0][1],42);
  assert.equal(env.get('chatCameraDialog').open,false);assert.deepEqual(env.urls.revoked,['blob:photo']);
});
test('handles denied permission and insecure pages without capturing anything',async()=>{
  const denied=setup(async()=>{const e=new Error();e.name='NotAllowedError';throw e;});
  denied.camera.open();await flush();assert.match(denied.get('chatCameraStatus').textContent,/chưa cho phép/);assert.equal(denied.get('takeChatPhoto').disabled,true);
  let requests=0;const insecure=setup(()=>{requests++;},false);insecure.camera.open();await flush();
  assert.equal(requests,0);assert.match(insecure.get('chatCameraStatus').textContent,/HTTPS/);assert.equal(insecure.photos.length,0);
});
test('releases live camera on tab hide and ignores captures completed after closing',async()=>{
  const media=stream();const env=setup(async()=>media);env.camera.open();await flush();
  env.doc.hidden=true;env.doc.fire('visibilitychange');assert.equal(media.track.stopped,true);assert.equal(env.camera.stream,null);
  const second=stream();const again=setup(async()=>second);again.camera.open();await flush();
  let finish;again.doc.createElement=()=>({getContext:()=>({drawImage(){}}),toBlob(callback){finish=callback;}});
  const capture=again.camera.capture();again.camera.close();finish(new Blob(['jpeg'],{type:'image/jpeg'}));await capture;
  assert.equal(again.camera.file,null);assert.equal(again.photos.length,0);assert.equal(second.track.stopped,true);
});
test('retake releases the preview and camera switching releases the previous stream',async()=>{
  const media=[stream(),stream(),stream()];let calls=0;const env=setup(async()=>media[calls++]);
  env.camera.open();await flush();env.get('switchChatCamera').click();await flush();assert.equal(media[0].track.stopped,true);
  await env.camera.capture();assert.equal(media[1].track.stopped,true);
  env.get('retakeChatPhoto').click();await flush();assert.equal(env.camera.file,null);assert.equal(env.urls.revoked.length,1);
  env.camera.close();assert.equal(media[2].track.stopped,true);
});
