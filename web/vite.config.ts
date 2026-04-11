import path from "path"
import crypto from "node:crypto"
import { defineConfig, loadEnv } from "vite"
import react from "@vitejs/plugin-react"
import tailwindcss from "@tailwindcss/vite"

/** Keep role strings and port ranges in sync with api/config.py */
function stablePort(projectRoot: string, role: string, lo: number, hi: number): number {
  const digest = crypto.createHash("sha256").update(`${role}:${projectRoot}`).digest()
  const n = digest.readUInt32BE(0)
  return lo + (n % (hi - lo + 1))
}

function parsePort(raw: string | undefined): number | undefined {
  if (raw === undefined || !String(raw).trim()) return undefined
  const n = parseInt(String(raw).trim(), 10)
  return Number.isFinite(n) ? n : undefined
}

export default defineConfig(({ mode }) => {
  const projectRoot = path.resolve(__dirname, "..")
  const env = loadEnv(mode, projectRoot, "")

  const apiPort =
    parsePort(env.DASHBOARD_PORT) ?? stablePort(projectRoot, "backchannel-api", 20000, 29999)
  const webPort =
    parsePort(env.WEB_DEV_PORT) ?? stablePort(projectRoot, "backchannel-web", 31000, 39999)

  return {
    plugins: [react(), tailwindcss()],
    envDir: projectRoot,
    resolve: {
      alias: {
        "@": path.resolve(__dirname, "./src"),
      },
    },
    server: {
      port: webPort,
      proxy: {
        "/api": {
          target: `http://127.0.0.1:${apiPort}`,
          changeOrigin: true,
        },
      },
    },
  }
})
