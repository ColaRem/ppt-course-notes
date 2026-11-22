#!/usr/bin/env node
/**
 * Install the ppt-course-notes skill into a skills directory.
 *
 * Usage:
 *   ppt-course-notes install --target dsh
 *   ppt-course-notes install --target claude
 *   ppt-course-notes install --target project
 *   ppt-course-notes install --dir <exact destination>
 */

import { cpSync, existsSync, mkdirSync, rmSync, statSync } from "node:fs";
import { homedir } from "node:os";
import path from "node:path";
import { fileURLToPath } from "node:url";

const packageRoot = path.resolve(
  path.dirname(fileURLToPath(import.meta.url)),
  ".."
);
const source = path.join(packageRoot, ".dsh", "skills", "ppt-course-notes");
const skillName = "ppt-course-notes";

function fail(message) {
  console.error(`[error] ${message}`);
  process.exit(2);
}

function usage() {
  console.log(`Install the ${skillName} agent skill.

Usage:
  ppt-course-notes install [options]

Options:
  --target <dsh|claude|project>   Install location (default: dsh)
                                  dsh      $DSH_HOME/skills or ~/.dsh/skills
                                  claude   ~/.claude/skills
                                  project  ./.claude/skills
  --dir <path>                    Exact destination directory
  --force                         Replace an existing installation
  -h, --help                      Show this help

Examples:
  npx ${skillName} install --target dsh
  npx ${skillName} install --target claude
  npx ${skillName} install --target project --force
`);
}

function destinationFor(target, explicitDir) {
  if (explicitDir) return path.resolve(explicitDir);
  if (target === "dsh") {
    const dshHome = process.env.DSH_HOME || path.join(homedir(), ".dsh");
    return path.join(dshHome, "skills", skillName);
  }
  if (target === "claude") {
    return path.join(homedir(), ".claude", "skills", skillName);
  }
  if (target === "project") {
    return path.join(process.cwd(), ".claude", "skills", skillName);
  }
  fail(`unknown target: ${target}`);
}

function assertSafeDestination(destination) {
  const parsed = path.parse(destination);
  if (destination === parsed.root) {
    fail(`refusing to install into a filesystem root: ${destination}`);
  }
  if (destination === homedir()) {
    fail("refusing to install directly into the home directory");
  }
  if (destination === source || destination.startsWith(source + path.sep)) {
    fail("refusing to install inside the package source directory");
  }
  if (source.startsWith(destination + path.sep)) {
    fail("refusing to install into a parent of the package source directory");
  }
}

function main() {
  const args = process.argv.slice(2);
  if (args.length === 0 || args.includes("-h") || args.includes("--help")) {
    usage();
    return;
  }
  if (args[0] !== "install") {
    fail(`unknown command: ${args[0]}`);
  }

  let target = "dsh";
  let explicitDir = "";
  let force = false;

  for (let index = 1; index < args.length; index += 1) {
    const arg = args[index];
    if (arg === "--target") {
      target = args[index + 1];
      index += 1;
      if (!["dsh", "claude", "project"].includes(target)) {
        fail(`invalid --target: ${target || "(empty)"}`);
      }
    } else if (arg === "--dir") {
      explicitDir = args[index + 1];
      index += 1;
      if (!explicitDir) fail("--dir requires a path");
    } else if (arg === "--force") {
      force = true;
    } else {
      fail(`unknown option: ${arg}`);
    }
  }

  if (!existsSync(path.join(source, "SKILL.md"))) {
    fail(`skill source is missing: ${source}`);
  }

  const destination = destinationFor(target, explicitDir);
  assertSafeDestination(destination);

  if (existsSync(destination)) {
    if (!force) {
      fail(
        `destination already exists: ${destination}\n` +
          "Use --force to replace it."
      );
    }
    if (!statSync(destination).isDirectory()) {
      fail(`destination is not a directory: ${destination}`);
    }
    rmSync(destination, { recursive: true, force: true });
  }

  mkdirSync(path.dirname(destination), { recursive: true });
  cpSync(source, destination, {
    recursive: true,
    filter: (file) => {
      const base = path.basename(file);
      return base !== "__pycache__" && !base.endsWith(".pyc");
    },
  });

  console.log(`Installed ${skillName} -> ${destination}`);
  console.log("Open a new agent session (or reload skills) to use it.");
}

main();
