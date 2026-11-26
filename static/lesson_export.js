// The file a student downloads when a lesson ends, to read it and come back to it later: one standalone HTML
// page with the exercise, the lesson's GeoGebra board (the real applet, loaded from geogebra.org, with an image
// of the final board for when there is no connection and for printing), every step with its explanation and
// the teacher's audio, and the construction as a .ggb file. Each step can rebuild the board up to that point.
// Everything the student or the model wrote is escaped: the page shows it as text, never as markup or code.

const GGB_SCRIPT = 'https://www.geogebra.org/apps/deployggb.js';
// Same modules as the applet of static/app.js, so every command of the lesson works when a step is rebuilt
const GGB_MODULES = 'advanced,prover,scripting,stats,cas,spatial,discrete';
const BASE64_RE = /^[A-Za-z0-9+/]+={0,2}$/;

const escapeHtml = (text) => String(text ?? '').replace(/[&<>"']/g, (c) => (
    { '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;' }[c]));

// JSON inside a <script>: no string can close the tag ("</script>") or open a comment ("<!--")
const scriptJson = (value) => JSON.stringify(value).replace(/</g, '\\u003c');

// Base64 without its "data:...;base64," prefix, or '' when it is not base64
const cleanBase64 = (value) => {
    if (typeof value !== 'string') return '';
    const raw = value.replace(/^data:[^,]*,/, '');
    return BASE64_RE.test(raw) ? raw : '';
};

// The teacher's audio of a step (data:audio/mp3;base64,... from app/bot.py), or '' when the step has none
const cleanAudio = (url) => (typeof url === 'string' && /^data:audio\/[\w.+-]+;base64,/.test(url)
    && BASE64_RE.test(url.slice(url.indexOf(',') + 1)) ? url : '');

// The construction (.ggb, base64) and an image of the graphics view of the applet that played the lesson
export async function readBoard(api) {
    const ggb = await new Promise((resolve) => {
        setTimeout(() => resolve(''), 5000);
        try {
            const sync = api.getBase64((b64) => resolve(b64));
            if (typeof sync === 'string' && sync) resolve(sync);
        } catch (err) {
            console.error('Could not read the GeoGebra construction', err);
            resolve('');
        }
    });
    let png = '';
    try {
        png = api.getPNGBase64(1, false, 72) || '';
    } catch (err) {
        console.error('Could not take the image of the board', err);
    }
    return { ggb: cleanBase64(ggb), png: cleanBase64(png) };
}

const isoDay = (date) => [date.getFullYear(), date.getMonth() + 1, date.getDate()]
    .map((n) => String(n).padStart(2, '0')).join('-');

// tutorgebra-2026-11-26-una-empresa-debe-producir-120.html (no accents or symbols, so any system accepts it)
export function lessonFileName(promptText, date, fallback, extension = 'html') {
    let slug = (promptText || '').normalize('NFD').replace(/[̀-ͯ]/g, '').toLowerCase()
        .replace(/[^a-z0-9]+/g, '-').replace(/^-+|-+$/g, '');
    if (slug.length > 40) slug = slug.slice(0, 41).replace(/-[^-]*$/, '').slice(0, 40); // whole words only
    return `tutorgebra-${isoDay(date)}-${slug || fallback}.${extension}`;
}

export function saveFile(fileName, content, type = 'text/html;charset=utf-8') {
    const url = URL.createObjectURL(new Blob([content], { type }));
    const link = document.createElement('a');
    link.href = url;
    link.download = fileName;
    document.body.appendChild(link);
    link.click();
    link.remove();
    setTimeout(() => URL.revokeObjectURL(url), 10000);
}

const STYLE = `
:root { --ink: #1f2937; --muted: #6b7280; --line: #e5e7eb; --page: #f3f4f6; --card: #ffffff;
  --brand: #4f46e5; --brand-dark: #4338ca; --brand-soft: #eef2ff; --code: #be185d;
  --warn-bg: #fffbeb; --warn-line: #f59e0b; --warn-ink: #92400e; color-scheme: light; }
* { box-sizing: border-box; }
body { margin: 0; background: var(--page); color: var(--ink);
  font: 16px/1.6 system-ui, -apple-system, "Segoe UI", Roboto, sans-serif; }
main { max-width: 1240px; margin: 0 auto; padding: 24px 16px 40px; }
.brand { color: var(--brand); font-weight: 700; font-size: .95rem; letter-spacing: .02em; margin: 0; }
h1 { font-size: 1.6rem; line-height: 1.25; margin: .25rem 0 .35rem; text-wrap: balance; }
h2 { font-size: 1.1rem; margin: 0 0 12px; }
.meta { color: var(--muted); font-size: .9rem; margin: 0; }
.card { background: var(--card); border: 1px solid var(--line); border-radius: 14px; padding: 20px; margin-top: 18px; }
.prompt { white-space: pre-wrap; overflow-wrap: anywhere; margin: 0; }
.photo { display: block; max-width: 100%; max-height: 520px; border: 1px solid var(--line); border-radius: 10px; margin-top: 12px; }
.warning { background: var(--warn-bg); border: 1px solid var(--warn-line); color: var(--warn-ink);
  border-radius: 12px; padding: 12px 16px; margin-top: 18px; }
.lesson { display: grid; gap: 18px; margin-top: 18px; }
.lesson > .card { margin-top: 0; min-width: 0; }
@media (min-width: 1024px) {
  .lesson { grid-template-columns: minmax(0, 2fr) minmax(0, 3fr); align-items: start; }
  .steps-card { order: 1; }
  .board-card { order: 2; position: sticky; top: 16px; }
}
.board-bar { display: flex; flex-wrap: wrap; gap: 8px; align-items: center; margin-bottom: 10px; }
.board-bar h2 { margin: 0 auto 0 0; }
.status { color: var(--muted); font-size: .9rem; margin: 0 0 10px; }
#board { position: relative; width: 100%; height: min(68vh, 600px); min-height: 360px;
  border: 1px solid var(--line); border-radius: 10px; overflow: hidden; background: #fff; }
#board .loading { position: absolute; inset: 0; display: grid; place-items: center; color: var(--muted); }
body.ggb-ready #board .loading { display: none; }
.graph { display: none; max-width: 100%; margin: 0 auto; border: 1px solid var(--line); border-radius: 10px; }
.offline-note { display: none; color: var(--muted); font-size: .9rem; margin: 0 0 10px; }
body.ggb-offline #board, body.ggb-offline .needs-ggb { display: none !important; }
body.ggb-offline .graph, body.ggb-offline .offline-note { display: block; }
body:not(.ggb-ready) .needs-ggb { display: none !important; }
button, .button { font: inherit; font-size: .9rem; line-height: 1.2; border: 1px solid var(--line); background: #fff;
  color: var(--ink); border-radius: 999px; padding: 7px 14px; cursor: pointer; text-decoration: none;
  display: inline-flex; align-items: center; gap: 6px; }
button:hover, .button:hover { border-color: var(--brand); color: var(--brand); }
button:focus-visible, .button:focus-visible { outline: 2px solid var(--brand); outline-offset: 2px; }
button.playing { background: var(--brand); border-color: var(--brand); color: #fff; }
ol.steps { list-style: none; margin: 0; padding: 0; display: grid; gap: 10px; }
li.step { border: 1px solid var(--line); border-radius: 12px; padding: 12px 14px; scroll-margin-top: 16px; }
li.step.active { border-color: var(--brand); background: var(--brand-soft); }
.step-head { display: flex; gap: 10px; align-items: baseline; }
.num { flex: none; min-width: 1.8em; font-weight: 700; color: var(--brand); }
code { font-family: ui-monospace, SFMono-Regular, Consolas, monospace; font-size: .88rem; color: var(--code);
  overflow-wrap: anywhere; }
.no-command { color: var(--muted); font-size: .88rem; }
.speech { margin: 6px 0 0; overflow-wrap: anywhere; }
.actions { display: flex; flex-wrap: wrap; gap: 8px; margin-top: 10px; }
footer { color: var(--muted); font-size: .85rem; text-align: center; margin-top: 28px; }
@media (max-width: 640px) { h1 { font-size: 1.3rem; } .card { padding: 16px; } }
@media print {
  body { background: #fff; }
  main { max-width: none; padding: 0; }
  .lesson { display: block; }
  .card { border: none; border-radius: 0; padding: 0; margin-top: 18px; }
  #board, .actions, .board-bar .button, .board-bar button, .status, .offline-note { display: none !important; }
  .graph { display: block !important; max-height: 60vh; }
  li.step { break-inside: avoid; }
  li.step.active { background: none; border-color: var(--line); }
}`;

// Runs in the downloaded page. DATA: { commands, audio, ggb, text }
const PAGE_SCRIPT = `
const boardEl = document.getElementById('board');
const statusEl = document.getElementById('status');
const steps = Array.from(document.querySelectorAll('li.step'));
let api = null, audio = null, playingButton = null;

function showStatus(index) {
  statusEl.textContent = index === null ? DATA.text.finalStatus
    : DATA.text.stepStatus.replace('{n}', index + 1).replace('{total}', DATA.commands.length);
}
function markStep(index) {
  steps.forEach((li, i) => li.classList.toggle('active', i === index));
}
// The board as it was after the given step: an empty construction and the lesson's commands up to that step.
// On a narrow screen the board is above the steps, so "Show on the board" scrolls to it.
function showStep(index, scroll) {
  if (!api) return;
  if (api.setRepaintingActive) api.setRepaintingActive(false);
  try {
    api.newConstruction();
    if (api.setErrorDialogsActive) api.setErrorDialogsActive(false);
    for (let i = 0; i <= index; i++) {
      if (DATA.commands[i]) api.evalCommand(DATA.commands[i]);
    }
  } finally {
    if (api.setRepaintingActive) api.setRepaintingActive(true);
  }
  markStep(index);
  showStatus(index);
  if (scroll && window.matchMedia('(max-width: 1023px)').matches) boardEl.scrollIntoView({ behavior: 'smooth', block: 'center' });
}
function showFinal() {
  if (!api) return;
  api.setBase64(DATA.ggb, () => { if (api.setErrorDialogsActive) api.setErrorDialogsActive(false); });
  markStep(null);
  showStatus(null);
}
function stopAudio() {
  if (audio) audio.pause();
  audio = null;
  if (playingButton) {
    playingButton.textContent = DATA.text.listen;
    playingButton.classList.remove('playing');
  }
  playingButton = null;
}
function listen(index, button) {
  const sameStep = playingButton === button;
  stopAudio();
  if (sameStep) return;
  showStep(index, false);
  markStep(index); // also without a board (offline)
  const current = new Audio(DATA.audio[index]);
  audio = current;
  playingButton = button;
  button.textContent = DATA.text.stop;
  button.classList.add('playing');
  current.onended = () => { if (audio === current) stopAudio(); };
  current.play().catch(() => { if (audio === current) stopAudio(); });
}

document.addEventListener('click', (event) => {
  const button = event.target.closest('[data-show], [data-listen], [data-final], [data-print]');
  if (!button) return;
  if (button.dataset.show !== undefined) showStep(Number(button.dataset.show), true);
  else if (button.dataset.listen !== undefined) listen(Number(button.dataset.listen), button);
  else if (button.dataset.final !== undefined) showFinal();
  else window.print();
});

// The .ggb file, rebuilt from the base64 in the page (works without a connection)
const ggbLink = document.getElementById('ggb-link');
if (DATA.ggb) {
  const bytes = Uint8Array.from(atob(DATA.ggb), (c) => c.charCodeAt(0));
  ggbLink.href = URL.createObjectURL(new Blob([bytes], { type: 'application/vnd.geogebra.file' }));
} else {
  ggbLink.remove();
}

function offline() {
  document.body.classList.add('ggb-offline');
}
function startBoard() {
  if (typeof GGBApplet === 'undefined' || !DATA.ggb) return offline();
  const params = {
    appName: 'classic', ggbBase64: DATA.ggb,
    width: boardEl.clientWidth || 800, height: boardEl.clientHeight || 520,
    showToolBar: true, showAlgebraInput: true, showMenuBar: false,
    language: 'en', errorDialogsActive: false, preloadModules: DATA.modules,
    appletOnLoad: (loaded) => {
      if (api) return; // setBase64 may report the load again
      api = loaded;
      if (api.setErrorDialogsActive) api.setErrorDialogsActive(false);
      document.body.classList.add('ggb-ready');
      let resizeTimeout;
      new ResizeObserver(() => {
        clearTimeout(resizeTimeout);
        resizeTimeout = setTimeout(() => {
          if (boardEl.clientWidth > 0 && boardEl.clientHeight > 0) api.setSize(boardEl.clientWidth, boardEl.clientHeight);
        }, 150);
      }).observe(boardEl);
    }
  };
  new GGBApplet(params, true).inject('board-applet');
}
showStatus(null);
if (!DATA.ggb) {
  offline();
} else {
  const script = document.createElement('script');
  script.src = DATA.ggbScript;
  script.onload = startBoard;
  script.onerror = offline;
  document.head.appendChild(script);
}`;

/**
 * The downloaded page.
 * lesson: { prompt, image (JPEG base64), date, model, checksFailed, steps: [{command, speech, audio_url}],
 *           commands (prepared for evalCommand, one per step), ggb, png, lang }
 * t: the translation function of static/i18n.js
 */
export function buildLessonPage(lesson, t) {
    const steps = lesson.steps || [];
    const promptText = (lesson.prompt || '').trim();
    const firstLine = promptText.split('\n')[0];
    const title = firstLine ? (firstLine.length > 90 ? `${firstLine.slice(0, 88).trimEnd()}…` : firstLine) : t('export.photoTitle');
    const date = lesson.date instanceof Date ? lesson.date : new Date();
    const dateText = date.toLocaleString(lesson.lang || undefined, { dateStyle: 'long', timeStyle: 'short' });
    const image = cleanBase64(lesson.image);
    const png = cleanBase64(lesson.png);
    const ggb = cleanBase64(lesson.ggb);
    const audio = steps.map((step) => cleanAudio(step.audio_url));

    const stepItems = steps.map((step, index) => {
        const command = (step.command || '').trim();
        return `
      <li class="step">
        <div class="step-head">
          <span class="num">${index + 1}</span>
          ${command ? `<code>${escapeHtml(command)}</code>` : `<span class="no-command">${escapeHtml(t('export.explanation'))}</span>`}
        </div>
        <p class="speech">${escapeHtml(step.speech)}</p>
        <div class="actions">
          <button type="button" class="needs-ggb" data-show="${index}">${escapeHtml(t('export.show'))}</button>
          ${audio[index] ? `<button type="button" data-listen="${index}">${escapeHtml(t('export.listen'))}</button>` : ''}
        </div>
      </li>`;
    }).join('');

    const data = {
        commands: (lesson.commands || []).map((c) => (typeof c === 'string' ? c : '')),
        audio, ggb, modules: GGB_MODULES, ggbScript: GGB_SCRIPT,
        text: {
            listen: t('export.listen'), stop: t('export.stop'),
            finalStatus: t('export.finalStatus'), stepStatus: t('export.stepStatus'),
        },
    };

    return `<!doctype html>
<html lang="${escapeHtml(lesson.lang || 'en')}">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>${escapeHtml(title)} · TutorGebra</title>
<style>${STYLE}</style>
</head>
<body>
<main>
  <header>
    <p class="brand">TutorGebra</p>
    <h1>${escapeHtml(title)}</h1>
    <p class="meta">${escapeHtml(t('export.generated', { date: dateText }))}${lesson.model ? ` · ${escapeHtml(t('export.model', { model: lesson.model }))}` : ''}</p>
  </header>

  <section class="card">
    <h2>${escapeHtml(t('export.exercise'))}</h2>
    ${promptText ? `<p class="prompt">${escapeHtml(promptText)}</p>` : ''}
    ${image ? `<img class="photo" src="data:image/jpeg;base64,${image}" alt="${escapeHtml(t('export.photoAlt'))}">` : ''}
  </section>

  ${lesson.checksFailed ? `<p class="warning" role="alert">${escapeHtml(t('lesson.checksFailed'))}</p>` : ''}

  <div class="lesson">
    <section class="card board-card">
      <div class="board-bar">
        <h2>${escapeHtml(t('export.board'))}</h2>
        <button type="button" class="needs-ggb" data-final>${escapeHtml(t('export.final'))}</button>
        <a class="button" id="ggb-link" download="${escapeHtml(lessonFileName(promptText, date, t('export.fileFallback'), 'ggb'))}" title="${escapeHtml(t('export.ggbHint'))}">${escapeHtml(t('export.ggb'))}</a>
        <button type="button" data-print>${escapeHtml(t('export.print'))}</button>
      </div>
      <p class="status" id="status" aria-live="polite"></p>
      <p class="offline-note">${escapeHtml(t('export.offline'))}</p>
      <div id="board"><div class="loading">${escapeHtml(t('export.loading'))}</div><div id="board-applet"></div></div>
      ${png ? `<img class="graph" src="data:image/png;base64,${png}" alt="${escapeHtml(t('export.graphAlt'))}">` : ''}
    </section>

    <section class="card steps-card">
      <h2>${escapeHtml(t('export.steps'))}</h2>
      <p class="meta needs-ggb">${escapeHtml(t('export.boardHint'))}</p>
      <ol class="steps">${stepItems}
      </ol>
    </section>
  </div>

  <footer>${escapeHtml(t('export.footer'))} · ${escapeHtml(dateText)}</footer>
</main>
<script>
const DATA = ${scriptJson(data)};
${PAGE_SCRIPT}
</script>
</body>
</html>
`;
}
