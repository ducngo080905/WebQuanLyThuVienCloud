const {test} = require('node:test');
const assert = require('node:assert/strict');
const fs = require('node:fs');
const vm = require('node:vm');

function setup() {
  const events = {}, windowEvents = {}, tasks = [], timers = new Map(), dataset = {};
  let next = 0;
  vm.runInNewContext(fs.readFileSync('app/static/page_motion.js', 'utf8'), {
    URL, location: new URL('https://library.test/catalog'),
    document: {documentElement: {dataset}, body: {append() {}},
      createElement: () => ({setAttribute() {}}), addEventListener: (name, callback) => {events[name] = callback;}},
    window: {addEventListener: (name, callback) => {windowEvents[name] = callback;}},
    queueMicrotask: callback => tasks.push(callback),
    setTimeout: (callback, ms) => {timers.set(++next, {callback, ms}); return next;},
    clearTimeout: id => timers.delete(id),
  });
  function click(href, extras = {}) {
    const link = {href, target: extras.target || '', hasAttribute: key => key === 'download' && !!extras.download};
    const event = {button: 0, defaultPrevented: false, ...extras, target: {closest: () => link}};
    events.click(event); return event;
  }
  return {click, events, windowEvents, dataset, timers,
    flush() {while (tasks.length) tasks.shift()();},
    show() {for (const {callback, ms} of [...timers.values()]) if (ms === 120) callback();},
  };
}

test('normal navigation gets delayed feedback without being intercepted', () => {
  const env = setup();
  const event = env.click('https://library.test/my-books'); env.flush();
  assert.equal(event.defaultPrevented, false);
  assert.equal(env.dataset.pageLoading, undefined);
  env.show(); assert.equal(env.dataset.pageLoading, '');
});

test('AJAX handlers and cancelled submissions do not leave navigation feedback', () => {
  const env = setup(), event = env.click('https://library.test/books');
  event.defaultPrevented = true; env.flush(); assert.equal(env.timers.size, 0);
  const submit = {target: {}, defaultPrevented: false};
  env.events.submit(submit); submit.defaultPrevented = true; env.flush();
  assert.equal(env.timers.size, 0);
});

test('anchors, downloads, exports, external and modified clicks remain untouched', () => {
  const env = setup();
  for (const [href, options] of [
    ['https://library.test/catalog#books', {}], ['https://outside.test/books', {}],
    ['https://library.test/download/manual', {}], ['https://library.test/reports?format=xlsx', {}],
    ['https://library.test/file.pdf', {}], ['https://library.test/books', {ctrlKey: true}],
    ['https://library.test/books', {target: '_blank'}], ['https://library.test/books', {download: true}],
  ]) env.click(href, options);
  env.flush(); assert.equal(env.timers.size, 0);
});

test('back/forward restore and abandoned navigation clear feedback and timers', () => {
  const env = setup();
  env.click('https://library.test/books'); env.flush(); env.show();
  env.windowEvents.pageshow();
  assert.equal(env.dataset.pageLoading, undefined); assert.equal(env.timers.size, 0);
  env.click('https://library.test/books'); env.flush(); env.show();
  [...env.timers.values()].find(timer => timer.ms === 15000).callback();
  assert.equal(env.dataset.pageLoading, undefined);
});
