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
      name: "no-shared-to-impl",
      comment: "Shared package must not depend on server or web.",
      severity: "error",
      from: { path: "^packages/shared/src/" },
      to: { path: ["^packages/server/", "^packages/web/"] },
    },
  ],
  options: {
    tsPreCompilationDeps: true,
  },
}
