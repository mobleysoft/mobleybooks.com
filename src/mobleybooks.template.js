const CATALOG = Object.freeze(__MOBLEYBOOKS_CATALOG__);

const SECURITY_HEADERS = Object.freeze({
  "Content-Security-Policy": "default-src 'none'; script-src 'unsafe-inline'; style-src 'unsafe-inline'; img-src data:; connect-src 'self'; base-uri 'none'; frame-ancestors 'none'; form-action 'none'",
  "Permissions-Policy": "camera=(), microphone=(), geolocation=()",
  "Referrer-Policy": "strict-origin-when-cross-origin",
  "X-Content-Type-Options": "nosniff",
  "X-Frame-Options": "DENY",
  "X-Mobley-Edge": "mobleybooks-library",
});

function withHeaders(body, request, init = {}) {
  const headers = new Headers(init.headers || {});
  for (const [name, value] of Object.entries(SECURITY_HEADERS)) headers.set(name, value);
  return new Response(request.method === "HEAD" ? null : body, { ...init, headers });
}

function json(body, request, status = 200) {
  return withHeaders(`${JSON.stringify(body, null, 2)}\n`, request, {
    status,
    headers: {
      "Cache-Control": "public, max-age=300, must-revalidate",
      "Content-Type": "application/json; charset=utf-8",
    },
  });
}

function xmlEscape(value) {
  return String(value).replaceAll("&", "&amp;").replaceAll("<", "&lt;").replaceAll(">", "&gt;");
}

function renderHtml() {
  const catalogPayload = JSON.stringify(CATALOG).replaceAll("<", "\\u003c");
  return `<!doctype html>
<html lang="en">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <meta name="description" content="A curated, evidence-backed library of science fiction, fantasy, thrillers, and story worlds from MobleyBooks.">
  <meta property="og:title" content="MobleyBooks — Stories with worlds inside">
  <meta property="og:description" content="Explore the workplace-safe public catalog from MobleyBooks.">
  <meta property="og:type" content="website">
  <meta property="og:url" content="https://mobleybooks.com/">
  <title>MobleyBooks — Stories with worlds inside</title>
  <style>
    :root{--paper:#eee6d7;--ink:#191713;--muted:#6c655a;--night:#11140f;--moss:#68764c;--gold:#c2934d;--line:rgba(25,23,19,.19);--serif:"Iowan Old Style","Palatino Linotype",Palatino,serif;--sans:"Avenir Next",Avenir,"Gill Sans",sans-serif;--mono:"SFMono-Regular",Consolas,monospace}
    *{box-sizing:border-box}html{scroll-behavior:smooth;background:var(--night)}body{margin:0;color:var(--ink);background:var(--paper);font-family:var(--sans)}button,input{font:inherit}a{color:inherit}.mast{position:relative;min-height:72vh;overflow:hidden;color:#f4efdf;background:linear-gradient(130deg,rgba(11,15,10,.97),rgba(24,28,18,.8)),radial-gradient(circle at 78% 18%,#8d6b35,transparent 33rem)}.mast:before{content:"";position:absolute;inset:-10%;opacity:.24;background:repeating-linear-gradient(107deg,transparent 0 88px,rgba(255,255,255,.08) 89px 90px),repeating-linear-gradient(17deg,transparent 0 72px,rgba(255,255,255,.04) 73px 74px);transform:rotate(-2deg)}nav,.hero,.catalog,.principle,footer{width:min(1240px,calc(100% - 40px));margin-inline:auto}nav{position:relative;z-index:2;display:flex;justify-content:space-between;align-items:center;padding:24px 0;border-bottom:1px solid rgba(255,255,255,.2)}.wordmark{font:700 12px/1 var(--mono);letter-spacing:.24em;text-transform:uppercase}.wordmark b{display:inline-grid;place-items:center;width:31px;height:31px;margin-right:12px;border:1px solid var(--gold);color:var(--gold)}nav a{font:600 10px/1 var(--mono);letter-spacing:.18em;text-transform:uppercase;text-decoration:none;color:#d8d1bf}.hero{position:relative;z-index:2;display:grid;grid-template-columns:1.25fr .75fr;gap:60px;align-items:end;padding:clamp(80px,15vw,170px) 0 72px}.eyebrow,.kicker,.count,.meta{font:600 10px/1.5 var(--mono);letter-spacing:.17em;text-transform:uppercase}.eyebrow{color:#d8af68}.hero h1{max-width:830px;margin:18px 0 26px;font:400 clamp(60px,10vw,128px)/.86 var(--serif);letter-spacing:-.065em}.hero h1 em{font-weight:400;color:#d8af68}.hero-copy{max-width:690px;margin:0;color:#d6d2c6;font:400 clamp(18px,2.3vw,27px)/1.5 var(--serif)}.hero-aside{padding:24px 0 8px;border-top:1px solid rgba(255,255,255,.3);color:#bdb7a9;font-size:13px;line-height:1.7}.hero-aside strong{display:block;margin-bottom:10px;color:white;font:500 24px/1.1 var(--serif)}.catalog{padding:70px 0 100px}.catalog-head{display:grid;grid-template-columns:1fr auto;gap:28px;align-items:end;margin-bottom:34px}.catalog h2,.principle h2{margin:0;font:400 clamp(36px,6vw,72px)/.95 var(--serif);letter-spacing:-.04em}.catalog-head p{max-width:600px;margin:16px 0 0;color:var(--muted);line-height:1.7}.controls{display:flex;gap:10px;align-items:center}.search{width:min(360px,54vw);padding:12px 14px;border:1px solid var(--line);border-radius:0;background:transparent;color:var(--ink)}.search:focus{outline:2px solid var(--gold);outline-offset:2px}.count{color:var(--muted);white-space:nowrap}.shelves{display:grid;grid-template-columns:repeat(3,1fr);border-top:1px solid var(--line);border-left:1px solid var(--line)}.book{position:relative;min-height:380px;padding:30px 28px 26px;border-right:1px solid var(--line);border-bottom:1px solid var(--line);background:rgba(255,255,255,.17);transition:background .25s ease,transform .25s ease}.book:hover{z-index:2;background:#f8f3e9;transform:translateY(-4px);box-shadow:0 18px 40px rgba(28,25,19,.1)}.book:before{content:"";position:absolute;top:0;left:0;width:5px;height:100%;background:var(--book-accent)}.ordinal{color:var(--book-accent);font:700 10px/1 var(--mono);letter-spacing:.18em}.book h3{margin:62px 0 12px;font:400 clamp(28px,3.3vw,43px)/.98 var(--serif);letter-spacing:-.035em}.series{min-height:35px;color:var(--muted);font-size:12px;letter-spacing:.08em;text-transform:uppercase}.description{margin:22px 0;color:#474239;font:400 16px/1.55 var(--serif)}.book-foot{position:absolute;left:28px;right:26px;bottom:25px;display:flex;justify-content:space-between;gap:14px;padding-top:16px;border-top:1px solid var(--line);color:var(--muted);font:600 9px/1.45 var(--mono);letter-spacing:.08em;text-transform:uppercase}.empty{grid-column:1/-1;padding:60px;border-right:1px solid var(--line);border-bottom:1px solid var(--line);text-align:center;color:var(--muted)}.principle-wrap{color:#efe8d9;background:#263024}.principle{display:grid;grid-template-columns:.9fr 1.1fr;gap:70px;padding:80px 0}.principle p{margin:0;color:#cbd1c4;font:400 20px/1.65 var(--serif)}.principle code{color:#e5bd74;font:500 11px/1.5 var(--mono);letter-spacing:.12em;text-transform:uppercase}footer{display:flex;justify-content:space-between;gap:30px;padding:34px 0;color:#958e80;font:600 9px/1.5 var(--mono);letter-spacing:.12em;text-transform:uppercase}body:after{content:"";position:fixed;inset:0;pointer-events:none;z-index:99;opacity:.035;background-image:url("data:image/svg+xml,%3Csvg xmlns='http://www.w3.org/2000/svg' width='80' height='80'%3E%3Cfilter id='n'%3E%3CfeTurbulence type='fractalNoise' baseFrequency='.9' numOctaves='3' stitchTiles='stitch'/%3E%3C/filter%3E%3Crect width='100%25' height='100%25' filter='url(%23n)' opacity='.45'/%3E%3C/svg%3E")}
    .book{padding-bottom:96px}.retail-link{display:inline-block;margin-top:2px;color:#73511e;font:700 9px/1 var(--mono);letter-spacing:.14em;text-decoration-thickness:1px;text-underline-offset:4px;text-transform:uppercase}
    @media(max-width:900px){.hero{grid-template-columns:1fr}.hero-aside{max-width:540px}.shelves{grid-template-columns:repeat(2,1fr)}.principle{grid-template-columns:1fr}.catalog-head{grid-template-columns:1fr}.controls{justify-content:space-between}.search{width:min(480px,70vw)}}
    @media(max-width:600px){nav,.hero,.catalog,.principle,footer{width:min(100% - 24px,1240px)}.mast{min-height:auto}.hero{padding:84px 0 54px}.hero h1{font-size:clamp(54px,18vw,86px)}nav a{display:none}.shelves{grid-template-columns:1fr}.book{min-height:340px}.catalog{padding-top:54px}.controls{align-items:flex-start;flex-direction:column}.search{width:100%}.principle{gap:34px;padding:60px 0}footer{display:block}footer span{display:block;margin-top:8px}}
    @media(prefers-reduced-motion:reduce){html{scroll-behavior:auto}.book{transition:none}}
  </style>
</head>
<body>
  <header class="mast">
    <nav><div class="wordmark"><b>M</b>MobleyBooks</div><a href="#catalog">Explore the catalog</a></nav>
    <section class="hero">
      <div><div class="eyebrow">The public collection / editorially cleared</div><h1>Stories with <em>worlds</em> inside.</h1><p class="hero-copy">Science fiction, fantasy, thrillers, and strange new mythologies—curated from the MobleyBooks archive and presented only when the underlying work can be verified.</p></div>
      <aside class="hero-aside"><strong>${CATALOG.title_count} works in the opening collection.</strong>Every entry is backed by a readable manuscript found on the Mac, the Dell index, or connected Google Drive. This is a catalog of real artifacts, not generated shelf filler.</aside>
    </section>
  </header>
  <main>
    <section class="catalog" id="catalog">
      <header class="catalog-head"><div><div class="kicker">Browse / discover</div><h2>The collection</h2><p>Search by title, author, series, or genre. Verified retail editions include direct links; other statuses describe the source artifact we reviewed.</p></div><div class="controls"><label><span class="kicker">Search titles</span><input class="search" id="search" type="search" autocomplete="off" placeholder="Try “fantasy” or “Ron Helms”"></label><div class="count" id="count"></div></div></header>
      <div class="shelves" id="shelves" aria-live="polite"></div>
    </section>
    <div class="principle-wrap"><section class="principle"><div><code>Editorial rule / default deny</code><h2>The archive is private. The library is deliberate.</h2></div><p>MobleyBooks searches broadly but publishes narrowly. A discovered file never becomes a public title automatically. Each entry must have a readable source, grounded metadata, and an explicit workplace-safe editorial decision.</p></section></div>
  </main>
  <footer><span>MobleyBooks / Media division</span><span>Catalog ${CATALOG.schema_version} / Updated ${CATALOG.updated_at.slice(0,10)}</span></footer>
  <script>
    const catalog=${catalogPayload};
    const shelves=document.getElementById('shelves');
    const search=document.getElementById('search');
    const count=document.getElementById('count');
    const esc=(value)=>String(value).replace(/[&<>"']/g,(char)=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[char]));
    function render(){
      const query=search.value.trim().toLowerCase();
      const titles=catalog.titles.filter((book)=>[book.title,book.author,book.series,book.genre,book.status].join(' ').toLowerCase().includes(query));
      count.textContent=titles.length+' / '+catalog.title_count+' works';
      shelves.innerHTML=titles.length?titles.map((book,index)=>'<article class="book" style="--book-accent:'+esc(book.accent)+'"><div class="ordinal">'+String(index+1).padStart(2,'0')+'</div><h3>'+esc(book.title)+'</h3><div class="series">'+esc(book.series)+' / '+esc(book.series_position)+'</div><p class="description">'+esc(book.description)+'</p>'+(book.retail_url?'<a class="retail-link" href="'+esc(book.retail_url)+'" target="_blank" rel="noopener noreferrer">View published edition</a>':'')+'<div class="book-foot"><span>'+esc(book.author)+'<br>'+esc(book.genre)+'</span><span>'+esc(book.status)+'<br>'+Number(book.words).toLocaleString()+' words</span></div></article>').join(''):'<div class="empty">No approved public works match that search.</div>';
    }
    search.addEventListener('input',render);render();
  </script>
</body>
</html>`;
}

function sitemap() {
  return `<?xml version="1.0" encoding="UTF-8"?>\n<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9"><url><loc>https://mobleybooks.com/</loc></url><url><loc>https://mobleybooks.com/catalog.json</loc></url></urlset>\n`;
}

export function handleMobleyBooks(request) {
  if (!new Set(["GET", "HEAD"]).has(request.method)) {
    return withHeaders("Method Not Allowed\n", request, { status: 405, headers: { Allow: "GET, HEAD", "Content-Type": "text/plain; charset=utf-8" } });
  }
  const url = new URL(request.url);
  if (url.pathname === "/health") return json({ status: "ok", product: "mobleybooks-library", title_count: CATALOG.title_count, catalog_version: CATALOG.schema_version }, request);
  if (url.pathname === "/catalog.json") return json(CATALOG, request);
  if (url.pathname === "/robots.txt") return withHeaders("User-agent: *\nAllow: /\nSitemap: https://mobleybooks.com/sitemap.xml\n", request, { headers: { "Cache-Control": "public, max-age=3600", "Content-Type": "text/plain; charset=utf-8" } });
  if (url.pathname === "/sitemap.xml") return withHeaders(sitemap(), request, { headers: { "Cache-Control": "public, max-age=3600", "Content-Type": "application/xml; charset=utf-8" } });
  if (url.pathname === "/favicon.svg") return withHeaders(`<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 64 64"><rect width="64" height="64" rx="9" fill="#11140f"/><path fill="#c2934d" d="M13 15h15c7 0 11 3 11 9 0 4-2 7-6 8 5 1 8 4 8 9 0 7-5 10-13 10H13zm10 7v7h5c3 0 4-1 4-4 0-2-1-3-4-3zm0 14v8h6c3 0 5-1 5-4s-2-4-5-4z"/></svg>`, request, { headers: { "Cache-Control": "public, max-age=86400", "Content-Type": "image/svg+xml; charset=utf-8" } });
  if (url.pathname !== "/" && url.pathname !== "/index.html") return withHeaders("Not Found\n", request, { status: 404, headers: { "Content-Type": "text/plain; charset=utf-8" } });
  return withHeaders(renderHtml(), request, { headers: { "Cache-Control": "public, max-age=300, must-revalidate", "Content-Type": "text/html; charset=utf-8" } });
}
