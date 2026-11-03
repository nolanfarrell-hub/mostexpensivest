/* Shared live-market loader for ME departments — image-led cards (Time/Art parity).
   Reads media/live_listings.json, renders the department's verified live-listing
   destinations as designed photo cards, each linking OUT to the actual marketplace.
   Pass a per-department photo set (deptPhotos) so the grid reads as a curated
   market surface, not a text list. Live engine = the verified manifest. */
(function(){
  function esc(s){var d=document.createElement("div");d.textContent=s==null?"":String(s);return d.innerHTML;}
  function card(it, imgSrc){
    var dest=it.url||"#";
    var st=((it.status||"").toLowerCase());
    var tag = st==="live" ? "LIVE" : (st==="wall" ? "MARKET" : "LISTED");
    var ver = it.verified ? "verified "+it.verified : "current";
    var mp = it.marketplace || "the market";
    var img = imgSrc;
    var im = img
      ? '<div class="im"><img src="'+esc(img)+'" alt="" loading="lazy"/><span class="live">'+tag+'</span></div>'
      : '<div class="im noph"><span class="live">'+tag+'</span></div>';
    return '<a class="mcard" href="'+esc(dest)+'" target="_blank" rel="noopener">'+im+
      '<div class="bd"><div class="n">'+esc(it.name)+'</div>'+
      '<div class="ref">'+esc(mp)+'</div>'+
      '<div class="sr">View listings \u2197 <span>'+esc(ver)+'</span></div></div></a>';
  }
  function load(dept, targetId, photos){
    var t=document.getElementById(targetId); if(!t) return;
    t.innerHTML='<div class="mload" style="grid-column:1/-1">reading the market\u2026</div>';
    fetch("media/live_listings.json",{cache:"no-store"}).then(function(r){return r.json();}).then(function(d){
      var lots=(d.departments&&d.departments[dept])||[];
      var live=lots.slice(0,9);
      if(!live.length){t.innerHTML='<div class="mload" style="grid-column:1/-1">The market is being updated.</div>';return;}
      var order={"live":0,"market":1,"listed":2,"dead":3};
      live.sort(function(a,b){return ((order[a.status]??9)-(order[b.status]??9));});
      var list=live.map(function(it,i){
        var ph=photos&&photos.length ? photos[i%photos.length] : (it.img_url||"");
        return card(it, ph);
      });
      t.innerHTML=list.join("");
    }).catch(function(){t.innerHTML='<div class="mload" style="grid-column:1/-1">The live market is momentarily unavailable.</div>';});
  }
  window.__meMarketLoad=load;
})();
