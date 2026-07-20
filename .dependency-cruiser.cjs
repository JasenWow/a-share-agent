/** @type {import('dependency-cruiser').IConfiguration} */
module.exports = {
  forbidden: [
    {
      name: "no-server-to-web",
      comment: "Server must not import from web package.",
      severity: "error",
      from: { path: "^packages/server/src/" },
      to: { path: "^packages/web/" },
    },
    {
      name: "no-web-to-server",
      comment: "Web must not import from server package.",
      severity: "error",
      from: { path: "^packages/web/" },
      to: { path: "^packages/server/" },
    },
    {
      name: "no-core-to-impl",
      comment: "Core package must not depend on server, web, orchestrator, or pi-runtime.",
      severity: "error",
      from: { path: "^packages/core/src/" },
      to: { path: ["^packages/server/", "^packages/web/", "^packages/orchestrator/", "^packages/pi-runtime/"] },
    },
    {
      name: "no-runtime-to-app",
      comment: "Orchestrator/pi-runtime must not import from server or web.",
      severity: "error",
      from: { path: ["^packages/orchestrator/src/", "^packages/pi-runtime/src/"] },
      to: { path: ["^packages/server/", "^packages/web/"] },
    },
  ],
  options: {
    tsPreCompilationDeps: true,
  },
}
