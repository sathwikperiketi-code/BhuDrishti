import { mkdir, readFile, writeFile } from 'node:fs/promises'
import { resolve } from 'node:path'
import openapiTS, { astToString } from 'openapi-typescript'

const openapiUrl = process.env.OPENAPI_URL || 'http://127.0.0.1:8000/openapi.json'
const openapiFile = process.env.OPENAPI_FILE
const outputPath = resolve('src/types/api.generated.ts')

try {
  const schema = openapiFile
    ? JSON.parse(await readFile(resolve(openapiFile), 'utf8'))
    : await (async () => {
      const response = await fetch(openapiUrl)
      if (!response.ok) throw new Error(`OpenAPI endpoint returned HTTP ${response.status}`)
      return response.json()
    })()
  const ast = await openapiTS(schema)
  await mkdir(resolve('src/types'), { recursive: true })
  await writeFile(outputPath, `// Generated from ${openapiFile || openapiUrl}. Do not edit by hand.\n${astToString(ast)}`)
  process.stdout.write(`Generated ${outputPath}\n`)
} catch (error) {
  const message = error instanceof Error ? error.message : String(error)
  process.stderr.write(`Could not generate API types: ${message}\n`)
  process.exitCode = 1
}
