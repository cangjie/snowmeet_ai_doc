// node 16 没有 node:test：拦截 require，按文件顺序串行执行 test(name, fn)
const Module = require('module')
const path = require('path')
const tests = []
let current = ''
const load = Module._load
Module._load = function (request) {
  if (request === 'node:test') return (name, fn) => tests.push({ name, fn, file: current })
  return load.apply(this, arguments)
}
for (const f of process.argv.slice(2)) { current = path.basename(f); require(path.resolve(f)) }
;(async () => {
  let fail = 0
  for (const t of tests) {
    try { await t.fn() } catch (e) { fail++; console.log('FAIL [' + t.file + '] ' + t.name + '\n    ' + String(e && e.message).split('\n').slice(0, 12).join('\n    ')) }
  }
  console.log('pass ' + (tests.length - fail) + ' / ' + tests.length + (fail ? '，失败 ' + fail : ''))
  process.exit(fail ? 1 : 0)
})()
