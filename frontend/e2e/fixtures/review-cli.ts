#!/usr/bin/env npx ts-node
/**
 * CLI tool for reviewing and approving recorded API fixtures
 *
 * Usage:
 *   npx ts-node e2e/fixtures/review-cli.ts
 *
 * Or add to package.json scripts:
 *   "fixtures:review": "ts-node e2e/fixtures/review-cli.ts"
 */

import * as fs from 'fs';
import * as path from 'path';
import * as readline from 'readline';
import { ApiFixture, RecordingSession } from './types';

const FIXTURES_DIR = path.join(__dirname, 'data');
const RECORDINGS_DIR = path.join(FIXTURES_DIR, 'recordings');
const APPROVED_DIR = path.join(FIXTURES_DIR, 'approved');

// Ensure directories exist
[FIXTURES_DIR, RECORDINGS_DIR, APPROVED_DIR].forEach((dir) => {
  if (!fs.existsSync(dir)) {
    fs.mkdirSync(dir, { recursive: true });
  }
});

const rl = readline.createInterface({
  input: process.stdin,
  output: process.stdout,
});

function prompt(question: string): Promise<string> {
  return new Promise((resolve) => {
    rl.question(question, resolve);
  });
}

function printFixture(fixture: ApiFixture, index: number, total: number): void {
  console.log('\n' + '='.repeat(80));
  console.log(`📋 Fixture ${index + 1}/${total}: ${fixture.id}`);
  console.log('='.repeat(80));

  console.log('\n📤 REQUEST:');
  console.log(`   Method: ${fixture.request.method}`);
  console.log(`   Path:   ${fixture.request.path}`);
  if (fixture.request.query && Object.keys(fixture.request.query).length > 0) {
    console.log(`   Query:  ${JSON.stringify(fixture.request.query)}`);
  }
  if (fixture.request.body) {
    console.log(`   Body:   ${JSON.stringify(fixture.request.body, null, 2).split('\n').join('\n          ')}`);
  }

  console.log('\n📥 RESPONSE:');
  console.log(`   Status: ${fixture.response.status} ${fixture.response.statusText}`);
  console.log(`   Body:`);

  const bodyStr = JSON.stringify(fixture.response.body, null, 2);
  const lines = bodyStr.split('\n');
  if (lines.length > 30) {
    // Truncate long responses
    console.log(lines.slice(0, 25).map((l) => `          ${l}`).join('\n'));
    console.log(`          ... (${lines.length - 25} more lines)`);
  } else {
    console.log(lines.map((l) => `          ${l}`).join('\n'));
  }

  console.log(`\n⏰ Captured: ${fixture.capturedAt}`);
}

async function reviewFixture(fixture: ApiFixture): Promise<'approve' | 'skip' | 'edit' | 'quit'> {
  console.log('\nOptions:');
  console.log('  [a] Approve - Save this fixture for use in tests');
  console.log('  [s] Skip    - Do not approve this fixture');
  console.log('  [e] Edit    - Add notes/description before approving');
  console.log('  [q] Quit    - Exit review session');

  const answer = await prompt('\nYour choice (a/s/e/q): ');

  switch (answer.toLowerCase().trim()) {
    case 'a':
      return 'approve';
    case 's':
      return 'skip';
    case 'e':
      return 'edit';
    case 'q':
      return 'quit';
    default:
      console.log('Invalid choice, please try again.');
      return reviewFixture(fixture);
  }
}

async function editFixture(fixture: ApiFixture): Promise<ApiFixture> {
  console.log('\nEditing fixture...');

  const description = await prompt(`Description (current: "${fixture.description}"): `);
  if (description.trim()) {
    fixture.description = description.trim();
  }

  const notes = await prompt('Review notes (optional): ');
  if (notes.trim()) {
    fixture.reviewNotes = notes.trim();
  }

  return fixture;
}

function saveApprovedFixture(fixture: ApiFixture): string {
  fixture.reviewed = true;

  // Generate filename from fixture ID
  const filename = `${fixture.id}.json`;
  const filepath = path.join(APPROVED_DIR, filename);

  // Check for existing fixture with same ID
  if (fs.existsSync(filepath)) {
    const timestamp = Date.now();
    const backupPath = path.join(APPROVED_DIR, `${fixture.id}.backup-${timestamp}.json`);
    fs.renameSync(filepath, backupPath);
    console.log(`   ⚠️ Existing fixture backed up to: ${path.basename(backupPath)}`);
  }

  fs.writeFileSync(filepath, JSON.stringify(fixture, null, 2), 'utf-8');
  return filepath;
}

async function reviewSession(sessionFile: string): Promise<void> {
  const content = fs.readFileSync(sessionFile, 'utf-8');
  const session: RecordingSession = JSON.parse(content);

  console.log('\n' + '🎬'.repeat(40));
  console.log(`\n📁 Reviewing recording session: ${session.sessionId}`);
  console.log(`   Started: ${session.startedAt}`);
  console.log(`   Test file: ${session.testFile || 'N/A'}`);
  console.log(`   Total API calls: ${session.calls.length}`);
  console.log('\n' + '🎬'.repeat(40));

  let approved = 0;
  let skipped = 0;

  for (let i = 0; i < session.calls.length; i++) {
    let fixture = session.calls[i];

    printFixture(fixture, i, session.calls.length);

    const action = await reviewFixture(fixture);

    switch (action) {
      case 'approve':
        const savedPath = saveApprovedFixture(fixture);
        console.log(`   ✅ Approved and saved: ${path.basename(savedPath)}`);
        approved++;
        break;

      case 'edit':
        fixture = await editFixture(fixture);
        const editedPath = saveApprovedFixture(fixture);
        console.log(`   ✅ Approved and saved: ${path.basename(editedPath)}`);
        approved++;
        break;

      case 'skip':
        console.log('   ⏭️ Skipped');
        skipped++;
        break;

      case 'quit':
        console.log('\n👋 Exiting review session...');
        console.log(`   Approved: ${approved}, Skipped: ${skipped}, Remaining: ${session.calls.length - i}`);
        rl.close();
        return;
    }
  }

  console.log('\n' + '='.repeat(80));
  console.log('📊 Review Summary:');
  console.log(`   ✅ Approved: ${approved}`);
  console.log(`   ⏭️ Skipped:  ${skipped}`);
  console.log('='.repeat(80));

  // Ask if user wants to delete the recording
  const deleteRecording = await prompt('\nDelete the processed recording file? (y/n): ');
  if (deleteRecording.toLowerCase().trim() === 'y') {
    fs.unlinkSync(sessionFile);
    console.log('   🗑️ Recording file deleted');
  }

  rl.close();
}

async function listRecordings(): Promise<string[]> {
  if (!fs.existsSync(RECORDINGS_DIR)) {
    return [];
  }
  return fs.readdirSync(RECORDINGS_DIR)
    .filter((f) => f.endsWith('.json'))
    .map((f) => path.join(RECORDINGS_DIR, f));
}

async function main(): Promise<void> {
  console.log('\n🔍 API Fixture Review Tool');
  console.log('='.repeat(40));

  const recordings = await listRecordings();

  if (recordings.length === 0) {
    console.log('\n📭 No recordings found to review.');
    console.log('\nTo capture new recordings:');
    console.log('  RECORD_FIXTURES=true npm run test:e2e');
    rl.close();
    return;
  }

  console.log(`\n📁 Found ${recordings.length} recording(s):\n`);
  recordings.forEach((file, i) => {
    const content = JSON.parse(fs.readFileSync(file, 'utf-8')) as RecordingSession;
    console.log(`  ${i + 1}. ${path.basename(file)}`);
    console.log(`     └─ ${content.calls.length} API calls, captured ${content.startedAt}`);
  });

  const choice = await prompt(`\nSelect recording to review (1-${recordings.length}), or 'q' to quit: `);

  if (choice.toLowerCase() === 'q') {
    console.log('\n👋 Goodbye!');
    rl.close();
    return;
  }

  const index = parseInt(choice, 10) - 1;
  if (isNaN(index) || index < 0 || index >= recordings.length) {
    console.log('Invalid selection.');
    rl.close();
    return;
  }

  await reviewSession(recordings[index]);
}

main().catch((err) => {
  console.error('Error:', err);
  rl.close();
  process.exit(1);
});
