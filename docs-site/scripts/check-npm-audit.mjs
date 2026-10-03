/**
 * Plan DEP-01: fail-closed npm audit gate with dated, per-advisory exceptions.
 * Why it works by advisory and not by package, and the conditions an exception
 * must meet: docs/adr/0009-npm-advisory-without-fix.md.
 *
 * Input is an `npm audit --json` report (auditReportVersion 2): produced by
 * running npm audit here, or supplied with --report. Root advisories (objects
 * in `via`; severity info is ignored) are uncovered unless a dated exception in
 * npm-audit-exceptions.json (schema 2) covers that exact advisory:
 *
 * - critical: never excepted
 * - exception advisory id, package and vulnerable_range must match exactly
 * - exception must not be expired; expiry is capped at 31 days from today
 * - advisory severity must not exceed the exception's max_severity
 * - dates must exist in the calendar; added must not be after expires
 * - required exception strings must contain non-whitespace characters
 *
 * Malformed entries, via items and unknown advisory severities fail before coverage.
 * Direct entries above info must contribute a root advisory above info.
 * Input names resolve only to own keys; root identity includes range and severity.
 *
 * Packages flagged only through other packages (string `via` items) carry no
 * exceptions of their own: they are covered only by derivation — every root
 * advisory their via chains reach must be covered (cycles guarded) and every
 * named package must exist in the report, otherwise they fail closed.
 * Exceptions whose advisory is absent from the report are stale and fail the gate.
 *
 * Usage: node scripts/check-npm-audit.mjs [--report <file>] [--exceptions <file>] [--today <YYYY-MM-DD>]
 * Expects: package-lock present; runs `npm audit --json` unless --report is given.
 */
import { spawnSync } from "node:child_process";
import { readFileSync } from "node:fs";
import { dirname, join } from "node:path";
import { fileURLToPath } from "node:url";

const __dirname = dirname(fileURLToPath(import.meta.url));
const ROOT = join(__dirname, "..");
const DEFAULT_EXCEPTIONS_PATH = join(ROOT, "npm-audit-exceptions.json");

const MAX_EXCEPTION_DAYS = 31;
const MIN_REASON_LENGTH = 20;
const SEVERITY_RANK = { info: 0, low: 1, moderate: 2, high: 3, critical: 4 };
const ALLOWED_MAX_SEVERITIES = ["low", "moderate", "high"];
const REQUIRED_STRING_FIELDS = [
  "advisory",
  "package",
  "vulnerable_range",
  "reason",
  "unfreeze",
  "owner",
  "added",
  "expires",
  "max_severity",
];
const ADVISORY_ID_RE = /^GHSA(-[0-9a-z]{4}){3}$/;
const ISO_DATE_RE = /^\d{4}-\d{2}-\d{2}$/;
const CLI_FLAGS = {
  "--report": "report",
  "--exceptions": "exceptions",
  "--today": "today",
};

function todayUtc() {
  return new Date().toISOString().slice(0, 10);
}

function isoDateToDays(iso) {
  const [year, month, day] = iso.split("-").map(Number);
  return Math.round(Date.UTC(year, month - 1, day) / 86400000);
}

function validateCalendarDate(iso, label) {
  const days = isoDateToDays(iso);
  if (!ISO_DATE_RE.test(iso) || new Date(days * 86400000).toISOString().slice(0, 10) !== iso) {
    throw new Error(`${label} must be an existing calendar date, got "${iso}"`);
  }
}

function isPlainObject(value) {
  return value !== null && typeof value === "object" && !Array.isArray(value);
}

function parseArgs(argv) {
  const parsed = { report: null, exceptions: null, today: null };
  for (let i = 0; i < argv.length; i += 1) {
    if (!Object.hasOwn(CLI_FLAGS, argv[i])) {
      throw new Error(`unknown argument: ${argv[i]}`);
    }
    const name = CLI_FLAGS[argv[i]];
    const value = argv[i + 1];
    if (value === undefined) {
      throw new Error(`missing value for ${argv[i]}`);
    }
    parsed[name] = value;
    i += 1;
  }
  if (parsed.today !== null && !ISO_DATE_RE.test(parsed.today)) {
    throw new Error(`--today expects YYYY-MM-DD, got "${parsed.today}"`);
  }
  if (parsed.today !== null) {
    validateCalendarDate(parsed.today, "--today");
  }
  return parsed;
}

function loadRegister(filePath) {
  const register = JSON.parse(readFileSync(filePath, "utf8"));
  if (register === null || typeof register !== "object" || Array.isArray(register)) {
    throw new Error("exceptions file must contain a JSON object");
  }
  return register;
}

function exceptionLabel(exception, index) {
  const advisory =
    exception !== null && typeof exception === "object" && typeof exception.advisory === "string"
      ? exception.advisory
      : String(exception && exception.advisory);
  const pkg =
    exception !== null && typeof exception === "object" && typeof exception.package === "string"
      ? exception.package
      : String(exception && exception.package);
  return `exceptions[${index}] (advisory "${advisory}" in "${pkg}")`;
}

function validateRegister(register, today) {
  if (register.schema_version !== 2) {
    throw new Error(
      `unsupported schema_version=${JSON.stringify(register.schema_version)} (expected 2)`,
    );
  }
  if (!Array.isArray(register.exceptions)) {
    throw new Error("exceptions must be an array");
  }
  const todayDays = isoDateToDays(today);
  const seenAdvisories = new Map();
  register.exceptions.forEach((exception, index) => {
    const label = exceptionLabel(exception, index);
    if (exception === null || typeof exception !== "object" || Array.isArray(exception)) {
      throw new Error(`${label}: entry must be an object`);
    }
    for (const field of REQUIRED_STRING_FIELDS) {
      if (typeof exception[field] !== "string" || exception[field].trim().length === 0) {
        throw new Error(`${label}: field "${field}" must be a non-empty string`);
      }
    }
    if (!ADVISORY_ID_RE.test(exception.advisory)) {
      throw new Error(
        `${label}: field "advisory" must match ^GHSA(-[0-9a-z]{4}){3}$, got "${exception.advisory}"`,
      );
    }
    for (const field of ["added", "expires"]) {
      if (!ISO_DATE_RE.test(exception[field])) {
        throw new Error(
          `${label}: field "${field}" must match YYYY-MM-DD, got "${exception[field]}"`,
        );
      }
      validateCalendarDate(exception[field], `${label}: field "${field}"`);
    }
    if (exception.added > exception.expires) {
      throw new Error(`${label}: field "added" must not be after "expires"`);
    }
    if (!ALLOWED_MAX_SEVERITIES.includes(exception.max_severity)) {
      throw new Error(
        `${label}: field "max_severity" must be one of low, moderate, high, got "${exception.max_severity}"`,
      );
    }
    if (exception.reason.trim().length < MIN_REASON_LENGTH) {
      throw new Error(
        `${label}: field "reason" must be at least ${MIN_REASON_LENGTH} characters, ` +
          `got ${exception.reason.trim().length}`,
      );
    }
    if (seenAdvisories.has(exception.advisory)) {
      throw new Error(
        `${label}: duplicate advisory "${exception.advisory}" ` +
          `(already used by exceptions[${seenAdvisories.get(exception.advisory)}])`,
      );
    }
    seenAdvisories.set(exception.advisory, index);
    const expiresInDays = isoDateToDays(exception.expires) - todayDays;
    if (expiresInDays > MAX_EXCEPTION_DAYS) {
      throw new Error(
        `${label}: field "expires" (${exception.expires}) is ${expiresInDays} days after ${today}; ` +
          `at most ${MAX_EXCEPTION_DAYS} days is allowed`,
      );
    }
  });
  return register.exceptions;
}

function runAuditJson() {
  const result = spawnSync("npm", ["audit", "--json"], {
    cwd: ROOT,
    encoding: "utf8",
    shell: true,
    maxBuffer: 20 * 1024 * 1024,
  });
  // npm audit exits non-zero when vulns exist; stdout is still parsed.
  const stdout = result.stdout || "";
  if (!stdout.trim()) {
    const detail = result.stderr || (result.error && result.error.message) || "";
    throw new Error(`npm audit produced no JSON (status=${result.status}): ${detail}`);
  }
  return validateReport(JSON.parse(stdout), "npm audit --json");
}

function validateReport(report, origin) {
  // An npm failure prints `{"error": ...}` with no vulnerabilities: that is not a clean audit.
  if (report === null || typeof report !== "object" || Array.isArray(report)) {
    throw new Error(`audit report from ${origin} is not a JSON object`);
  }
  if (report.auditReportVersion !== 2) {
    // npm's own failure documents carry `error` (`code`, `summary`) or `message` and no
    // report; repeat what npm said, so a registry outage is not read as a format change.
    const npmSaid =
      (report.error && (report.error.summary || report.error.code)) || report.message;
    const hint = npmSaid ? `; npm said: ${npmSaid}` : "";
    throw new Error(
      `audit report from ${origin} has auditReportVersion=${JSON.stringify(report.auditReportVersion)} ` +
        `(expected 2)${hint}`,
    );
  }
  const vulns = report.vulnerabilities;
  if (vulns === null || typeof vulns !== "object" || Array.isArray(vulns)) {
    throw new Error(`audit report from ${origin} has no vulnerabilities object`);
  }
  for (const [entryName, entry] of Object.entries(vulns)) {
    const label = `audit report from ${origin}: entry "${entryName}"`;
    if (!isPlainObject(entry)) {
      throw new Error(`${label} must be an object`);
    }
    // A missing via is an empty one (rejected below unless the entry is info); any
    // other type could hide advisories from every later pass.
    if (entry.via !== undefined && !Array.isArray(entry.via)) {
      throw new Error(`${label} via must be an array`);
    }
    viaItems(entry).forEach((item, index) => {
      if (typeof item === "string" && item.trim().length > 0) {
        return;
      }
      if (!isPlainObject(item)) {
        throw new Error(`${label} via[${index}] must be a non-empty string or an object`);
      }
      const severity = typeof item.severity === "string" ? item.severity.toLowerCase() : "";
      if (!Object.hasOwn(SEVERITY_RANK, severity)) {
        throw new Error(`${label} via[${index}] has unknown severity: ${JSON.stringify(item.severity)}`);
      }
    });
  }
  return report;
}

function loadReport(filePath) {
  return validateReport(JSON.parse(readFileSync(filePath, "utf8")), filePath);
}

function viaItems(entry) {
  return Array.isArray(entry && entry.via) ? entry.via : [];
}

function hasStringVia(entry) {
  return viaItems(entry).some((item) => typeof item === "string");
}

function advisoryId(viaItem) {
  if (typeof viaItem.url === "string" && viaItem.url.trim() !== "") {
    const segments = viaItem.url.split("/").filter((segment) => segment.length > 0);
    if (segments.length > 0 && segments[segments.length - 1].trim() !== "") {
      return segments[segments.length - 1];
    }
  }
  // No usable url: identified by source only; can never be covered by an exception.
  return `source:${viaItem.source}`;
}

function rootKeyFor(viaItem, entryName) {
  const pkg = typeof viaItem.name === "string" && viaItem.name !== "" ? viaItem.name : entryName;
  const range = typeof viaItem.range === "string" ? viaItem.range : "";
  const severity = typeof viaItem.severity === "string" ? viaItem.severity.toLowerCase() : "";
  return JSON.stringify([advisoryId(viaItem), pkg, range, severity]);
}

function collectRootAdvisories(vulnerabilities) {
  // One entry per (advisory id, package, range, severity); severity info is ignored.
  const rootsByKey = new Map();
  for (const [entryName, entry] of Object.entries(vulnerabilities)) {
    for (const item of viaItems(entry)) {
      if (item === null || typeof item !== "object") {
        continue; // string items are derivation edges, not root advisories
      }
      const severity = typeof item.severity === "string" ? item.severity.toLowerCase() : "";
      if (severity === "info") {
        continue;
      }
      const key = rootKeyFor(item, entryName);
      if (!rootsByKey.has(key)) {
        rootsByKey.set(key, {
          key,
          id: advisoryId(item),
          package: typeof item.name === "string" && item.name !== "" ? item.name : entryName,
          severity,
          range: typeof item.range === "string" ? item.range : "",
        });
      }
    }
  }
  return rootsByKey;
}

function coverRootAdvisory(root, exceptionsByAdvisory, today) {
  if (root.severity === "critical") {
    return { covered: false, reason: "critical severity is never excepted" };
  }
  const exception = exceptionsByAdvisory.get(root.id);
  if (exception === undefined) {
    return { covered: false, reason: `no exception for advisory ${root.id} in ${root.package}` };
  }
  if (exception.package !== root.package) {
    return {
      covered: false,
      reason: `exception ${root.id} names package "${exception.package}" ` +
        `but the advisory is against "${root.package}"`,
    };
  }
  if (exception.vulnerable_range !== root.range) {
    return {
      covered: false,
      reason: `vulnerable_range mismatch: exception says "${exception.vulnerable_range}", ` +
        `advisory says "${root.range}" (a fixed release may exist)`,
    };
  }
  if (exception.expires < today) {
    return { covered: false, reason: `exception expired on ${exception.expires} (today is ${today})` };
  }
  const advisoryRank = Object.hasOwn(SEVERITY_RANK, root.severity) ? SEVERITY_RANK[root.severity] : 99;
  const maxRank = Object.hasOwn(SEVERITY_RANK, exception.max_severity)
    ? SEVERITY_RANK[exception.max_severity]
    : -1;
  if (advisoryRank > maxRank) {
    return {
      covered: false,
      reason: `advisory severity "${root.severity}" is above exception ` +
        `max_severity "${exception.max_severity}"`,
    };
  }
  return { covered: true, reason: exception.reason, expires: exception.expires };
}

function collectReachedRoots(vulnerabilities, entryName, rootsByKey) {
  const reached = new Set();
  const missing = [];
  const visited = new Set([entryName]); // cycle guard
  const pending = [entryName];
  while (pending.length > 0) {
    const current = pending.pop();
    if (!Object.hasOwn(vulnerabilities, current)) {
      missing.push(current);
      continue;
    }
    for (const item of viaItems(vulnerabilities[current])) {
      if (typeof item === "string") {
        if (visited.has(item)) {
          continue;
        }
        visited.add(item);
        if (!Object.hasOwn(vulnerabilities, item)) {
          missing.push(item); // report cannot be explained: fail closed
        } else {
          pending.push(item);
        }
      } else if (item !== null && typeof item === "object") {
        const root = rootsByKey.get(rootKeyFor(item, current));
        if (root !== undefined) {
          reached.add(root); // info advisories are not collected, so they are never reached
        }
      }
    }
  }
  return { reached, missing };
}

function coverDerivedEntry(vulnerabilities, entryName, rootsByKey, coverageByKey) {
  const { reached, missing } = collectReachedRoots(vulnerabilities, entryName, rootsByKey);
  if (missing.length > 0) {
    return {
      covered: false,
      reason: `via names package(s) with no entry in the report: ${missing.join(", ")} ` +
        "(fail closed: the report cannot be explained)",
    };
  }
  if (reached.size === 0) {
    return { covered: false, reason: "no root advisory reached through via chains" };
  }
  const uncoveredRoots = [...reached].filter((root) => !coverageByKey.get(root.key).covered);
  if (uncoveredRoots.length > 0) {
    return {
      covered: false,
      reason: `reached uncovered advisory(ies): ${uncoveredRoots
        .map((root) => `${root.id} in ${root.package}`)
        .join(", ")}`,
    };
  }
  return {
    covered: true,
    reason: `covered by derivation from: ${[...reached]
      .map((root) => `${root.id} in ${root.package}`)
      .join(", ")}`,
  };
}

function main() {
  const args = parseArgs(process.argv.slice(2));
  const today = args.today === null ? todayUtc() : args.today;
  const exceptionsPath = args.exceptions === null ? DEFAULT_EXCEPTIONS_PATH : args.exceptions;

  const register = loadRegister(exceptionsPath);
  const exceptions = validateRegister(register, today);
  const audit = args.report === null ? runAuditJson() : loadReport(args.report);
  const vulnerabilities = audit.vulnerabilities;
  const metadata = (audit.metadata && audit.metadata.vulnerabilities) || {};

  const rootsByKey = collectRootAdvisories(vulnerabilities);
  const exceptionsByAdvisory = new Map(exceptions.map((exception) => [exception.advisory, exception]));

  const covered = [];
  const uncovered = [];
  const coverageByKey = new Map();
  for (const root of rootsByKey.values()) {
    const status = coverRootAdvisory(root, exceptionsByAdvisory, today);
    coverageByKey.set(root.key, status);
    if (status.covered) {
      covered.push({
        advisory: root.id,
        package: root.package,
        severity: root.severity,
        reason: status.reason,
        expires: status.expires,
      });
    } else {
      uncovered.push({
        advisory: root.id,
        package: root.package,
        severity: root.severity,
        reason: status.reason,
      });
    }
  }

  for (const [entryName, entry] of Object.entries(vulnerabilities)) {
    if (!isPlainObject(entry)) {
      throw new Error(`entry "${entryName}" must be an object`);
    }
    const severity = typeof entry.severity === "string" ? entry.severity.toLowerCase() : "unknown";
    if (severity === "info") {
      continue; // info is ignored
    }
    if (viaItems(entry).length === 0) {
      uncovered.push({
        advisory: null,
        package: entryName,
        severity,
        reason: "entry has no via items (fail closed: the report cannot be explained)",
      });
      continue;
    }
    if (!hasStringVia(entry)) {
      const contributedRoot = viaItems(entry).some((item) => rootsByKey.has(rootKeyFor(item, entryName)));
      if (!contributedRoot) {
        uncovered.push({
          advisory: null,
          package: entryName,
          severity,
          reason: "no root advisory above info (the report cannot be explained)",
        });
      }
      continue; // flagged directly: handled above as root advisories
    }
    const status = coverDerivedEntry(vulnerabilities, entryName, rootsByKey, coverageByKey);
    const item = { advisory: null, package: entryName, severity, reason: status.reason };
    if (status.covered) {
      covered.push(item);
    } else {
      uncovered.push(item);
    }
  }

  const rootAdvisoryIds = new Set([...rootsByKey.values()].map((root) => root.id));
  const stale = exceptions
    .filter((exception) => !rootAdvisoryIds.has(exception.advisory))
    .map((exception) => ({
      advisory: exception.advisory,
      package: exception.package,
      expires: exception.expires,
      reason: `advisory ${exception.advisory} is not among this report's root advisories; ` +
        "remove it from npm-audit-exceptions.json",
    }));

  const summary = {
    date: today,
    metadata,
    covered_count: covered.length,
    uncovered_count: uncovered.length,
    stale_count: stale.length,
    exceptions_file: exceptionsPath,
  };
  console.log(JSON.stringify({ summary, covered, uncovered, stale }, null, 2));

  if (uncovered.length > 0 || stale.length > 0) {
    const uncoveredAdvisories = uncovered.filter((item) => item.advisory !== null).length;
    const uncoveredPackages = uncovered.length - uncoveredAdvisories;
    console.error(
      `DEP-01 FAIL: ${uncoveredAdvisories} advisory(ies) and ${uncoveredPackages} package(s) uncovered, ` +
        `${stale.length} stale exception(s)`,
    );
    for (const item of uncovered) {
      const kind = item.advisory === null ? "package (flagged via others)" : `advisory ${item.advisory}`;
      console.error(`- uncovered ${kind} in ${item.package}: ${item.reason}`);
    }
    for (const item of stale) {
      console.error(`- stale exception ${item.advisory} in ${item.package}: ${item.reason}`);
    }
    process.exitCode = 1;
    return;
  }

  const applied = covered.filter((item) => item.advisory !== null);
  if (applied.length > 0) {
    const names = applied
      .map((item) => `${item.advisory} in ${item.package} until ${item.expires}`)
      .join("; ");
    console.error(`DEP-01 PASS: nothing uncovered; exception(s) applied: ${names}`);
  } else {
    console.error("DEP-01 PASS: the audit reported nothing uncovered (no exceptions needed).");
  }
  process.exitCode = 0;
}

try {
  main();
} catch (err) {
  console.error(`DEP-01 FAIL: ${err && err.message ? err.message : err}`);
  process.exitCode = 1;
}
