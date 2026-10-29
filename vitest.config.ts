import { defineConfig } from 'vitest/config'

// Unit tests sit next to the code they test; test/ holds the checks of the app as a whole.
export default defineConfig({ test: { include: ['**/*.test.ts'], exclude: ['node_modules/**', 'dist/**'], passWithNoTests: true } })
