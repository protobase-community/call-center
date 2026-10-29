import { spawnSync } from 'node:child_process'
import { configExports } from '@protobase/server'
import * as config from '../config'

// Runs `protobase doctor` against DATABASE_URL: the check Protobase Cloud runs before it deploys a change, such as an
// index that every filterable or sortable field needs. Doctor refuses a config without resources, so until the first
// change exports one from config/index.ts there is nothing to check and this passes.

if (configExports(config).resources.length === 0) {
  console.log('doctor: no resources in config/index.ts yet, so there is nothing to check')
  process.exit(0)
}

const doctor = spawnSync('protobase', ['doctor'], { stdio: 'inherit' })
if (doctor.error) throw doctor.error
process.exit(doctor.status ?? 1)
