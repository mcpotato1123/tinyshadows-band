/**
 * 用 Node 复刻 game.ux 的节点执行语义，把整部剧本跑一遍，
 * 用来在没有真机的情况下验证数据是否自洽、每条分支是否都能走到结局。
 *
 * 用法：node tools/simulate_galgod.mjs [工程目录]
 */

import fs from 'node:fs'
import path from 'node:path'

const root = process.argv[2] || 'galgod-port'
const SRC = path.join(root, 'src')

// ---- 载入 assets.js（把 export const X = 换成普通赋值后求值）
const assetsSrc = fs.readFileSync(path.join(SRC, 'common', 'assets.js'), 'utf8')
const IMG = JSON.parse(
  assetsSrc.match(/export const IMG = (\[[\s\S]*?\n\])/)[1])
const BG = JSON.parse(
  assetsSrc.match(/export const BG = (\{[\s\S]*?\n\})/)[1])
const SP = JSON.parse(
  assetsSrc.match(/export const SP = (\{[\s\S]*?\n\})/)[1])

const idx = JSON.parse(fs.readFileSync(
  path.join(SRC, 'common', 'story', 'index.txt'), 'utf8'))

let nodes = []
for (const c of idx.chunks) {
  const part = JSON.parse(fs.readFileSync(
    path.join(SRC, c.file.replace('/common/', 'common/')), 'utf8'))
  if (part.length !== c.count) throw new Error(`${c.file} 长度不符`)
  if (c.start !== nodes.length) throw new Error(`${c.file} 起始偏移不符`)
  nodes = nodes.concat(part)
}
const N = nodes.length

console.log(`IMG ${IMG.length} 项 / 剧本 ${N} 节点 / ${idx.chunks.length} 分片 / ${idx.chapters.length} 章`)

// ---- 资源引用检查
const missing = IMG.filter((p) => !fs.existsSync(path.join(SRC, p.replace('/common/', 'common/'))))
console.log(`IMG 指向的文件缺失: ${missing.length}`)
if (missing.length) console.log('  ', missing.slice(0, 5))

// ---- 复刻 step()
function runPath(chooseFn) {
  let pc = 0
  let flags = {}
  let shown = 0
  const visitedChapters = new Set()
  const guard = N * 8
  let steps = 0
  let ending = null

  const chapterOf = (i) => {
    let cur = 0
    for (let k = 0; k < idx.chapters.length; k++) if (i >= idx.chapters[k].start) cur = k
    return cur
  }

  while (steps++ < guard) {
    if (pc >= N) { ending = '(走到数组末尾)'; break }
    const n = nodes[pc]
    visitedChapters.add(chapterOf(pc))

    if (n.t === 's') { shown++; pc++; continue }
    if (n.t === 'j') { pc = n.j; continue }
    if (n.t === 'cj') {
      const v = flags[n.v] || 0
      const y = n.n
      let ok
      if (n.op === '>=') ok = v >= y
      else if (n.op === '<=') ok = v <= y
      else if (n.op === '>') ok = v > y
      else if (n.op === '<') ok = v < y
      else ok = v === y
      pc = ok ? n.j : pc + 1
      continue
    }
    if (n.t === 'f') { flags[n.v] = (flags[n.v] || 0) + n.n; pc++; continue }
    if (n.t === 'sf') { flags[n.v] = n.n; pc++; continue }
    if (n.t === 'o') {
      const opts = n.o.filter((o) => !o.c)
      const pick = chooseFn(opts, n)
      if (!pick) { ending = '(选项为空)'; break }
      pc = pick.j
      continue
    }
    if (n.t === 'e') { ending = n.x; break }
    pc++
  }
  if (steps >= guard) ending = '(超出步数上限，疑似死循环)'
  return { shown, ending, visitedChapters, flags, steps }
}

// 路径 1：每次选项都选第一项
const first = runPath((opts) => opts[0])
console.log(`\n[首选路径] 对白 ${first.shown} 句 步数 ${first.steps}`)
console.log(`           经过章节 ${first.visitedChapters.size}/${idx.chapters.length}  结局: ${first.ending}`)

// 穷举所有选项组合
const choiceNodes = nodes.map((n, i) => (n.t === 'o' ? i : -1)).filter((i) => i >= 0)
console.log(`\n选项节点 ${choiceNodes.length} 个: ` +
  choiceNodes.map((i) => `#${i}(${nodes[i].o.length}项)`).join(' '))

let combos = 1
for (const i of choiceNodes) combos *= nodes[i].o.length
console.log(`组合数 ${combos}，全部跑一遍：`)

let ok = 0
const endings = {}
for (let c = 0; c < combos; c++) {
  let k = c
  const picks = []
  for (const i of choiceNodes) { picks.push(k % nodes[i].o.length); k = Math.floor(k / nodes[i].o.length) }
  let ci = 0
  const r = runPath((opts) => opts[picks[ci++]])
  const good = r.ending && r.ending.indexOf('(') !== 0
  if (good) ok++
  endings[r.ending] = (endings[r.ending] || 0) + 1
  console.log(`  选 ${picks.join(',')} -> 对白 ${r.shown} 句, 章节 ${r.visitedChapters.size}, 结局「${r.ending}」${good ? '' : '  ⚠ 异常'}`)
}
console.log(`\n${ok}/${combos} 条路径正常走到结局`)
console.log('结局分布:', endings)

// ---- 静态统计
const kinds = {}
for (const n of nodes) kinds[n.t] = (kinds[n.t] || 0) + 1
const cgUsed = new Set(nodes.filter((n) => n.cg >= 0).map((n) => n.cg))
const bgUsed = new Set(nodes.filter((n) => n.bg >= 0).map((n) => n.bg))
const spUsed = new Set()
for (const n of nodes) for (const c of (n.cs || [])) spUsed.add(c.i)
console.log(`\n节点类型 ${JSON.stringify(kinds)}`)
console.log(`用到 背景 ${bgUsed.size} / CG ${cgUsed.size} / 立绘 ${spUsed.size}`)
