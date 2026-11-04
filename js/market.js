/* ME shared market layer — one component, any department.
   Consumes out/feed.json (or any source-of-truth manifest with the same shape)
   and renders the MARKET frame: facet rail ABOVE a borderless image-led grid,
   bold price below the title, and the three separate scores (value/rarity/
   investment) as metadata — never blended, exactly as the rubric demands.

   Department pages only declare:
     ME.market({ feed:'out/feed.json', dept:'art', grid:'#artGrid', rail:'#artRail',
                 records:'#artTable', photos:['media/img/art_wave.jpg', ...] });

   Falls back gracefully: no feed -> loads the local manifest; nothing -> message.
   Price/anatomy follow the reference brief (1stDibs/Artsy borderless card shape). */
(function (window) {
  var sk = { script: 1, style: 1, noscript: 1, svg: 1 };
  function esc(s) { var d = document.createElement('div'); d.textContent = s == null ? '' : String(s); return d.innerHTML; }
  function money(val, cur) {
    if (val == null) return 'on request';
    var n = Math.round(Number(val));
    if (typeof Intl !== 'undefined') {
      try { return new Intl.NumberFormat('en-US', { style: 'currency', currency: String(cur || 'USD'), maximumFractionDigits: 0 }).format(n); }
      catch (e) { /* fall through */ }
    }
    var sym = { 'GBP': '\u00a3', 'EUR': '\u20ac', 'USD': '$' }[String(cur || 'USD').toUpperCase()] || '$';
    return sym + n.toLocaleString('en-US');
  }

  function scoreChip(label, val) {
    if (val == null) return '';
    var v = Math.round(Number(val));
    return '<span class="schip ' + (v >= 4 ? 'hi' : v <= 2 ? 'lo' : 'md') + '">' +
      '<i>' + esc(label) + '</i><b>' + v + '</b></span>';
  }

  function makeCard(it, photo) {
    var img = it.image && it.image.indexOf('/') !== -1 ? it.image : (photo || '');
    var im = img
      ? '<div class="im"><img src="' + esc(img) + '" alt="" loading="lazy"/><span class="live">LIVE</span></div>'
      : '<div class="im noph"><span class="live">LIVE</span></div>';
    var spec = it.spec || {};
    var s = it.scores || {};
    var meta = [];
    if (it.condition) meta.push(esc(it.condition));
    if (spec.est_low != null && spec.est_high != null)
      meta.push('est ' + esc(spec.est_low) + '–' + esc(spec.est_high));
    if (spec.hammer_to_est != null)
      meta.push('hammer ' + (Number(spec.hammer_to_est) >= 1 ? '>' : '<') + ' est ×' + esc(spec.hammer_to_est));
    var chips = scoreChip('value', s.value) + scoreChip('rarity', s.rarity) + scoreChip('invest', s.investment);
    var rank = it.rank ? '<div class="rnum">No. ' + esc(it.rank) + '</div>' : '';
    return '<a class="mcard" href="' + esc(it.link || '#') + '" target="_blank" rel="noopener">' +
      im +
      '<div class="bd">' +
      rank +
      '<div class="n">' + esc(it.title) + '</div>' +
      (meta.length ? '<div class="meta">' + meta.join(' · ') + '</div>' : '') +
      '<div class="p">' + money(it.ask, it.currency) + '</div>' +
      (chips ? '<div class="chips">' + chips + '</div>' : '') +
      '<div class="sr">' + esc(it.source || 'the market') + ' · <span>' + (it.link_state === 'fallback' ? 'search' : 'view') + '</span></div>' +
      '</div></a>';
  }

  function buildRail(railEl, items) {
    if (!railEl) return;
    // derive facets from source + condition + rarity band — data-driven, no hardcode
    var facets = {};
    items.forEach(function (it) {
      var key = (it.source || '').toLowerCase();
      if (!key) return;
      facets[key] = facets[key] || { count: 0 };
      facets[key].count++;
    });
    var keys = Object.keys(facets).sort();
    var all = '<span class="rail-chip all on">All<span class="cnt">' + items.length + '</span></span>';
    var chips = all + keys.map(function (k) {
      return '<span class="rail-chip" data-f="' + esc(k) + '">' + esc(k.replace(/^www\./, '').split('.')[0]) +
        '<span class="cnt">' + facets[k].count + '</span></span>';
    }).join('');
    railEl.innerHTML = '<span class="rail-label">Market ·</span>' + chips;
  }

  function renderAll(cfg, items) {
    var grid = document.querySelector(cfg.grid);
    var list = items.slice(0, cfg.limit || 30);
    if (grid) {
      grid.innerHTML = list.map(function (it, i) {
        var ph = cfg.photos && cfg.photos.length ? cfg.photos[i % cfg.photos.length] : null;
        return makeCard(it, ph);
      }).join('') || '<div class="mload">The market is being updated.</div>';
    }
    if (cfg.records) {
      var rEl = document.querySelector(cfg.records);
      if (rEl) {
        var top = list.slice(0, 10);
        rEl.innerHTML = top.map(function (it) {
          return '<a class="rrow" href="' + esc(it.link || '#') + '" target="_blank" rel="noopener">' +
            '<div class="rdesc">' + esc(it.title) + '</div>' +
            '<div class="rprice"><span>' + (it.scores ? 'v' + (it.scores.value != null ? it.scores.value.toFixed(1) : '-') + ' · r' + (it.scores.rarity != null ? it.scores.rarity.toFixed(1) : '-') + ' · i' + (it.scores.investment != null ? it.scores.investment.toFixed(1) : '-') : '') + '</span>' +
            money(it.ask, it.currency) + '</div></a>';
        }).join('');
      }
    }
  }

  function load(cfg) {
    var api = cfg.feed || 'out/feed.json';
    return fetch(api, { cache: 'no-store' }).then(function (r) { return r.ok ? r.json() : Promise.reject(); })
      .then(function (d) {
        var items = (d.departments && d.departments[cfg.dept]) || d.items || d;
        if (!Array.isArray(items)) items = [];
        items = items.filter(function (it) { return it && it.rank != null; })
          .sort(function (a, b) { return (a.rank || 0) - (b.rank || 0); });
        var railEl = document.querySelector(cfg.rail);
        buildRail(railEl, items);
        if (railEl) {
          railEl.addEventListener('click', function (e) {
            var chip = e.target.closest('.rail-chip');
            if (!chip) return;
            Array.prototype.forEach.call(railEl.querySelectorAll('.rail-chip'), function (c) { c.classList.remove('on'); });
            if (chip.classList.contains('all')) { chip.classList.add('on'); renderAll(cfg, items); return; }
            chip.classList.add('on');
            var f = chip.getAttribute('data-f');
            renderAll(cfg, items.filter(function (it) { return (it.source || '').toLowerCase() === f; }));
          });
        }
        renderAll(cfg, items);
      })
      .catch(function () {
        Array.prototype.forEach.call(document.querySelectorAll(cfg.grid), function (g) {
          g.innerHTML = '<div class="mload">The live market is momentarily unavailable.</div>';
        });
      });
  }

  window.ME = window.ME || {};
  window.ME.market = load;
})(window);
