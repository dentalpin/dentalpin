import { describe, expect, it } from 'vitest'
import { existsSync, readdirSync, readFileSync } from 'node:fs'
import { relative, resolve } from 'node:path'

/**
 * A `<form>` without `method` submits as GET. Vue's `@submit.prevent` only
 * takes over once the page has hydrated, so a click before that (slow
 * network, JS that failed to load) makes the browser submit natively and put
 * every named field into the URL: browser history, proxy logs, `Referer`.
 * A form that holds a password must therefore declare `method="post"` (#838).
 */

const ROOTS = [
  resolve(__dirname, '../../app'),
  existsSync('/module_layers') ? '/module_layers' : resolve(__dirname, '../../../backend/app/modules')
]

function walk(dir: string, out: string[] = []): string[] {
  if (!existsSync(dir)) return out
  for (const entry of readdirSync(dir, { withFileTypes: true })) {
    if (entry.name === 'node_modules' || entry.name === '.nuxt') continue
    const path = resolve(dir, entry.name)
    if (entry.isDirectory()) walk(path, out)
    else if (entry.name.endsWith('.vue')) out.push(path)
  }
  return out
}

// Opening tag, quote-aware so `=>` inside a handler does not end it early.
const FORM = /<form\b((?:[^>"']|"[^"]*"|'[^']*')*)>/g
// A static `type="password"` or a show/hide toggle such as `:type="show ? 'text' : 'password'"`.
const PASSWORD_INPUT = /(?:^|\s)type="password"|(?:^|\s):type="[^"]*'password'[^"]*"/

describe('every form holding a password submits by POST', () => {
  const forms: { where: string, attrs: string }[] = []
  for (const root of ROOTS) {
    for (const file of walk(root)) {
      const source = readFileSync(file, 'utf8').replace(/<!--[\s\S]*?-->/g, '')
      for (const match of source.matchAll(FORM)) {
        const start = match.index + match[0].length
        const end = source.indexOf('</form>', start)
        if (!PASSWORD_INPUT.test(source.slice(start, end === -1 ? undefined : end))) continue
        const line = source.slice(0, match.index).split('\n').length
        forms.push({ where: `${relative(resolve(root, '..'), file)}:${line}`, attrs: match[1] ?? '' })
      }
    }
  }

  it('finds the login, invitation and setup forms', () => {
    const files = forms.map(({ where }) => where.replace(/:\d+$/, ''))
    expect(files).toEqual(expect.arrayContaining([
      'app/pages/login.vue',
      'app/pages/set-password.vue',
      'app/pages/setup.vue'
    ]))
  })

  it('declares method="post"', () => {
    const offenders = forms
      .filter(({ attrs }) => !/(?:^|\s)method="post"/.test(attrs))
      .map(({ where }) => where)
    expect(offenders).toEqual([])
  })
})
