/* Shared live-market loader for ME departments.
   Reads media/live_listings.json, renders the department's verified
   live-listing destinations as real linked cards. Each card links OUT to
   the actual marketplace where the object is for sale now.
   Live engine = the verified manifest; not invented data. */
(function(){
  function esc(s){var d=document.createElement("div");d.textContent=s==null?"":String(s);return d.innerHTML;}
  function card(it){
    var dest=it.url||"#";
    var st=((it.status||"").toLowerCase());
    var tag = st==="live" ? "live" : (st==="wall" ? "market" : "listed");
    var ver = it.verified ? "verified " + it.verified : "current";
    // Image avatar: use a department keyword chip instead of a photoshopped card
    return '<a class="mlink" href="'+esc(dest)+'" target="_blank" rel="noopener">'+
      '<div class="ml-tag">'+tag+'</div>'+
      '<div class="ml-name">'+esc(it.name)+'</div>'+
      '<div class="ml-mp">'+esc(it.marketplace||"the market")+'</div>'+
      '<div class="ml-go">View listings \u2197 <span>'+esc(ver)+'</span></div>'+
    '</a>';
  }
  function load(dept, targetId){
    var t=document.getElementById(targetId); if(!t) return;
    fetch("media/live_listings.json",{cache:"no-store"}).then(function(r){return r.json();}).then(function(d){
      var lots=(d.departments&&d.departments[dept])||[];
      var live=lots.slice(0,9);
      if(!live.length){t.innerHTML='<div class="mload">The market is being updated.</div>';return;}
      t.innerHTML=live.map(card).join("");
    }).catch(function(){t.innerHTML='<div class="mload">The live market is momentarily unavailable.</div>';});
  }
  window.__meMarketLoad=load;
})();
