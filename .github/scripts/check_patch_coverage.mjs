// SPDX-FileCopyrightText: 2026 Arnaldo Mendes Pires Junior
// SPDX-License-Identifier: MIT

import { readFileSync, existsSync } from "node:fs";
import { execSync } from "node:child_process";
import { resolve } from "node:path";

function parseArgs(argv) {
  const out = {};
  for (let i = 2; i < argv.length; i += 1) {
    const key = argv[i];
    const value = argv[i + 1];
    if (!key.startsWith("--") || value === undefined) {
      continue;
    }
    out[key.slice(2)] = value;
    i += 1;
  }
  return out;
}

function normalizePath(pathText, workspace) {
  const raw = pathText.replaceAll("\\", "/");
  const ws = workspace.replaceAll("\\", "/").replace(/\/$/, "");
  if (raw.startsWith(`${ws}/`)) {
    return raw.slice(ws.length + 1);
  }

  const marker = `/${ws.split("/").at(-1)}/`;
  const idx = raw.indexOf(marker);
  if (idx !== -1) {
    return raw.slice(idx + marker.length);
  }

  return raw.replace(/^\.\//, "");
}

function readDiff(baseSha, includePaths) {
  const quotedPaths = includePaths.map((p) => `"${p}"`).join(" ");
  const cmd = `git diff --unified=0 ${baseSha}...HEAD -- ${quotedPaths}`;
  return execSync(cmd, { encoding: "utf8" });
}

function handleFileHeader(line, workspace, changed) {
  const fileMatch = line.match(/^\+\+\+ b\/(.+)$/);
  if (!fileMatch) {
    return { handled: false, currentFile: null };
  }
  if (fileMatch[1] === "/dev/null") {
    return { handled: true, currentFile: null };
  }
  const currentFile = normalizePath(fileMatch[1], workspace);
  if (!changed.has(currentFile)) {
    changed.set(currentFile, new Set());
  }
  return { handled: true, currentFile };
}

function addHunkLines(line, fileSet) {
  const hunkMatch = line.match(/^@@ -\d+(?:,\d+)? \+(\d+)(?:,(\d+))? @@/);
  if (!hunkMatch) {
    return;
  }

  const start = Number.parseInt(hunkMatch[1], 10);
  const len = Number.parseInt(hunkMatch[2] ?? "1", 10);
  if (len <= 0) {
    return;
  }

  for (let lineNo = start; lineNo < start + len; lineNo += 1) {
    fileSet.add(lineNo);
  }
}

function parseChangedLines(diffText, workspace) {
  const changed = new Map();
  let currentFile = null;

  for (const line of diffText.split(/\r?\n/)) {
    const header = handleFileHeader(line, workspace, changed);
    if (header.handled) {
      currentFile = header.currentFile;
      continue;
    }

    if (!currentFile) {
      continue;
    }

    addHunkLines(line, changed.get(currentFile));
  }

  return changed;
}

function parseLcov(reportText, workspace) {
  const cov = new Map();
  let currentFile = null;

  for (const line of reportText.split(/\r?\n/)) {
    if (line.startsWith("SF:")) {
      currentFile = normalizePath(line.slice(3), workspace);
      if (!cov.has(currentFile)) {
        cov.set(currentFile, new Map());
      }
      continue;
    }

    if (line.startsWith("DA:") && currentFile) {
      const [lineNoText, hitsText] = line.slice(3).split(",");
      const lineNo = Number.parseInt(lineNoText, 10);
      const hits = Number.parseInt(hitsText, 10);
      cov.get(currentFile).set(lineNo, Number.isNaN(hits) ? 0 : hits);
      continue;
    }

    if (line === "end_of_record") {
      currentFile = null;
    }
  }

  return cov;
}

function parseCobertura(reportText, workspace) {
  const cov = new Map();
  let currentFile = null;

  for (const line of reportText.split(/\r?\n/)) {
    const classMatch = line.match(/<class[^>]*filename="([^"]+)"/);
    if (classMatch) {
      currentFile = normalizePath(classMatch[1], workspace);
      if (!cov.has(currentFile)) {
        cov.set(currentFile, new Map());
      }
    }

    const lineMatch = line.match(/<line[^>]*number="(\d+)"[^>]*hits="([0-9.]+)"/);
    if (lineMatch && currentFile) {
      const lineNo = Number.parseInt(lineMatch[1], 10);
      const hits = Math.trunc(Number.parseFloat(lineMatch[2]));
      cov.get(currentFile).set(lineNo, Number.isNaN(hits) ? 0 : hits);
    }
  }

  return cov;
}

function startsWithAnyPrefix(filePath, includePaths) {
  return includePaths.some((p) => filePath.startsWith(`${p.replace(/\/$/, "")}/`));
}

function parseIncludePaths(paths) {
  return paths
    .split(",")
    .map((x) => x.trim().replace(/^\/+|\/+$/g, ""))
    .filter(Boolean);
}

function validateArgs(args) {
  const baseSha = args["base-sha"];
  const paths = args.paths;
  const reportFormat = args["report-format"];
  const reportFile = args["report-file"];
  const threshold = Number.parseFloat(args.threshold);
  const label = args.label;

  if (!baseSha || !paths || !reportFormat || !reportFile || Number.isNaN(threshold) || !label) {
    throw new Error("Missing required arguments");
  }

  const includePaths = parseIncludePaths(paths);
  if (includePaths.length === 0) {
    throw new Error("No include paths provided");
  }

  return { baseSha, includePaths, reportFormat, reportFile, threshold, label };
}

function loadCoverage(reportFormat, reportPath, workspace) {
  if (!existsSync(reportPath)) {
    return null;
  }
  const reportText = readFileSync(reportPath, "utf8");
  return reportFormat === "lcov"
    ? parseLcov(reportText, workspace)
    : parseCobertura(reportText, workspace);
}

function computePatchCoverage(changed, cov, includePaths) {
  let total = 0;
  let covered = 0;
  const missing = [];

  for (const [filePath, lines] of changed.entries()) {
    if (!startsWithAnyPrefix(filePath, includePaths)) {
      continue;
    }
    const fileCov = cov.get(filePath) ?? new Map();
    for (const lineNo of [...lines].sort((a, b) => a - b)) {
      total += 1;
      const hits = fileCov.get(lineNo) ?? 0;
      if (hits > 0) {
        covered += 1;
      } else if (!fileCov.has(lineNo)) {
        missing.push(`${filePath}:${lineNo}`);
      }
    }
  }

  return { total, covered, missing };
}

function printMissing(missing) {
  if (missing.length === 0) {
    return;
  }
  console.log("::warning::Changed lines not found in coverage report (counted as uncovered):");
  console.log(missing.slice(0, 30).join("\n"));
  if (missing.length > 30) {
    console.log(`... and ${missing.length - 30} more`);
  }
}

function main() {
  let cfg;
  try {
    cfg = validateArgs(parseArgs(process.argv));
  } catch (err) {
    console.error(`::error::${err.message}`);
    process.exit(1);
  }

  const workspace = process.cwd();
  const diffText = readDiff(cfg.baseSha, cfg.includePaths);
  const changed = parseChangedLines(diffText, workspace);

  const reportPath = resolve(workspace, cfg.reportFile);
  const cov = loadCoverage(cfg.reportFormat, reportPath, workspace);
  if (cov === null) {
    console.error(`::error::${cfg.label}: coverage report not found: ${cfg.reportFile}`);
    process.exit(1);
  }

  const { total, covered, missing } = computePatchCoverage(changed, cov, cfg.includePaths);

  if (total === 0) {
    console.log(`${cfg.label} patch coverage: N/A (no changed lines in ${cfg.includePaths.join(", ")})`);
    process.exit(0);
  }

  const pct = (covered / total) * 100;
  console.log(`${cfg.label} patch coverage: ${pct.toFixed(1)}%  (${covered} / ${total} changed lines)`);

  printMissing(missing);

  if (pct + 1e-9 < cfg.threshold) {
    console.error(
      `::error::${cfg.label} patch coverage below ${cfg.threshold.toFixed(1)}% threshold (got ${pct.toFixed(1)}%)`,
    );
    process.exit(1);
  }
}

main();
