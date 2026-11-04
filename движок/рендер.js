// Рендер ролика: кадры нарезки + сцена (сцена.html) по плану → mp4 со звуком нарезки.
//   node рендер.js план.json нарезка.mp4 итог.mp4 [--from 0 --to 12]
const { chromium } = require('playwright');
const fs = require('fs'), path = require('path'), os = require('os'), { execFileSync } = require('child_process');

const [planPath, cut, out] = process.argv.slice(2);
const arg = (k, d) => { const i = process.argv.indexOf(k); return i > 0 ? parseFloat(process.argv[i + 1]) : d; };
const FPS = 30, plan = JSON.parse(fs.readFileSync(planPath, 'utf8'));
const tmp = fs.mkdtempSync(path.join(os.tmpdir(), 'рендер-'));
const src = path.join(tmp, 'src'), dst = path.join(tmp, 'dst'); fs.mkdirSync(src); fs.mkdirSync(dst);
const from = arg('--from', 0), to = arg('--to', 1e9);

execFileSync('ffmpeg', ['-v', 'error', '-ss', String(from), '-to', String(to), '-i', cut, '-vf', `scale=1080:1920,fps=${FPS}`, '-q:v', '2', path.join(src, '%05d.jpg')]);
const frames = fs.readdirSync(src).filter(f => f.endsWith('.jpg')).sort();

(async () => {
  const browser = await chromium.launch();
  const page = await browser.newPage({ viewport: { width: 1080, height: 1920 } });
  await page.goto('file://' + path.resolve(__dirname, 'сцена.html'));
  await page.evaluate(p => setup(p), plan);
  await page.evaluate(() => document.fonts.ready);
  for (let i = 0; i < frames.length; i++) {
    const t = from + i / FPS;
    await page.evaluate(async ([t, s]) => {
      draw(t, s);
      await Promise.all([...document.images].filter(im => im.src).map(im => im.decode().catch(() => {})));
    }, [t, 'file://' + path.join(src, frames[i])]);
    await page.screenshot({ path: path.join(dst, frames[i]), type: 'jpeg', quality: 92 });
    if (i % 150 === 0) console.log(`кадр ${i}/${frames.length}`);
  }
  await browser.close();
  execFileSync('ffmpeg', ['-v', 'error', '-y', '-framerate', String(FPS), '-i', path.join(dst, '%05d.jpg'), '-ss', String(from), '-to', String(to), '-i', cut,
    '-map', '0:v', '-map', '1:a', '-c:v', 'libx264', '-crf', '18', '-preset', 'medium', '-pix_fmt', 'yuv420p', '-c:a', 'aac', '-b:a', '192k', '-shortest', out]);
  fs.rmSync(tmp, { recursive: true });
  console.log(`кадров: ${frames.length} → ${out}`);
})();
