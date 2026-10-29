import { applyMigrations } from './apply-migrations'
import { connect } from './connection'

// Applies the migrations not applied yet to DATABASE_URL. Run it before a new version serves, while nothing else writes.

const sql = connect({ max: 1 })
const applied = await applyMigrations(sql)
for (const file of applied) console.log(`applied ${file}`)

await sql.end()
