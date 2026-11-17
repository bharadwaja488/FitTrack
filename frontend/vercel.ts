import { createVercelConfig } from './vercelConfig.js'

export const config = createVercelConfig(process.env.RENDER_API_ORIGIN)
