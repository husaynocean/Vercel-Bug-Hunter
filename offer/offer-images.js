const { chromium } = require('playwright');
(async () => {
  const b = await chromium.launch();
  const p = await b.newPage({ viewport: { width: 560, height: 300 }, deviceScaleFactor: 2, colorScheme: 'light' });
  const html = require('fs').readFileSync(process.argv[2], 'utf8');
  await p.setContent(`<!doctype html><html><head><meta charset="utf-8"><meta name="viewport" content="width=device-width"></head><body>${html}</body></html>`);
  await p.evaluate(() => document.fonts.ready);
  await p.addStyleTag({ content: '[hidden]{display:none!important} body{padding-bottom:28px} header{padding-top:28px} .run{font-size:12.5px!important;white-space:pre-wrap!important;overflow-wrap:anywhere} .wrap{gap:28px} pre.code{font-size:11.5px!important;white-space:pre-wrap!important;overflow-wrap:anywhere}' });
  await p.waitForTimeout(500);
  const ids = [['header', 'x-offer-1.png'], ['section[aria-labelledby=track]', 'x-offer-2.png'], ['section[aria-labelledby=price]', 'x-offer-3.png'], ['section[aria-labelledby=sample]', 'x-offer-4.png']];
  for (const [sel, name] of ids) {
    await p.evaluate((sel) => { document.querySelectorAll('.wrap > *').forEach(e => e.hidden = !e.matches(sel) && !(sel.includes('price') && e.classList.contains('cta'))); }, sel);
    await p.screenshot({ path: name, fullPage: true });
  }
  await b.close();
})();
