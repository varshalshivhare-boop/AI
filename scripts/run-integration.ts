import { runEndToEndVerification } from '../packages/testing/end-to-end-verifier.ts';
import type { StepResult } from '../packages/testing/end-to-end-verifier.ts';

// ── Sandbox: mock global fetch for Telegram API calls ──────────────────────
global.fetch = async (url: RequestInfo | URL, _init?: RequestInit) => {
  const urlStr = String(url);
  if (urlStr.includes('telegram.org')) {
    return {
      ok: true,
      status: 200,
      json: async () => ({ ok: true, result: { message_id: 12345 } })
    } as Response;
  }
  return { ok: true, status: 200, json: async () => ({}) } as Response;
};

function separator(char = '─', width = 76) { return char.repeat(width); }

function printStepResult(r: StepResult) {
  const icon = r.status === 'PASS' ? '✅ PASS' : '❌ FAIL';
  console.log(`\n${separator()}`);
  console.log(`  [STEP ${r.step}] ${icon}`);
  console.log(`  ${r.description}`);
  console.log(separator('·'));
  console.log(`  Owner    : ${r.owner}`);
  console.log(`  Boundary : ${r.boundary}`);
  console.log(`  Evidence :\n`);
  // Wrap evidence at 72 chars for readability
  const evidenceParts = r.evidence.split('. ').filter(Boolean);
  for (const part of evidenceParts) {
    console.log(`    • ${part.trim().replace(/\.$/, '')}.`);
  }
  if (r.violations && r.violations.length > 0) {
    console.log(`\n  ⚠  Violations (${r.violations.length}):`);
    for (const v of r.violations) {
      console.log(`    ✗ ${v}`);
    }
  }
}

async function main() {
  console.log(`\n${separator('═')}`);
  console.log('  QUANTMIND AI — PHASE 4 END-TO-END INTEGRATION VERIFICATION');
  console.log('  Integration Lead: verifying service seams against contracts.');
  console.log(`${separator('═')}\n`);

  const results = await runEndToEndVerification();

  for (const r of results) {
    printStepResult(r);
  }

  const passed = results.filter(r => r.status === 'PASS').length;
  const failed = results.filter(r => r.status === 'FAIL');

  console.log(`\n${separator('═')}`);
  console.log(`  SUMMARY: ${passed}/${results.length} steps PASSED`);

  if (failed.length > 0) {
    console.log(`\n  FAILURES requiring contract issue raises:`);
    for (const f of failed) {
      console.log(`    ✗ Step ${f.step} (${f.owner}) — boundary: ${f.boundary}`);
    }
    console.log('\n  Next action: raise contract issues per owning PC above.');
    console.log('  Do NOT patch another PC\'s code directly.\n');
  } else {
    console.log('\n  All integration seams verified. No contract issues raised.');
    console.log('  System is ready for Phase 5 (live market data integration).\n');
  }

  console.log(`${separator('═')}\n`);

  process.exit(failed.length > 0 ? 1 : 0);
}

main().catch(err => {
  console.error('\n[FATAL] Integration test runner crashed:', err);
  process.exit(1);
});
