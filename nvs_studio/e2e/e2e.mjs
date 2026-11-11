// Kiểm thử trình duyệt thật cho Karaoke Editor. Chạy: npm run build && npx vite preview --port 4173 & node e2e/e2e.mjs
// Cần (không nằm trong package.json vì nặng): npm i -D playwright-core @sparticuz/chromium   (hoặc dùng Chrome cài sẵn qua executablePath)
import { chromium } from 'playwright-core';
import sparticuz from '@sparticuz/chromium';
import fs from 'node:fs';
import os from 'node:os';
import path from 'node:path';
const BASE = process.env.E2E_URL ?? 'http://127.0.0.1:4173/', TMP = fs.mkdtempSync(path.join(os.tmpdir(), 'nvs-e2e-')), OUT = path.resolve('e2e/out'); fs.mkdirSync(OUT, { recursive: true });
{ // nhạc thử 24 s (nhiễu có nhịp đập) viết thẳng ra WAV 16-bit mono
  const sr = 22050, n = sr * 24, buf = Buffer.alloc(44 + n * 2); buf.write('RIFF', 0); buf.writeUInt32LE(36 + n * 2, 4); buf.write('WAVEfmt ', 8); buf.writeUInt32LE(16, 16); buf.writeUInt16LE(1, 20); buf.writeUInt16LE(1, 22); buf.writeUInt32LE(sr, 24); buf.writeUInt32LE(sr * 2, 28); buf.writeUInt16LE(2, 32); buf.writeUInt16LE(16, 34); buf.write('data', 36); buf.writeUInt32LE(n * 2, 40);
  for (let i = 0; i < n; i++) { const env = 0.5 + 0.5 * Math.sin((2 * Math.PI * 2.2 * i) / sr); buf.writeInt16LE(Math.round((Math.random() * 2 - 1) * 12000 * env), 44 + i * 2); }
  fs.writeFileSync(path.join(TMP, 'test.wav'), buf);
  fs.writeFileSync(path.join(TMP, 'sample.lrc'), '[ti:Thử nghiệm]\n[00:01.00]<00:01.00>Xin <00:01.60>chào <00:02.20>các <00:02.80>bạn<00:03.40>\n[00:05.00]<00:05.00>お<00:05.40>母さん<00:06.20>は<00:06.80>\n');
  fs.writeFileSync(path.join(TMP, 'sample.srt'), '1\n00:00:08,000 --> 00:00:11,000\nMột dòng từ SRT\n\n2\n00:00:12,000 --> 00:00:14,500\nDòng hai\n');
}
const results = []; const ok = (name, cond, extra = '') => { results.push([cond ? 'PASS' : 'FAIL', name, extra]); };
const b = await chromium.launch({ executablePath: await sparticuz.executablePath(), args: sparticuz.args, headless: true });
const page = await b.newPage({ viewport: { width: 1600, height: 900 }, acceptDownloads: true });
const errs = []; page.on('pageerror', (e) => errs.push('PAGEERROR ' + e.message)); page.on('console', (m) => m.type() === 'error' && errs.push('CONSOLE ' + m.text()));
await page.goto(BASE + '?e2e'); await page.waitForTimeout(500);
const S = (fn, arg) => page.evaluate(fn, arg);
const kar = () => S(() => { const s = window.__nvs.karaoke.getState(); return { n: s.lines.length, sel: s.sel, edge: s.selEdge, est: s.lines.map((l) => !!l.est), w: s.lines.map((l) => l.words.map((x) => [x.text, x.start, x.end])), past: s.past.length, offset: s.offset, source: s.source }; });

try {
// 1) nhập nhạc thật, đưa vào timeline
await page.setInputFiles('input[multiple]', path.join(TMP, 'test.wav')); await page.waitForFunction(() => window.__nvs.studio.getState().media.length === 1, null, { timeout: 15000 });
const med = await S(() => { const m = window.__nvs.studio.getState().media[0]; return { dur: m.dur, hp: m.hp?.length, peaks: m.peaks?.length }; });
ok('Nhập WAV: có thời lượng và sóng âm độ phân giải cao', med.dur > 23 && med.hp > 1100, JSON.stringify(med));
await page.locator('button[title="Thêm vào timeline tại playhead"]').click();
ok('Thêm nhạc vào timeline (track A1)', await S(() => window.__nvs.studio.getState().clips.some((c) => c.track === 'A1' && c.start === 0)));
// 2) timeline cũ vẫn hoạt động: chọn clip, cắt bằng phím S
await page.getByText('test.wav').last().click(); await S(() => window.__nvs.studio.setState({ playhead: 10 })); const nA = await S(() => window.__nvs.studio.getState().clips.length);
await page.keyboard.press('s'); ok('Timeline: phím S cắt clip tại playhead', (await S(() => window.__nvs.studio.getState().clips.length)) === nA + 1);
await page.keyboard.press('Control+z'); ok('Timeline: Ctrl+Z hoàn tác cắt', (await S(() => window.__nvs.studio.getState().clips.length)) === nA);
// 3) mở Karaoke Editor, nhập Enhanced LRC
await page.getByRole('button', { name: 'Karaoke Editor', exact: true }).click(); await page.waitForTimeout(300);
await page.setInputFiles('input[accept*=".lrc"]', path.join(TMP, 'sample.lrc')); await page.waitForTimeout(300);
let k = await kar(); ok('Nhập Enhanced LRC: 2 câu, mốc từng từ thật (không ước lượng)', k.n === 2 && !k.est[0] && k.w[0].length === 4 && Math.abs(k.w[0][1][1] - 1.6) < 0.011, JSON.stringify(k.w[0]));
ok('Nhập LRC tiếng Nhật được tách từ', k.w[1].map((x) => x[0]).join('') === 'お母さんは', JSON.stringify(k.w[1]));
await page.setInputFiles('input[accept*=".lrc"]', path.join(TMP, 'sample.srt')); await page.waitForTimeout(300); k = await kar(); ok('Nhập SRT: 2 câu, đánh dấu ước lượng', k.n === 2 && k.est.every(Boolean));
await page.setInputFiles('input[accept*=".lrc"]', path.join(TMP, 'sample.lrc')); await page.waitForTimeout(300);
// 4) kéo mép từ bằng chuột trên waveform
const cvs = page.locator('div[tabindex="0"] canvas'); const box = await cvs.boundingBox(); const Z = 120;
const t0 = (await kar()).w[0][1][2]; const y = box.y + box.height - 40;
await page.mouse.click(box.x + 1.2 * Z, y); await page.waitForTimeout(100); ok('Bấm vào câu để chọn', (await kar()).sel === (await S(() => window.__nvs.karaoke.getState().lines[0].id)));
const pastBefore = (await kar()).past; await page.mouse.move(box.x + t0 * Z, y); await page.mouse.down(); await page.mouse.move(box.x + t0 * Z + 30, y, { steps: 6 }); await page.mouse.up();
k = await kar(); const t1 = k.w[0][1][2]; ok('Kéo mép bằng chuột: dịch ≈ +0,25 s và từ kế tiếp dính theo', Math.abs(t1 - (t0 + 0.25)) < 0.02 && Math.abs(k.w[0][2][1] - t1) < 0.002, `${t0} → ${t1}`);
ok('Kéo mép chỉ tạo một bước hoàn tác', k.past === pastBefore + 1, `past ${pastBefore}→${k.past}`);
await page.keyboard.press('ArrowRight'); k = await kar(); ok('Phím → nhích 10 ms', Math.abs(k.w[0][1][2] - (t1 + 0.01)) < 0.0015, `${k.w[0][1][2]}`);
await page.keyboard.press('Shift+ArrowLeft'); k = await kar(); ok('Shift+← lùi 100 ms', Math.abs(k.w[0][1][2] - (t1 - 0.09)) < 0.0015);
await S(() => window.__nvs.studio.setState({ playhead: 2.6 })); const selBefore = (await kar()).edge; await page.keyboard.press('m'); k = await kar();
ok('Phím M đặt mép tại playhead rồi sang mép kế', Math.abs(k.w[0][1][2] - 2.6) < 0.0015 && k.edge > selBefore, `edge ${selBefore}→${k.edge}, t=${k.w[0][1][2]}`);
await page.keyboard.press('Control+z'); await page.keyboard.press('Control+z'); await page.keyboard.press('Control+z'); k = await kar(); ok('Ctrl+Z hoàn tác thao tác lời (không đụng timeline)', Math.abs(k.w[0][1][2] - t0) < 0.0015, `${k.w[0][1][2]} vs ${t0}`);
// 5) ranh giới: không cho kéo vượt từ kế
await page.mouse.move(box.x + t0 * Z, y); await page.mouse.down(); await page.mouse.move(box.x + 20 * Z, y, { steps: 4 }); await page.mouse.up(); k = await kar();
ok('Không kéo mép vượt qua mép kế tiếp', k.w[0][1][2] < k.w[0][2][2] && k.w[0][1][2] > k.w[0][1][1]);
await page.keyboard.press('Control+z');
// 6) sửa chữ và gõ được dấu cách
const inp = page.locator('input[placeholder="Thêm câu sau câu đang chọn…"]').locator('xpath=ancestor::div[contains(@class,"overflow-auto")]').locator('input').first();
await inp.click(); await inp.fill(''); await inp.type('Xin chào các bạn ơi'); k = await kar(); ok('Gõ lời có dấu cách và dấu tiếng Việt', k.w[0].map((x) => x[0]).join(' ') === 'Xin chào các bạn ơi', JSON.stringify(k.w[0].map((x) => x[0])));
await page.keyboard.press('Tab'); await page.keyboard.press('Control+z');
// 7) preview tô màu theo mốc: giữa từ "chào" (1,6–2,2) → tô khoảng nửa từ
const px = (t) => S((tt) => { window.__nvs.studio.setState({ playhead: tt, playing: false }); return new Promise((r) => setTimeout(() => { const c = document.querySelectorAll('canvas')[0], g = c.getContext('2d'); const d = g.getImageData(0, Math.floor(c.height * 0.7), c.width, Math.floor(c.height * 0.25)).data; let cy = 0, wh = 0; for (let i = 0; i < d.length; i += 4) { if (d[i] < 90 && d[i + 1] > 170 && d[i + 2] > 190) cy++; else if (d[i] > 230 && d[i + 1] > 230 && d[i + 2] > 230) wh++; } r({ cy, wh }); }, 150)); }, t);
const a = await px(0.8), c1 = await px(1.9), c2 = await px(3.3); ok('Preview: trước khi hát chưa có chữ tô màu', a.cy === 0 && a.wh > 50, JSON.stringify(a)); ok('Preview: đang hát có chữ tô màu cyan', c1.cy > 100, JSON.stringify(c1)); ok('Preview: cuối câu tô nhiều hơn giữa câu', c2.cy > c1.cy, JSON.stringify([c1, c2]));
await page.screenshot({ path: path.join(OUT, '01-editor.png') });
// 8) xuất file và đọc lại bằng bộ đọc của chính app
const dlOf = async (title) => { const [d] = await Promise.all([page.waitForEvent('download'), page.locator(`button[title="${title}"]`).click()]); const p = await d.path(); return { name: d.suggestedFilename(), text: fs.readFileSync(p, 'utf8') }; };
const e1 = await dlOf('Xuất Enhanced LRC'); ok('Xuất Enhanced LRC có mốc từng từ', /^\[00:01\.00\]<00:01\.00>Xin <00:01\.60>chào/.test(e1.text) && e1.name.endsWith('.enhanced.lrc'), e1.text.split('\n')[0]);
const e2 = await dlOf('Xuất SRT'); ok('Xuất SRT đúng định dạng', /^1\n00:00:01,000 --> 00:00:03,400\nXin chào các bạn\n/.test(e2.text), JSON.stringify(e2.text.slice(0, 60)));
const e3 = await dlOf('Xuất ASS'); ok('Xuất ASS có \\kf và Dialogue', e3.text.includes('{\\kf60}Xin ') && e3.text.includes('Dialogue: 0,0:00:01.00,0:00:03.40'), e3.text.split('\n').find((l) => l.startsWith('Dialogue')));
// 9) offset
await page.locator('label:has-text("Offset") input').fill('500'); k = await kar(); const e4 = await dlOf('Xuất LRC'); ok('Offset +500 ms áp dụng khi xuất', e4.text.startsWith('[00:01.50]'), e4.text.split('\n')[0]);
await page.getByRole('button', { name: 'Áp dụng' }).click(); k = await kar(); ok('Áp dụng offset vào dữ liệu và đưa về 0', k.offset === 0 && Math.abs(k.w[0][0][1] - 1.5) < 0.002);
// 10) nghe thử câu
await page.locator('button[title="Nghe thử câu này"]').first().click(); await page.waitForTimeout(300);
ok('Nghe thử câu: bắt đầu phát từ trước câu', await S(() => { const s = window.__nvs.studio.getState(), e = window.__nvs.karaoke.getState().auditionEnd; return s.playing && e > 3; }));
await S(() => window.__nvs.studio.setState({ playhead: window.__nvs.karaoke.getState().auditionEnd + 0.01 })); await page.waitForTimeout(300); ok('Nghe thử câu: tự dừng ở cuối câu', !(await S(() => window.__nvs.studio.getState().playing)));
// 11) Wizard MOCK
await page.getByRole('button', { name: 'Auto Karaoke' }).first().click(); await page.getByText('Auto Karaoke Wizard').waitFor();
await page.getByRole('button', { name: /^MOCK/ }).click(); await page.getByRole('button', { name: 'Tiếp tục' }).click(); await page.screenshot({ path: path.join(OUT, '02-wizard-lang.png') });
await page.locator('textarea').fill('Dòng một của tôi\nDòng hai của tôi'); await page.getByRole('button', { name: 'Bắt đầu' }).click(); await page.waitForTimeout(1200); await page.screenshot({ path: path.join(OUT, '03-wizard-progress.png') });
const stateMid = await page.locator('b', { hasText: /Đang|Thành công/ }).first().textContent(); ok('Wizard: hiện trạng thái đang xử lý', /Đang/.test(stateMid), stateMid);
await page.getByRole('button', { name: 'Mở trong Karaoke Editor' }).waitFor({ timeout: 15000 }); await page.screenshot({ path: path.join(OUT, '04-wizard-result.png') });
ok('Wizard: kết quả ghi rõ MOCK', await page.getByText('DỮ LIỆU GIẢ LẬP (MOCK)').isVisible());
await page.getByRole('button', { name: 'Mở trong Karaoke Editor' }).click(); k = await kar(); ok('Wizard: mở kết quả vào editor, nguồn = mock', k.n === 2 && k.source === 'mock' && k.w[0].map((x) => x[0]).join(' ') === 'Dòng một của tôi', JSON.stringify([k.n, k.source]));
ok('Editor hiện nhãn MOCK', await page.getByText('MOCK: DỮ LIỆU GIẢ LẬP').isVisible());
// 12) Wizard hủy giữa chừng + backend chưa chạy
await page.getByRole('button', { name: 'Auto Karaoke' }).first().click(); await page.getByRole('button', { name: /^MOCK/ }).click(); await page.getByRole('button', { name: 'Tiếp tục' }).click(); await page.getByRole('button', { name: 'Bắt đầu' }).click(); await page.waitForTimeout(500); await page.getByRole('button', { name: 'Hủy xử lý' }).click();
await page.getByText('Đã hủy xử lý.').waitFor({ timeout: 5000 }); ok('Wizard: hủy xử lý hiện trạng thái đã hủy', true); await page.getByRole('button', { name: 'Quay lại' }).click(); await page.getByRole('button', { name: 'Quay lại' }).click();
ok('Wizard: backend chưa chạy được báo rõ', await page.getByText('chưa chạy').isVisible()); await page.screenshot({ path: path.join(OUT, '05-wizard-backend-down.png') }); await page.locator('button:has(svg.lucide-x)').click();
// 13) hiệu ứng chữ
await page.getByRole('button', { name: 'Timeline', exact: true }).click(); await page.getByRole('button', { name: 'Karaoke Editor', exact: true }).click();
for (const eff of ['pop', 'glow', 'bounce', 'type', 'fade', 'sweep']) { await page.locator('select').filter({ has: page.locator('option[value="pop"]') }).selectOption(eff); await S(() => window.__nvs.studio.setState({ playhead: 2.2 })); await page.waitForTimeout(80); }
ok('Đổi 6 hiệu ứng chữ không lỗi', true); await page.screenshot({ path: path.join(OUT, '06-final.png') });
const realErrs = errs.filter((x) => !/404/.test(x)); ok('Không có lỗi JS/console (bỏ qua 404 của /api vì máy chủ thử không có backend)', realErrs.length === 0, JSON.stringify(realErrs.slice(0, 3)));
} catch (e) { ok('LỖI KỊCH BẢN', false, String(e.message).split('\n')[0].slice(0, 250)); }
console.log(results.map((r) => `${r[0]}  ${r[1]}${r[2] ? '  [' + r[2] + ']' : ''}`).join('\n')); console.log(`\n${results.filter((r) => r[0] === 'PASS').length}/${results.length} đạt`);
await b.close(); process.exit(results.some((r) => r[0] === 'FAIL') ? 1 : 0);
