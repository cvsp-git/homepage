/* CVSP Lab site script: mobile menu, publication filters, gallery filter, hero Gaussian field. */
(function () {
  "use strict";

  /* ---------- mobile menu ---------- */
  var toggle = document.querySelector(".nav-toggle");
  if (toggle) {
    toggle.addEventListener("click", function () {
      var open = document.body.classList.toggle("nav-open");
      toggle.setAttribute("aria-expanded", open ? "true" : "false");
    });
    document.querySelectorAll(".site-nav a").forEach(function (a) {
      a.addEventListener("click", function () {
        document.body.classList.remove("nav-open");
        toggle.setAttribute("aria-expanded", "false");
      });
    });
  }

  /* ---------- publications ---------- */
  var pubs = document.querySelector("[data-pubs]");
  if (pubs) {
    var state = { scope: "intl", type: "all", q: "" };
    var tabs = pubs.querySelectorAll("[data-scope]");
    var chips = pubs.querySelectorAll(".chip[data-type]");
    var search = pubs.querySelector("#pub-search");
    var empty = pubs.querySelector(".pub-empty");

    var apply = function () {
      var shown = 0;
      pubs.querySelectorAll("[data-scope-panel]").forEach(function (panel) {
        var active = panel.getAttribute("data-scope-panel") === state.scope;
        panel.hidden = !active;
        if (!active) return;
        panel.querySelectorAll(".pub-year").forEach(function (sec) {
          var visible = 0;
          sec.querySelectorAll(".pub").forEach(function (li) {
            var ok = (state.type === "all" || li.dataset.type === state.type) &&
                     (!state.q || li.dataset.search.indexOf(state.q) !== -1);
            li.hidden = !ok;
            if (ok) visible++;
          });
          sec.hidden = visible === 0;
          var c = sec.querySelector(".year-label .count");
          if (c) c.textContent = visible;
          shown += visible;
        });
      });
      if (empty) empty.hidden = shown !== 0;
    };

    tabs.forEach(function (t) {
      t.addEventListener("click", function () {
        state.scope = t.dataset.scope;
        tabs.forEach(function (x) { x.setAttribute("aria-selected", x === t ? "true" : "false"); });
        apply();
      });
    });
    chips.forEach(function (c) {
      c.addEventListener("click", function () {
        state.type = c.dataset.type;
        chips.forEach(function (x) { x.classList.toggle("is-on", x === c); });
        apply();
      });
    });
    if (search) search.addEventListener("input", function () { state.q = search.value.trim().toLowerCase(); apply(); });
  }

  /* ---------- gallery ---------- */
  var gf = document.querySelector("[data-gallery-filter]");
  if (gf) {
    var gchips = gf.querySelectorAll(".chip");
    gchips.forEach(function (c) {
      c.addEventListener("click", function () {
        var cat = c.dataset.cat;
        gchips.forEach(function (x) { x.classList.toggle("is-on", x === c); });
        document.querySelectorAll(".gallery-grid .g-tile").forEach(function (t) {
          t.hidden = !(cat === "all" || t.classList.contains("g-" + cat));
        });
      });
    });
  }

  /* ---------- home photo slider ---------- */
  document.querySelectorAll("[data-slider]").forEach(function (sl) {
    var slides = sl.querySelectorAll(".slide"), dots = sl.querySelectorAll(".slider-dots button");
    if (slides.length < 2) return;
    var i = 0, timer = null;
    var still = window.matchMedia && window.matchMedia("(prefers-reduced-motion: reduce)").matches;
    var show = function (n) {
      i = (n + slides.length) % slides.length;
      slides.forEach(function (s, k) { s.classList.toggle("is-active", k === i); s.setAttribute("aria-hidden", k === i ? "false" : "true"); });
      dots.forEach(function (d, k) { if (k === i) d.setAttribute("aria-current", "true"); else d.removeAttribute("aria-current"); });
    };
    var play = function () { if (!still) { clearInterval(timer); timer = setInterval(function () { show(i + 1); }, 5000); } };
    var stop = function () { clearInterval(timer); };
    sl.querySelector("[data-prev]").addEventListener("click", function () { show(i - 1); play(); });
    sl.querySelector("[data-next]").addEventListener("click", function () { show(i + 1); play(); });
    dots.forEach(function (d, k) { d.addEventListener("click", function () { show(k); play(); }); });
    sl.addEventListener("mouseenter", stop); sl.addEventListener("mouseleave", play);
    sl.addEventListener("focusin", stop); sl.addEventListener("focusout", play);
    show(0); play();
  });

  /* ---------- hero: a living 4D Gaussian field ---------- */
  var canvas = document.getElementById("splat-canvas");
  if (!canvas || !canvas.getContext) return;
  var ctx = canvas.getContext("2d");
  var reduce = window.matchMedia && window.matchMedia("(prefers-reduced-motion: reduce)").matches;
  var countEl = document.getElementById("splat-count");
  var timeEl = document.getElementById("splat-time");

  // soft gaussian sprites, one per palette color
  var palette = [[47, 123, 255], [63, 211, 224], [150, 190, 255], [255, 255, 255]];
  var sprites = palette.map(function (c) {
    var s = document.createElement("canvas"); s.width = s.height = 64;
    var g = s.getContext("2d");
    var grad = g.createRadialGradient(32, 32, 0, 32, 32, 32);
    grad.addColorStop(0, "rgba(" + c + ",1)");
    grad.addColorStop(0.35, "rgba(" + c + ",0.45)");
    grad.addColorStop(1, "rgba(" + c + ",0)");
    g.fillStyle = grad; g.fillRect(0, 0, 64, 64);
    return s;
  });

  // scene: a rippling terrain (the "world") plus a floating object cluster (the "thing in it")
  var pts = [];
  var GRID = 34;
  for (var i = 0; i < GRID; i++) {
    for (var j = 0; j < GRID; j++) {
      var u = i / (GRID - 1) * 2 - 1, v = j / (GRID - 1) * 2 - 1;
      if (u * u + v * v > 1.05) continue; // round patch
      pts.push({ kind: 0, x: u + (Math.random() - .5) * .04, z: v + (Math.random() - .5) * .04, y: 0, s: .9 + Math.random() * .5 });
    }
  }
  // optional mascot: <canvas data-mascot="..."> turns a picture into gaussians standing on the field.
  // Without it, a floating torus is drawn instead.
  var mascotSrc = canvas.getAttribute("data-mascot");
  var mascotMode = false, assembleT = 0;
  var colorSprites = {};
  var spriteFor = function (r, g, b) {
    var key = (r >> 4) + "," + (g >> 4) + "," + (b >> 4);
    if (colorSprites[key]) return colorSprites[key];
    var c = [(r >> 4) * 17, (g >> 4) * 17, (b >> 4) * 17];
    var s = document.createElement("canvas"); s.width = s.height = 32;
    var gx = s.getContext("2d");
    var grad = gx.createRadialGradient(16, 16, 0, 16, 16, 16);
    grad.addColorStop(0, "rgba(" + c + ",1)");
    grad.addColorStop(0.5, "rgba(" + c + ",0.7)");
    grad.addColorStop(1, "rgba(" + c + ",0)");
    gx.fillStyle = grad; gx.fillRect(0, 0, 32, 32);
    colorSprites[key] = s;
    return s;
  };
  var addTorus = function () {
    for (var k = 0; k < 260; k++) {
      var a = Math.random() * Math.PI * 2, b = Math.random() * Math.PI * 2;
      var R = .34, r = .12 + Math.random() * .03;
      pts.push({ kind: 1, a: a, b: b, R: R, r: r, s: .7 + Math.random() * .6, c: Math.random() < 0.06 ? 3 : 1 });
    }
  };
  var addMascot = function (img) {
    var SH = 124; // sample height in pixels
    var SW = Math.max(1, Math.round(img.naturalWidth / img.naturalHeight * SH));
    var oc = document.createElement("canvas"); oc.width = SW; oc.height = SH;
    var ox = oc.getContext("2d");
    ox.drawImage(img, 0, 0, SW, SH);
    var data;
    try { data = ox.getImageData(0, 0, SW, SH).data; } catch (e) { return false; }
    var HEIGHT = 0.78, unit = HEIGHT / SH, step = 2, added = 0;
    for (var py = 0; py < SH; py += step) {
      for (var px = 0; px < SW; px += step) {
        var o = (py * SW + px) * 4;
        if (data[o + 3] < 140) continue;
        var nx = (px - SW / 2) / (SW / 2), ny = (py - SH / 2) / (SH / 2);
        var bulge = 0.16 * Math.sqrt(Math.max(0, 1 - (nx * nx * 0.8 + ny * ny * 0.6)));
        var tx = (px - SW / 2) * unit, ty = 0.12 + (SH - py) * unit, tz = bulge + (Math.random() - .5) * .03;
        pts.push({
          kind: 2, tx: tx, ty: ty, tz: tz,
          // start scattered, then assemble
          sx0: (Math.random() - .5) * 2.4, sy0: Math.random() * 1.6 - .2, sz0: (Math.random() - .5) * 2.4,
          spr: spriteFor(data[o], data[o + 1], data[o + 2]), s: .85 + Math.random() * .3, delay: Math.random() * .6
        });
        added++;
      }
    }
    return added > 0;
  };
  var setCount = function () { if (countEl) countEl.textContent = pts.length.toLocaleString("en-US"); };
  if (mascotSrc) {
    var mimg = new Image();
    mimg.onload = function () {
      if (addMascot(mimg)) { mascotMode = true; assembleT = reduce ? 10 : 0; yaw = 0; pitch = 0.22; if (reduce) draw(3); }
      else addTorus();
      setCount();
    };
    mimg.onerror = function () { addTorus(); setCount(); };
    mimg.src = mascotSrc;
  } else { addTorus(); }
  setCount();

  var W = 0, H = 0, dpr = 1, cx = 0, cy = 0, scale = 1;
  var resize = function () {
    dpr = Math.min(window.devicePixelRatio || 1, 2);
    W = canvas.clientWidth; H = canvas.clientHeight;
    canvas.width = Math.round(W * dpr); canvas.height = Math.round(H * dpr);
    ctx.setTransform(dpr, 0, 0, dpr, 0, 0);
    var wide = W > 900;
    if (canvas.hasAttribute("data-mascot")) {
      // centered stage at the top of the hero; the lab name sits below it
      var stage = parseFloat(getComputedStyle(canvas.parentNode).getPropertyValue("--stage")) || 400;
      cx = W * 0.5;
      cy = stage - 80;
      scale = Math.min(W * 0.5, stage * 0.78);
      return;
    }
    cx = wide ? W * 0.70 : W * 0.5;
    cy = wide ? H * 0.50 : H * 0.86;
    scale = Math.min(wide ? W * 0.30 : W * 0.42, H * 0.62);
  };

  var yaw = 0.6, pitch = 0.42, drag = null, spin = 0.12;
  canvas.addEventListener("pointerdown", function (e) { drag = { x: e.clientX, y: e.clientY, yaw: yaw, pitch: pitch }; canvas.classList.add("dragging"); });
  window.addEventListener("pointerup", function () { drag = null; canvas.classList.remove("dragging"); });
  window.addEventListener("pointermove", function (e) {
    if (!drag) return;
    yaw = drag.yaw + (e.clientX - drag.x) * 0.006;
    pitch = Math.max(0.1, Math.min(1.1, drag.pitch + (e.clientY - drag.y) * 0.004));
  });

  var buf = [];
  var draw = function (t) {
    ctx.clearRect(0, 0, W, H);
    ctx.globalCompositeOperation = "lighter";
    var cyw = Math.cos(yaw), syw = Math.sin(yaw), cp = Math.cos(pitch), sp = Math.sin(pitch);
    buf.length = 0;
    for (var n = 0; n < pts.length; n++) {
      var p = pts[n], x, y, z, col;
      if (p.kind === 0) {
        x = p.x; z = p.z;
        if (mascotMode) { x *= 0.85; z *= 0.85; }
        y = Math.sin(x * 3.1 + t * 0.9) * Math.cos(z * 2.6 - t * 0.7) * 0.12 + Math.sin((x + z) * 5 + t * 1.6) * 0.025;
        col = y > 0.06 ? 1 : (y > -0.02 ? 2 : 0);
      } else if (p.kind === 2) {
        var e = Math.min(1, Math.max(0, (assembleT - p.delay) / 1.8));
        e = 1 - Math.pow(1 - e, 3);
        var wob = Math.sin(t * 1.4 + p.tx * 6) * 0.004;
        x = p.sx0 + (p.tx - p.sx0) * e;
        y = p.sy0 + (p.ty + wob + Math.sin(t * 1.1) * 0.012 - p.sy0) * e;
        z = p.sz0 + (p.tz - p.sz0) * e;
        col = -1;
      } else {
        var bb = p.b + t * 0.6;
        var rx = (p.R + p.r * Math.cos(bb)) * Math.cos(p.a), ry = p.r * Math.sin(bb), rz = (p.R + p.r * Math.cos(bb)) * Math.sin(p.a);
        // tilt and bob the torus
        var tilt = 0.9 + Math.sin(t * 0.5) * 0.15;
        var y2 = ry * Math.cos(tilt) - rz * Math.sin(tilt), z2 = ry * Math.sin(tilt) + rz * Math.cos(tilt);
        x = rx; y = y2 + 0.52 + Math.sin(t * 0.8) * 0.04; z = z2;
        col = p.c;
      }
      // rotate yaw (around y), then pitch (around x)
      var X = x * cyw - z * syw, Z = x * syw + z * cyw;
      var Y = y * cp - Z * sp, Z2 = y * sp + Z * cp;
      var persp = 2.6 / (2.6 + Z2);
      buf.push({ sx: cx + X * scale * persp, sy: cy - Y * scale * persp, d: Z2, r: p.s * persp, c: col, k: p.kind, spr: p.spr });
    }
    // in mascot mode the field is drawn first and the mascot on top, so it stays readable
    buf.sort(function (m, n2) { if (mascotMode && (m.k === 2) !== (n2.k === 2)) return m.k === 2 ? 1 : -1; return n2.d - m.d; });
    for (var q = 0; q < buf.length; q++) {
      var b = buf[q];
      if (b.k === 2) {
        var ms = 12 * b.r * (scale / 320);
        ctx.globalCompositeOperation = "source-over";
        ctx.globalAlpha = 0.85;
        ctx.drawImage(b.spr, b.sx - ms / 2, b.sy - ms / 2, ms, ms);
        ctx.globalCompositeOperation = "lighter";
        continue;
      }
      var size = (b.k === 1 ? 16 : 22) * b.r * (scale / 320);
      ctx.globalAlpha = Math.max(0.05, Math.min(mascotMode ? 0.3 : 0.55, (mascotMode ? 0.24 : 0.42) - b.d * 0.18));
      ctx.drawImage(sprites[b.c], b.sx - size / 2, b.sy - size / 2, size, size);
    }
    ctx.globalAlpha = 1;
    ctx.globalCompositeOperation = "source-over";
    if (timeEl) timeEl.textContent = t.toFixed(2);
  };

  var visible = true, t0 = performance.now(), last = t0, simT = 0;
  var loop = function (now) {
    var dt = Math.min(0.05, (now - last) / 1000); last = now;
    if (visible && !document.hidden) {
      simT += dt;
      if (mascotMode) { assembleT += dt; if (!drag) yaw += (Math.sin(simT * 0.45) * 0.55 - yaw) * Math.min(1, dt * 1.5); }
      else if (!drag) yaw += spin * dt;
      draw(simT);
    }
    requestAnimationFrame(loop);
  };

  resize();
  window.addEventListener("resize", resize);
  if ("IntersectionObserver" in window) {
    new IntersectionObserver(function (es) { visible = es[0].isIntersecting; }).observe(canvas);
  }
  if (reduce) { draw(1.5); } else { requestAnimationFrame(loop); }
})();
