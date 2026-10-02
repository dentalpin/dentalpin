// Write `modules.json` listing every module layer under <layers-root>.
//
//   node scripts/modules-json.mjs <layers-root> [--prefix <path-prefix>]
//
// The backend regenerates this file at runtime as modules are installed;
// build/CI contexts have no backend, so they bake every layer instead:
//   Dockerfile.prod  → /module_layers            (COPY of backend/app/modules)
//   CI e2e           → $GITHUB_WORKSPACE/backend/app/modules
//   CI typecheck     → ./module_layers           (symlink, same trick as ESLint)
//
// `--prefix` decouples the emitted paths from the scanned directory: the
// modules-json-freshness CI job scans backend/app/modules on the runner
// but emits the canonical committed form (`/module_layers/...`, the
// Docker mount) so the snapshot can be diffed against git (#264).
import { existsSync, readdirSync, statSync, writeFileSync } from 'node:fs'
import { join } from 'node:path'

const args = process.argv.slice(2)
const prefixIdx = args.indexOf('--prefix')
const prefix = prefixIdx === -1 ? null : args[prefixIdx + 1]
const positional = args.filter((_, i) => prefixIdx === -1 || (i !== prefixIdx && i !== prefixIdx + 1))
const root = positional[0]
if (!root || (prefixIdx !== -1 && !prefix)) {
  console.error('usage: node scripts/modules-json.mjs <layers-root> [--prefix <path-prefix>]')
  process.exit(1)
}
const base = prefix ?? root
const names = readdirSync(root)
  .filter(name => existsSync(`${root}/${name}/frontend/nuxt.config.ts`))
  .sort()
// Fail loudly on zero layers (#544): an empty directory would emit an
// empty modules.json and every layer-enumerating gate would pass
// vacuously. (A file in place of the directory already throws ENOTDIR.)
if (names.length === 0) {
  console.error(`modules-json: no layers with frontend/nuxt.config.ts under ${root} - refusing to write an empty modules.json`)
  process.exit(1)
}
// Route paths each layer contributes (issue #326): walk pages/ and turn
// files into route patterns ("[id]" → ":param"). The module-gate route
// middleware uses these to 404 pages of baked-but-uninstalled modules.
function routesOf(name) {
  const pagesDir = join(root, name, 'frontend/pages')
  if (!existsSync(pagesDir)) return []
  const routes = []
  const walk = (dir, segs) => {
    for (const entry of readdirSync(dir).sort()) {
      const full = join(dir, entry)
      if (statSync(full).isDirectory()) {
        walk(full, [...segs, entry])
      } else if (entry.endsWith('.vue')) {
        const leaf = entry.slice(0, -4)
        const parts = leaf === 'index' ? segs : [...segs, leaf]
        routes.push('/' + parts.map(p => p.replace(/\[(\.\.\.)?([^\]]+)\]/g, ':$2')).join('/'))
      }
    }
  }
  walk(pagesDir, [])
  return routes
}

const modules = names.map(name => ({
  name,
  path: `${base}/${name}/frontend`,
  routes: routesOf(name)
}))
writeFileSync(
  'modules.json',
  JSON.stringify({ layers: modules.map(m => m.path), modules, version: 1 }, null, 2) + '\n'
)
console.log('modules.json:', names.join(', '))
