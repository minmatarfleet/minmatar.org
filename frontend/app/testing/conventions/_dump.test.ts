import { it } from 'vitest'
import { RULES } from './rules'
import { source_files } from './scan'
import { writeFileSync } from 'node:fs'
it('dump', () => {
  const out: string[] = []
  const ids = (process.env.IDS ?? '').split(',')
  for (const r of RULES.filter(r=>ids.includes(r.id))) for (const f of source_files()) for (const h of r.find(f)) out.push(`${r.id}|${f.path}:${h.line}|${h.snippet}`)
  writeFileSync('/tmp/hits.txt', out.join('\n'))
})
