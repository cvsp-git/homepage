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
    /* 갤러리: 처음에는 STEP장만 보이고 "Load more"를 누를 때마다 STEP장씩 더 나옵니다 (분류를 바꾸면 다시 처음부터). */
    var STEP = 12, gcat = "gallery", shown = STEP;
    var gchips = gf.querySelectorAll(".chip"), gcards = document.querySelectorAll(".board-grid .bcard");
    var gmore = document.querySelector("[data-gallery-more]");
    var gapply = function () {
      var k = 0;
      gcards.forEach(function (t) {
        var match = gcat === "all" || t.classList.contains("bcard-" + gcat);
        t.hidden = !(match && k++ < shown);
      });
      if (gmore) gmore.hidden = k <= shown;
    };
    gchips.forEach(function (c) {
      c.addEventListener("click", function () {
        gcat = c.dataset.cat; shown = STEP;
        gchips.forEach(function (x) { x.classList.toggle("is-on", x === c); });
        gapply();
      });
    });
    if (gmore) gmore.addEventListener("click", function () { shown += STEP; gapply(); });
    gapply();
    /* gallery.html#conference 처럼 주소 끝에 분류를 붙이면 그 분류만 보여 줍니다. */
    var h = (location.hash || "").slice(1).toLowerCase();
    gchips.forEach(function (c) { if (h && c.dataset.cat === h) c.click(); });
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
  // the gaussian characters are drawn with WebGL (one draw call for all of them, smooth even on laptops);
  // without WebGL the same picture is drawn with the 2D canvas, one sprite per gaussian (slower)
  var gl = null, glx = null;
  if (canvas.hasAttribute("data-mascot")) {
    try {
      gl = canvas.getContext("webgl", { alpha: true, premultipliedAlpha: true, antialias: false, depth: false });
      glx = gl && gl.getExtension("ANGLE_instanced_arrays");
      if (!glx) gl = null;
    } catch (err) { gl = null; }
  }
  var ctx = gl ? null : canvas.getContext("2d");
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
  // true gaussian sprite: exp(-r^2/2) out to 3 sigma (used by trained gaussians)
  var gaussSprites = {};
  var gaussSprite = function (r, g, b) {
    var key = (r >> 2) + "," + (g >> 2) + "," + (b >> 2);
    if (gaussSprites[key]) return gaussSprites[key];
    var c = [(r >> 2) << 2, (g >> 2) << 2, (b >> 2) << 2];
    var s = document.createElement("canvas"); s.width = s.height = 64;
    var gx = s.getContext("2d");
    var grad = gx.createRadialGradient(32, 32, 0, 32, 32, 32);
    for (var i = 0; i <= 12; i++) { var t = i / 12; grad.addColorStop(t, "rgba(" + c + "," + Math.exp(-0.5 * 9 * t * t).toFixed(4) + ")"); }
    gx.fillStyle = grad; gx.fillRect(0, 0, 64, 64);
    gaussSprites[key] = s;
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
  // (trained by tools/train_mascot_gaussians.py; older point formats still render)
  // characters standing in a row: Sanjini in the middle, the Sanjini Friends (assets/js/friends-data.js) beside him.
  // ox = place along the row, s = size (guidebook proportions, a bit enlarged), ph = turn offset (0 = all face the same way)
  var groups = [{ key: "CVSP_MASCOT", ox: 0, s: 1, ph: 0 },
                { key: "CVSP_FRIEND_DAENY", ox: -0.95, s: 0.72, ph: 0 },
                { key: "CVSP_FRIEND_TORY", ox: 0.86, s: 0.6, ph: 0 },
                { key: "CVSP_FRIEND_BUDDY", ox: 1.42, s: 0.5, ph: 0 }];
  var addMascotFromData = function (m, gi) {
    if (!m || !m.data) return false;
    var bin = atob(m.data), dv = new DataView(new ArrayBuffer(bin.length));
    for (var q = 0; q < bin.length; q++) dv.setUint8(q, bin.charCodeAt(q));
    if (m.fmt === "gs3") {
      // trained 3D gaussians (tools/train_mascot_gaussians.py): position, rgb, opacity, 3 scales, rotation
      for (var g = 0; g < m.n; g++) {
        var o3 = g * 17, L = m.lmax - m.lmin;
        var sc = [Math.exp(m.lmin + dv.getUint8(o3 + 10) / 255 * L), Math.exp(m.lmin + dv.getUint8(o3 + 11) / 255 * L), Math.exp(m.lmin + dv.getUint8(o3 + 12) / 255 * L)];
        var qw = dv.getInt8(o3 + 13) / 127, qx = dv.getInt8(o3 + 14) / 127, qy = dv.getInt8(o3 + 15) / 127, qz = dv.getInt8(o3 + 16) / 127;
        var qn = Math.hypot(qw, qx, qy, qz) || 1; qw /= qn; qx /= qn; qy /= qn; qz /= qn;
        // rotation matrix columns scaled by the axis lengths -> M (row-major 3x3)
        var R = [1 - 2 * (qy * qy + qz * qz), 2 * (qx * qy - qw * qz), 2 * (qx * qz + qw * qy),
                 2 * (qx * qy + qw * qz), 1 - 2 * (qx * qx + qz * qz), 2 * (qy * qz - qw * qx),
                 2 * (qx * qz - qw * qy), 2 * (qy * qz + qw * qx), 1 - 2 * (qx * qx + qy * qy)];
        var M = [];
        for (var r3 = 0; r3 < 3; r3++) for (var c3 = 0; c3 < 3; c3++) M.push(R[r3 * 3 + c3] * sc[c3]);
        var gx0 = dv.getInt16(o3, true) / 10000, gy0 = dv.getInt16(o3 + 2, true) / 10000, gz0 = dv.getInt16(o3 + 4, true) / 10000;
        pts.push({
          kind: 2, g: gi, tx: gx0, ty: gy0, tz: gz0,
          sx0: (Math.random() - .5) * 2.4, sy0: Math.random() * 1.6 - .2, sz0: (Math.random() - .5) * 2.4,
          spr: gl ? null : gaussSprite(dv.getUint8(o3 + 6), dv.getUint8(o3 + 7), dv.getUint8(o3 + 8)),
          rgb: [dv.getUint8(o3 + 6) / 255, dv.getUint8(o3 + 7) / 255, dv.getUint8(o3 + 8) / 255],
          s: 1, delay: Math.random() * .6, op: dv.getUint8(o3 + 9) / 255, M: M, ax: null
        });
      }
      return m.n > 0;
    }
    var thin = 1, stride = m.stride || 9, AX = m.ax || 3000;
    for (var k = 0; k < m.n; k += thin) {
      var o = k * stride;
      var tx = dv.getInt16(o, true) / 10000, ty = dv.getInt16(o + 2, true) / 10000, tz = -dv.getInt16(o + 4, true) / 10000; // +z is away from the camera
      pts.push({
        kind: 2, g: gi, tx: tx, ty: ty, tz: tz,
        sx0: (Math.random() - .5) * 2.4, sy0: Math.random() * 1.6 - .2, sz0: (Math.random() - .5) * 2.4,
        spr: spriteFor(dv.getUint8(o + 6), dv.getUint8(o + 7), dv.getUint8(o + 8)),
        s: (thin > 1 ? 1.35 : 1) * (.95 + Math.random() * .1), delay: Math.random() * .6, op: 0.78 + Math.random() * 0.2,
        // ellipsoid axes (z flipped like the position); absent in old data = round splat
        ax: stride >= 15 ? [dv.getInt8(o + 9) / AX, dv.getInt8(o + 10) / AX, -dv.getInt8(o + 11) / AX,
                            dv.getInt8(o + 12) / AX, dv.getInt8(o + 13) / AX, -dv.getInt8(o + 14) / AX] : null
      });
    }
    return m.n > 0;
  };
  var startMascot = function () {
    mascotMode = true; assembleT = reduce ? 10 : 0; yaw = 0; pitch = 0.2;
    groups.forEach(function (G) { if (G) { G.at = assembleT; G.bt = -1; G.sc = false; } });
  };
  var setCount = function () { if (countEl) countEl.textContent = pts.length.toLocaleString("en-US"); };
  var useMascot = !!mascotSrc && addMascotFromData(window.CVSP_MASCOT, 0);
  // the friends only join when Sanjini stands above the photo carousel
  if (useMascot && canvas.parentNode.classList.contains("has-slides")) groups.forEach(function (G, gi) { if (gi) G.on = addMascotFromData(window[G.key], gi); });
  groups[0].on = useMascot;
  groups = groups.map(function (G) { return G.on ? G : null; });
  if (!useMascot) addTorus();
  setCount();

  var W = 0, H = 0, dpr = 1, cx = 0, cy = 0, scale = 1, burstR = 0.6, burstY = 0.5;
  var resize = function () {
    dpr = Math.min(window.devicePixelRatio || 1, 2);
    W = canvas.clientWidth; H = canvas.clientHeight;
    canvas.width = Math.round(W * dpr); canvas.height = Math.round(H * dpr);
    if (ctx) ctx.setTransform(dpr, 0, 0, dpr, 0, 0); else gl.viewport(0, 0, canvas.width, canvas.height);
    var wide = W > 900;
    if (canvas.hasAttribute("data-mascot") && canvas.parentNode.classList.contains("has-slides")) {
      // Sanjini stands centred just above the photo carousel, in the room left by --mascot-room
      var inner2 = canvas.parentNode.querySelector(".hero-inner");
      var room = parseFloat(getComputedStyle(canvas.parentNode).getPropertyValue("--mascot-room")) || 110;
      // the row of characters fills most of the band above the photos
      scale = (W < 760 ? Math.min(W * 0.3, 150) : Math.min(W * 0.3, 240)) / 2;
      cx = W * 0.5;
      // the burst is a round cloud that fills the empty band above the photos (photoTop = top edge of the photos)
      var photoTop = (inner2 ? inner2.offsetTop : 0) + room;
      cy = photoTop * 0.5 + scale * 0.5;
      burstR = Math.max(30, photoTop * 0.5 - 8) / scale; burstY = (cy - photoTop * 0.5) / scale;
      return;
    }
    if (canvas.hasAttribute("data-mascot")) {
      // centered stage at the top of the hero; the lab name sits below it
      var stage = parseFloat(getComputedStyle(canvas.parentNode).getPropertyValue("--stage")) || 400;
      cx = W * 0.5;
      scale = Math.min(W * 0.5, 343) / 3;
      var inner = canvas.parentNode.querySelector(".hero-inner");
      cy = (inner ? inner.offsetTop : 0) + stage * 0.5 + scale * 0.5 + 10;
      return;
    }
    cx = wide ? W * 0.70 : W * 0.5;
    cy = wide ? H * 0.50 : H * 0.86;
    scale = Math.min(wide ? W * 0.30 : W * 0.42, H * 0.62);
  };

  var yaw = 0.6, pitch = 0.42, drag = null, spin = 0.12;
  // click (or tap) on the mascot: the gaussians burst apart and fly back
  var scattered = false;   // true while any character is burst (kept for older code paths)
  // which character is under the pointer (index into groups) or -1
  var mascotAt = function (e) {
    if (!mascotMode) return -1;
    var r = canvas.getBoundingClientRect(), mx = e.clientX - r.left, my = e.clientY - r.top;
    for (var gi = 0; gi < groups.length; gi++) {
      var G = groups[gi]; if (!G) continue;
      var gx = cx + G.ox * scale, hw = scale * 0.45 * G.s, top = cy - scale * 1.0 * G.s;
      if (G.sc) { hw = burstR * scale; top = cy - (burstY + burstR) * scale; }
      if (Math.abs(mx - gx) < hw && my > top && my < cy + scale * 0.05) return gi;
    }
    return -1;
  };
  var onMascot = function (e) { return mascotAt(e) >= 0; };
  // click a character: its gaussians burst into a round cloud around it; click again and it gathers back
  var burst = function (gi) {
    var G = groups[gi]; if (!G) return;
    if (G.bt >= 0 && G.bt < 0.55) return;
    if (G.sc) {
      for (var k = 0; k < pts.length; k++) if (pts[k].kind === 2 && pts[k].g === gi) pts[k].delay = Math.random() * .25;
      G.sc = false; G.at = 0; G.bt = -1;
    } else {
      var R = burstR * (0.55 + 0.45 * G.s);
      for (var n = 0; n < pts.length; n++) {
        var p = pts[n];
        if (p.kind !== 2 || p.g !== gi) continue;
        if (overlay) {
          // round cloud: denser in the middle, thinning out toward the edge, never past the band above the photos
          var ang = Math.random() * Math.PI * 2, rr = R * Math.pow(Math.random(), 0.7);
          p.sx0 = G.ox + Math.cos(ang) * rr; p.sy0 = burstY + Math.sin(ang) * rr; p.sz0 = (Math.random() - .5) * 0.1;
        } else {
          // fly outward from the body center, with some randomness
          var dx = p.tx + (Math.random() - .5) * .3, dy = p.ty - 0.45 + (Math.random() - .5) * .3, dz = p.tz + (Math.random() - .5) * .3;
          var len = Math.sqrt(dx * dx + dy * dy + dz * dz) || 1, dist = 0.3 + Math.random() * 0.5;
          p.sx0 = p.tx + dx / len * dist; p.sy0 = p.ty + dy / len * dist; p.sz0 = p.tz + dz / len * dist;
        }
        p.delay = Math.random() * .35;
      }
      G.bt = 0; G.sc = true;
    }
    scattered = groups.some(function (H) { return H && H.sc; });
  };
  // with the photo carousel the canvas is drawn on top (so the burst is not hidden behind the photos)
  // and lets clicks through; the hero listens instead and only reacts on Sanjini or the empty background
  var overlay = canvas.parentNode.classList.contains("has-slides"), hit = overlay ? canvas.parentNode : canvas;
  var freeSpot = function (e) { return !overlay || onMascot(e) || !(e.target.closest && e.target.closest(".hero-slides, a, button, p, h1")); };
  hit.addEventListener("pointerdown", function (e) { if (!freeSpot(e)) return; drag = { x: e.clientX, y: e.clientY, yaw: yaw, pitch: pitch, moved: false }; canvas.classList.add("dragging"); });
  window.addEventListener("pointerup", function (e) {
    if (drag && !drag.moved) { var gi = mascotAt(e); if (gi >= 0) burst(gi); }
    drag = null; canvas.classList.remove("dragging");
  });
  hit.addEventListener("pointermove", function (e) { if (!drag) hit.style.cursor = onMascot(e) ? "pointer" : ""; });
  window.addEventListener("pointermove", function (e) {
    if (!drag) return;
    if (Math.abs(e.clientX - drag.x) + Math.abs(e.clientY - drag.y) > 6) drag.moved = true;
    yaw = drag.yaw + (e.clientX - drag.x) * 0.006;
    pitch = Math.max(0.1, Math.min(1.1, drag.pitch + (e.clientY - drag.y) * 0.004));
  });

  var buf = [];
  // ---- WebGL: every gaussian is an instanced quad; the shader draws exp(-r^2/2) out to 3 sigma, like the sprite
  var glProg = null, glBuf = null, glData = null, glLoc = null;
  var glInit = function () {
    var vs = "attribute vec2 q; attribute vec2 c; attribute vec3 l; attribute vec4 col; uniform vec2 vp; varying vec2 uv; varying vec4 vc;" +
      "void main(){ vec2 p = c + vec2(l.x*q.x, l.y*q.x + l.z*q.y); uv = q; vc = col;" +
      " gl_Position = vec4(p.x/vp.x*2.0-1.0, 1.0-p.y/vp.y*2.0, 0.0, 1.0); }";
    var fs = "precision mediump float; varying vec2 uv; varying vec4 vc;" +
      "void main(){ float r2 = dot(uv,uv); if (r2 > 1.0) discard; float a = vc.a * exp(-4.5*r2); gl_FragColor = vec4(vc.rgb*a, a); }";
    var mk = function (type, src) { var sh = gl.createShader(type); gl.shaderSource(sh, src); gl.compileShader(sh); return sh; };
    glProg = gl.createProgram();
    gl.attachShader(glProg, mk(gl.VERTEX_SHADER, vs)); gl.attachShader(glProg, mk(gl.FRAGMENT_SHADER, fs));
    gl.linkProgram(glProg);
    if (!gl.getProgramParameter(glProg, gl.LINK_STATUS)) return false;
    gl.useProgram(glProg);
    glLoc = { q: gl.getAttribLocation(glProg, "q"), c: gl.getAttribLocation(glProg, "c"), l: gl.getAttribLocation(glProg, "l"),
              col: gl.getAttribLocation(glProg, "col"), vp: gl.getUniformLocation(glProg, "vp") };
    var quad = gl.createBuffer(); gl.bindBuffer(gl.ARRAY_BUFFER, quad);
    gl.bufferData(gl.ARRAY_BUFFER, new Float32Array([-1, -1, 1, -1, -1, 1, 1, 1]), gl.STATIC_DRAW);
    gl.enableVertexAttribArray(glLoc.q); gl.vertexAttribPointer(glLoc.q, 2, gl.FLOAT, false, 0, 0);
    glBuf = gl.createBuffer(); gl.bindBuffer(gl.ARRAY_BUFFER, glBuf);
    var st = 9 * 4;
    [[glLoc.c, 2, 0], [glLoc.l, 3, 8], [glLoc.col, 4, 20]].forEach(function (a) {
      gl.enableVertexAttribArray(a[0]); gl.vertexAttribPointer(a[0], a[1], gl.FLOAT, false, st, a[2]); glx.vertexAttribDivisorANGLE(a[0], 1);
    });
    gl.enable(gl.BLEND); gl.blendFunc(gl.ONE, gl.ONE_MINUS_SRC_ALPHA);
    return true;
  };
  if (gl && !glInit()) {
    // WebGL refused the shaders: draw with the 2D canvas instead (needs a fresh canvas, a canvas keeps its first context)
    var c2 = canvas.cloneNode(false); canvas.parentNode.replaceChild(c2, canvas); canvas = c2;
    gl = null; ctx = canvas.getContext("2d");
    pts.forEach(function (p) { if (p.rgb && !p.spr) p.spr = gaussSprite(p.rgb[0] * 255, p.rgb[1] * 255, p.rgb[2] * 255); });
    resize();
  }
  var drawGL = function () {
    var n = 0;
    if (!glData || glData.length < buf.length * 9) glData = new Float32Array(buf.length * 9);
    for (var q = 0; q < buf.length; q++) {
      var b = buf[q];
      if (b.k !== 2 || !b.g || b.op < 0.02) continue;
      var o = n * 9;
      glData[o] = b.sx; glData[o + 1] = b.sy; glData[o + 2] = b.g[0]; glData[o + 3] = b.g[1]; glData[o + 4] = b.g[2];
      glData[o + 5] = b.rgb[0]; glData[o + 6] = b.rgb[1]; glData[o + 7] = b.rgb[2]; glData[o + 8] = b.op;
      n++;
    }
    gl.clearColor(0, 0, 0, 0); gl.clear(gl.COLOR_BUFFER_BIT);
    gl.uniform2f(glLoc.vp, W, H);
    gl.bindBuffer(gl.ARRAY_BUFFER, glBuf);
    gl.bufferData(gl.ARRAY_BUFFER, glData.subarray(0, n * 9), gl.DYNAMIC_DRAW);
    glx.drawArraysInstancedANGLE(gl.TRIANGLE_STRIP, 0, 4, n);
  };

  var draw = function (t) {
    if (ctx) { ctx.clearRect(0, 0, W, H); ctx.globalCompositeOperation = "lighter"; }
    var cyw = Math.cos(yaw), syw = Math.sin(yaw), cp = Math.cos(pitch), sp = Math.sin(pitch);
    // each character turns around its own centre (yaw + its phase); the row itself is not rotated
    for (var gq = 0; gq < groups.length; gq++) { var Gq = groups[gq]; if (Gq) { Gq.c = Math.cos(yaw + Gq.ph); Gq.sn = Math.sin(yaw + Gq.ph); } }
    buf.length = 0;
    for (var n = 0; n < pts.length; n++) {
      var p = pts[n], x, y, z, col;
      if (p.kind === 0) {
        x = p.x; z = p.z;
        if (mascotMode) { x *= 0.85; z *= 0.85; }
        y = Math.sin(x * 3.1 + t * 0.9) * Math.cos(z * 2.6 - t * 0.7) * 0.12 + Math.sin((x + z) * 5 + t * 1.6) * 0.025;
        col = y > 0.06 ? 1 : (y > -0.02 ? 2 : 0);
      } else if (p.kind === 2) {
        var e, G = groups[p.g];
        if (G.sc) {
          // burst phase: from the shape out to the scattered positions, then stay there
          var u2 = Math.min(1, G.bt / 0.55); e = 1 - (1 - Math.pow(1 - u2, 3));
        } else {
          e = Math.min(1, Math.max(0, (G.at - p.delay) / 1.8));
        }
        e = 1 - Math.pow(1 - e, 3);
        var wob = Math.sin(t * 1.4 + p.tx * 6) * 0.004;
        // assembled place: the character's own turn and size, then its spot in the row
        var lx = p.tx * G.s, lz = p.tz * G.s;
        var ax0 = G.ox + lx * G.c - lz * G.sn, az0 = lx * G.sn + lz * G.c;
        var ay0 = (p.ty + wob + Math.sin(t * 1.1 + G.ph) * 0.012) * G.s;
        x = p.sx0 + (ax0 - p.sx0) * e;
        y = p.sy0 + (ay0 - p.sy0) * e;
        z = p.sz0 + (az0 - p.sz0) * e;
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
      // rotate yaw (around y), then pitch (around x); characters are already turned (see above)
      var ry0 = p.kind === 2 ? 1 : cyw, rs0 = p.kind === 2 ? 0 : syw;
      var X = x * ry0 - z * rs0, Z = x * rs0 + z * ry0;
      var Y = y * cp - Z * sp, Z2 = y * sp + Z * cp;
      var persp = 2.6 / (2.6 + Z2);
      var it = { sx: cx + X * scale * persp, sy: cy - Y * scale * persp, d: Z2, r: p.s * persp, c: col, k: p.kind, spr: p.spr, a: null, op: p.op, rgb: p.rgb };
      if (p.M) {
        // full 3D gaussian: project the covariance with the perspective jacobian (as in 3DGS)
        var Mm = p.M, fz = scale * persp, dz = 2.6 + Z2, a2 = 0.3, b2 = 0, c2 = 0.3;
        var Gm = groups[p.g], gc = Gm.c * Gm.s, gs = Gm.sn * Gm.s, gsz = Gm.s;
        for (var ci = 0; ci < 3; ci++) {
          var vx = Mm[ci], vy = Mm[3 + ci] * gsz, vz = Mm[6 + ci];
          var rx = vx * gc - vz * gs, rzt = vx * gs + vz * gc;
          var ry = vy * cp - rzt * sp, rz = vy * sp + rzt * cp;
          var ux = fz * (rx - X * rz / dz), uy = -fz * (ry - Y * rz / dz);
          a2 += ux * ux; b2 += ux * uy; c2 += uy * uy;
        }
        var l11 = Math.sqrt(a2), l21 = b2 / l11, l22 = Math.sqrt(Math.max(c2 - l21 * l21, 1e-4));
        it.g = [3 * l11, 3 * l21, 3 * l22];
      } else if (p.ax) {
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
    if (gl) { drawGL(); return; }
    for (var q = 0; q < buf.length; q++) {
      var b = buf[q];
      if (b.k === 2) {
        ctx.globalCompositeOperation = "source-over";
        ctx.globalAlpha = b.op || 0.95;
        if (b.g) {
          if (b.op < 0.02) { ctx.globalCompositeOperation = "lighter"; continue; }
          ctx.setTransform(dpr * b.g[0], dpr * b.g[1], 0, dpr * b.g[2], dpr * b.sx, dpr * b.sy);
          ctx.drawImage(b.spr, -1, -1, 2, 2);
          ctx.setTransform(dpr, 0, 0, dpr, 0, 0);
        } else if (b.a) {
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
      if (mascotMode) {
        assembleT += dt;
        groups.forEach(function (G) { if (!G) return; G.at += dt; if (G.bt >= 0) G.bt = Math.min(0.55, G.bt + dt); });
        // the characters keep turning all the way round (360°)
        if (!drag) yaw += 0.6 * dt;
      }
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

/* Demos: 화면에 보일 때만 자동 재생(소리 없음), 벗어나면 멈춤 → 처음 로딩이 가볍습니다. */
(function () {
  var vids = document.querySelectorAll(".demo-video");
  if (!vids.length) return;
  var reduce = window.matchMedia && window.matchMedia("(prefers-reduced-motion: reduce)").matches;
  if (reduce || !("IntersectionObserver" in window)) return;
  var io = new IntersectionObserver(function (es) {
    es.forEach(function (e) {
      var v = e.target;
      if (e.isIntersecting) { if (v.preload === "none") v.preload = "auto"; var p = v.play(); if (p && p.catch) p.catch(function () {}); }
      else if (!v.paused) v.pause();
    });
  }, { threshold: 0.35 });
  vids.forEach(function (v) { io.observe(v); });
})();

/* 홈 News / Gallery / LAB Life: 아래 "Load more" 하나를 누르면 각 섹션에 카드가 2줄씩 더 나옵니다. */
(function () {
  var btn = document.querySelector("[data-feed-more-all]");
  if (!btn) return;
  var boxes = document.querySelectorAll("[data-feed]");
  var left = function () { return document.querySelectorAll("[data-feed] .bcard.is-more[hidden]").length; };
  if (!left()) { btn.hidden = true; return; }
  btn.addEventListener("click", function () {
    boxes.forEach(function (box) {
      var step = parseInt(box.getAttribute("data-step"), 10) || 4;
      var rest = box.querySelectorAll(".bcard.is-more[hidden]");
      for (var i = 0; i < rest.length && i < step; i++) rest[i].hidden = false;
    });
    if (!left()) btn.hidden = true;
  });
})();

/* home hero photo carousel (Notion main page "oopy:slide"): the current photo in the middle,
   neighbours peeking in at the sides; slides sideways every 4.5 s, endless loop; arrows, dots, swipe */
(function () {
  var box = document.querySelector("[data-hero-slides]");
  if (!box) return;
  var orig = Array.prototype.slice.call(box.querySelectorAll("img")), n = orig.length;
  if (!n) return;
  var K = Math.min(2, n), track = document.createElement("div"); track.className = "hero-slides-track";
  orig.forEach(function (im) { im.classList.remove("is-on"); im.loading = "eager"; });
  var head = orig.slice(-K).map(function (im) { var c = im.cloneNode(); c.setAttribute("aria-hidden", "true"); return c; });
  var tail = orig.slice(0, K).map(function (im) { var c = im.cloneNode(); c.setAttribute("aria-hidden", "true"); return c; });
  head.concat(orig, tail).forEach(function (im) { track.appendChild(im); });
  box.appendChild(track);
  var all = track.children, pos = K, timer = null, busy = false;
  var place = function (anim) {
    var sw = all[0].getBoundingClientRect().width, gap = parseFloat(getComputedStyle(track).columnGap) || 0;
    track.classList.toggle("is-moving", !!anim);
    track.style.transform = "translateX(" + (box.clientWidth / 2 - sw / 2 - pos * (sw + gap)) + "px)";
    for (var i = 0; i < all.length; i++) all[i].classList.toggle("is-on", i === pos);
    var cur = ((pos - K) % n + n) % n;
    for (var j = 0; j < dots.children.length; j++) dots.children[j].classList.toggle("is-on", j === cur);
  };
  var dots = document.createElement("div"); dots.className = "hero-slides-dots";
  var go = function (to) {
    if (busy || n < 2) return;
    busy = true; pos = to; place(true);
    setTimeout(function () {
      // stepped onto a copy at either end: jump to the real photo without animation
      if (pos >= K + n) { pos -= n; place(false); }
      else if (pos < K) { pos += n; place(false); }
      busy = false;
    }, 820);
  };
  var reduce = window.matchMedia("(prefers-reduced-motion: reduce)").matches;
  var restart = function () { clearInterval(timer); if (!reduce && n > 1) timer = setInterval(function () { go(pos + 1); }, 4500); };
  if (n > 1) {
    for (var i = 0; i < n; i++) (function (i) {
      var d = document.createElement("button"); d.type = "button"; d.setAttribute("aria-label", "Photo " + (i + 1));
      d.addEventListener("click", function () { go(K + i); restart(); }); dots.appendChild(d);
    })(i);
    box.appendChild(dots);
    [["prev", -1, "Previous photo", "\u2039"], ["next", 1, "Next photo", "\u203A"]].forEach(function (x) {
      var btn = document.createElement("button"); btn.type = "button"; btn.className = "hero-slides-arrow is-" + x[0];
      btn.setAttribute("aria-label", x[2]); btn.textContent = x[3];
      btn.addEventListener("click", function () { go(pos + x[1]); restart(); }); box.appendChild(btn);
    });
    var sx = null;
    box.addEventListener("touchstart", function (e) { sx = e.touches[0].clientX; }, { passive: true });
    box.addEventListener("touchend", function (e) {
      if (sx === null) return; var dx = e.changedTouches[0].clientX - sx; sx = null;
      if (Math.abs(dx) > 40) { go(pos + (dx < 0 ? 1 : -1)); restart(); }
    });
    // click a peeking neighbour to bring it to the middle
    for (var k = 0; k < all.length; k++) (function (k) {
      all[k].addEventListener("click", function () { if (k !== pos) { go(k); restart(); } });
    })(k);
  }
  place(false);
  window.addEventListener("resize", function () { place(false); });
  restart();
})();

/* Notion "oopy:slide" photo slides on board pages */
(function () {
  document.querySelectorAll("[data-slide]").forEach(function (box) {
    var track = box.querySelector(".board-slide-track");
    var n = track.children.length; if (n < 2) return;
    var dots = document.createElement("div"); dots.className = "board-slide-dots";
    for (var i = 0; i < n; i++) (function (i) {
      var b = document.createElement("button"); b.type = "button"; b.setAttribute("aria-label", "Slide " + (i + 1));
      b.addEventListener("click", function () { go(i); restart(); }); dots.appendChild(b);
    })(i);
    box.appendChild(dots);
    function cur() { return Math.round(track.scrollLeft / track.clientWidth); }
    function go(i) { track.scrollTo({ left: i * track.clientWidth, behavior: "smooth" }); }
    function mark() { var c = cur(); [].forEach.call(dots.children, function (d, i) { d.setAttribute("aria-current", i === c ? "true" : "false"); }); }
    track.addEventListener("scroll", function () { window.requestAnimationFrame(mark); }); mark();
    var t; function restart() { clearInterval(t); t = setInterval(function () { go((cur() + 1) % n); }, 6000); }
    restart();
  });
})();


// keep the publications year anchors clear of the sticky filter bar
(function () {
  var bar = document.querySelector(".pub-controls");
  if (!bar) return;
  var set = function () { document.documentElement.style.setProperty("--pubbar", bar.offsetHeight + "px"); };
  set(); window.addEventListener("resize", set);
  // year buttons: put the year label right under the sticky filter bar
  var go = function (id, smooth) {
    var sec = document.getElementById(id);
    if (!sec || sec.hidden) return false;
    var label = sec.querySelector(".year-label") || sec;
    var top = label.getBoundingClientRect().top + window.scrollY - (parseFloat(getComputedStyle(bar).top) || 0) - bar.offsetHeight - 16;
    window.scrollTo({ top: top, behavior: smooth ? "smooth" : "auto" });
    return true;
  };
  document.querySelectorAll(".year-jump a[href^='#']").forEach(function (a) {
    a.addEventListener("click", function (e) {
      var id = a.getAttribute("href").slice(1);
      if (go(id, false)) {
        e.preventDefault(); history.replaceState(null, "", "#" + id);
        // images above may finish loading and push the year down: correct once more
        setTimeout(function () { go(id, false); }, 250);
        setTimeout(function () { go(id, false); }, 800);
      }
    });
  });
  if (location.hash) window.addEventListener("load", function () { go(location.hash.slice(1), false); });
})();
