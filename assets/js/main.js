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
  var GRID = canvas.hasAttribute("data-mascot") ? 0 : 34; // with a mascot, only the mascot is drawn
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
    var key = (r >> 3) + "," + (g >> 3) + "," + (b >> 3);
    if (colorSprites[key]) return colorSprites[key];
    var c = [(r >> 3) << 3, (g >> 3) << 3, (b >> 3) << 3];
    var s = document.createElement("canvas"); s.width = s.height = 48;
    var gx = s.getContext("2d");
    var grad = gx.createRadialGradient(24, 24, 0, 24, 24, 24);
    // gaussian-like falloff
    grad.addColorStop(0, "rgba(" + c + ",1)");
    grad.addColorStop(0.25, "rgba(" + c + ",0.93)");
    grad.addColorStop(0.5, "rgba(" + c + ",0.62)");
    grad.addColorStop(0.75, "rgba(" + c + ",0.22)");
    grad.addColorStop(1, "rgba(" + c + ",0)");
    gx.fillStyle = grad; gx.fillRect(0, 0, 48, 48);
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
  // Sanjini as a 3D gaussian cloud: points come from assets/js/mascot-data.js
  // (made by tools/make_mascot_data.py: front, back and side surfaces of an inflated picture)
  var addMascotFromData = function () {
    var m = window.CVSP_MASCOT;
    if (!m || !m.data) return false;
    var bin = atob(m.data), dv = new DataView(new ArrayBuffer(bin.length));
    for (var q = 0; q < bin.length; q++) dv.setUint8(q, bin.charCodeAt(q));
    var thin = 1, stride = m.stride || 9, AX = m.ax || 3000;
    for (var k = 0; k < m.n; k += thin) {
      var o = k * stride;
      var tx = dv.getInt16(o, true) / 10000, ty = dv.getInt16(o + 2, true) / 10000, tz = -dv.getInt16(o + 4, true) / 10000; // +z is away from the camera
      pts.push({
        kind: 2, tx: tx, ty: ty, tz: tz,
        sx0: (Math.random() - .5) * 2.4, sy0: Math.random() * 1.6 - .2, sz0: (Math.random() - .5) * 2.4,
        spr: spriteFor(dv.getUint8(o + 6), dv.getUint8(o + 7), dv.getUint8(o + 8)),
        s: (thin > 1 ? 1.35 : 1) * (.95 + Math.random() * .1), delay: Math.random() * .6, op: 0.62 + Math.random() * 0.33,
        // ellipsoid axes (z flipped like the position); absent in old data = round splat
        ax: stride >= 15 ? [dv.getInt8(o + 9) / AX, dv.getInt8(o + 10) / AX, -dv.getInt8(o + 11) / AX,
                            dv.getInt8(o + 12) / AX, dv.getInt8(o + 13) / AX, -dv.getInt8(o + 14) / AX] : null
      });
    }
    return m.n > 0;
  };
  var startMascot = function () { mascotMode = true; assembleT = reduce ? 10 : 0; yaw = 0; pitch = 0.2; };
  var setCount = function () { if (countEl) countEl.textContent = pts.length.toLocaleString("en-US"); };
  var useMascot = !!mascotSrc && addMascotFromData();
  if (!useMascot) addTorus();
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
      scale = Math.min(W * 0.5, 343) / 3;
      cy = stage * 0.5 + scale * 0.5 + 10;
      return;
    }
    cx = wide ? W * 0.70 : W * 0.5;
    cy = wide ? H * 0.50 : H * 0.86;
    scale = Math.min(wide ? W * 0.30 : W * 0.42, H * 0.62);
  };

  var yaw = 0.6, pitch = 0.42, drag = null, spin = 0.12;
  // click (or tap) on the mascot: the gaussians burst apart and fly back
  var burstT = -1, scattered = false;
  var onMascot = function (e) {
    if (!mascotMode) return false;
    var r = canvas.getBoundingClientRect(), mx = e.clientX - r.left, my = e.clientY - r.top;
    return Math.abs(mx - cx) < scale * 0.45 && my > cy - scale * 1.0 && my < cy + scale * 0.05;
  };
  var burst = function () {
    if (burstT >= 0 && burstT < 0.55) return;
    if (scattered) {
      // second click: gather back into Sanjini
      for (var k = 0; k < pts.length; k++) if (pts[k].kind === 2) pts[k].delay = Math.random() * .25;
      scattered = false; assembleT = 0; burstT = -1;
      return;
    }
    for (var n = 0; n < pts.length; n++) {
      var p = pts[n];
      if (p.kind !== 2) continue;
      // fly outward from the body center, with some randomness
      var dx = p.tx + (Math.random() - .5) * .3, dy = p.ty - 0.45 + (Math.random() - .5) * .3, dz = p.tz + (Math.random() - .5) * .3;
      var len = Math.sqrt(dx * dx + dy * dy + dz * dz) || 1, dist = 0.3 + Math.random() * 0.5;
      p.sx0 = p.tx + dx / len * dist; p.sy0 = p.ty + dy / len * dist; p.sz0 = p.tz + dz / len * dist;
      p.delay = Math.random() * .35;
    }
    burstT = 0; scattered = true;
  };
  canvas.addEventListener("pointerdown", function (e) { drag = { x: e.clientX, y: e.clientY, yaw: yaw, pitch: pitch, moved: false }; canvas.classList.add("dragging"); });
  window.addEventListener("pointerup", function (e) {
    if (drag && !drag.moved && onMascot(e)) burst();
    drag = null; canvas.classList.remove("dragging");
  });
  canvas.addEventListener("pointermove", function (e) { if (!drag) canvas.style.cursor = onMascot(e) ? "pointer" : ""; });
  window.addEventListener("pointermove", function (e) {
    if (!drag) return;
    if (Math.abs(e.clientX - drag.x) + Math.abs(e.clientY - drag.y) > 6) drag.moved = true;
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
        var e;
        if (scattered) {
          // burst phase: from the shape out to the scattered positions, then stay there
          var u2 = Math.min(1, burstT / 0.55); e = 1 - (1 - Math.pow(1 - u2, 3));
        } else {
          e = Math.min(1, Math.max(0, (assembleT - p.delay) / 1.8));
        }
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
      var it = { sx: cx + X * scale * persp, sy: cy - Y * scale * persp, d: Z2, r: p.s * persp, c: col, k: p.kind, spr: p.spr, a: null, op: p.op };
      if (p.ax) {
        // project both ellipsoid axes to the screen (same rotation as the position, no translation)
        var A = p.ax, k2 = scale * persp;
        var ax1 = A[0] * cyw - A[2] * syw, az1 = A[0] * syw + A[2] * cyw, ay1 = A[1] * cp - az1 * sp;
        var ax2 = A[3] * cyw - A[5] * syw, az2 = A[3] * syw + A[5] * cyw, ay2 = A[4] * cp - az2 * sp;
        it.a = [ax1 * k2, -ay1 * k2, ax2 * k2, -ay2 * k2];
      }
      buf.push(it);
    }
    // in mascot mode the field is drawn first and the mascot on top, so it stays readable
    buf.sort(function (m, n2) { if (mascotMode && (m.k === 2) !== (n2.k === 2)) return m.k === 2 ? 1 : -1; return n2.d - m.d; });
    for (var q = 0; q < buf.length; q++) {
      var b = buf[q];
      if (b.k === 2) {
        ctx.globalCompositeOperation = "source-over";
        ctx.globalAlpha = b.op || 0.95;
        if (b.a) {
          // anisotropic gaussian: map the round sprite onto the projected ellipse
          var e4 = b.a, minA = 0.6;
          // keep a hair of thickness when an ellipse is seen edge-on
          var det = e4[0] * e4[3] - e4[1] * e4[2], l2 = Math.hypot(e4[2], e4[3]);
          var bx = e4[2], by = e4[3];
          if (Math.abs(det) < minA * Math.hypot(e4[0], e4[1])) { var l1 = Math.hypot(e4[0], e4[1]) || 1; bx = -e4[1] / l1 * minA; by = e4[0] / l1 * minA; }
          ctx.setTransform(dpr * e4[0], dpr * e4[1], dpr * bx, dpr * by, dpr * b.sx, dpr * b.sy);
          ctx.drawImage(b.spr, -1.5, -1.5, 3, 3);
          ctx.setTransform(dpr, 0, 0, dpr, 0, 0);
        } else {
          var ms = 9 * b.r * (scale / 320);
          ctx.drawImage(b.spr, b.sx - ms / 2, b.sy - ms / 2, ms, ms);
        }
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
      if (burstT >= 0) burstT = Math.min(0.55, burstT + dt);
      if (mascotMode) { assembleT += dt; if (!drag) yaw += (Math.sin(simT * 0.4) * 0.75 - yaw) * Math.min(1, dt * 1.5); }
      else if (!drag) yaw += spin * dt;
      draw(simT);
    }
    requestAnimationFrame(loop);
  };

  if (useMascot) startMascot();
  resize();
  window.addEventListener("resize", resize);
  if ("IntersectionObserver" in window) {
    new IntersectionObserver(function (es) { visible = es[0].isIntersecting; }).observe(canvas);
  }
  if (reduce) { draw(1.5); } else { requestAnimationFrame(loop); }
})();
