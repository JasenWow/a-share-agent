/**
 * Workspace — per-WorkItem working directory management.
 *
 * Phase 5: minimal. Each WorkItem gets an isolated directory under the
 * configured root so agent runs don't collide.
 */

import { resolve } from "node:path"

export interface WorkspaceManager {
  /** Return the absolute workspace path for a WorkItem. */
  pathFor(workId: string): string
}

export class LocalWorkspaceManager implements WorkspaceManager {
  constructor(private readonly root: string) {}

  pathFor(workId: string): string {
    return resolve(this.root, workId)
  }
}
