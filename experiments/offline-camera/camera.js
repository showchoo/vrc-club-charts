/* A synthetic-camera recorder for an owned, offline demo scene.
 * No VRChat integration. No getUserMedia(), OSC, fetch() or remote uploads.
 */
(() => {
  'use strict';
  const nav = window.VCCOfflineNavigator;
  const canvas = document.getElementById('scene');
  const ctx = canvas.getContext('2d');
  const startButton = document.getElementById('start');
  const previewButton = document.getElementById('preview');
  const stopButton = document.getElementById('stop');
  const status = document.getElementById('status');
  const controls = document.querySelector('.controls');
  const FPS = 12;
  const MAX_FRAMES = 420;
  const colors = {floor: '#172137', wall: '#34526a'};

  if (!nav || !ctx) {
    status.textContent = '描画・経路探索モジュールを初期化できません。';
    startButton.disabled = true;
    previewButton.disabled = true;
    return;
  }

  let session = null;
  const plan = nav.planInspection();
  const timeline = nav.makeTimeline(plan, 2, 9);
  if (!timeline.length || timeline.length > MAX_FRAMES) {
    status.textContent = '安全上限を超える巡回計画です。';
    startButton.disabled = true;
    previewButton.disabled = true;
    return;
  }

  function label(text, x, y, color = '#e4edfc', size = 16, align = 'left') {
    ctx.font = '600 ' + size + 'px system-ui, sans-serif';
    ctx.textAlign = align;
    ctx.fillStyle = color;
    ctx.fillText(text, x, y);
    ctx.textAlign = 'left';
  }

  function drawScene(frame, index, count) {
    const w = 672, h = canvas.height;
    ctx.fillStyle = '#091424';
    ctx.fillRect(0, 0, canvas.width, h);

    const roof = ctx.createLinearGradient(0, 0, 0, 280);
    roof.addColorStop(0, '#10182d');
    roof.addColorStop(1, '#243451');
    ctx.fillStyle = roof;
    ctx.fillRect(0, 0, w, 280);

    const floor = ctx.createLinearGradient(0, 280, 0, h);
    floor.addColorStop(0, '#222b4b');
    floor.addColorStop(1, '#080e1a');
    ctx.fillStyle = floor;
    ctx.fillRect(0, 280, w, h);

    const vanishingX = 335;
    ctx.strokeStyle = 'rgba(128,169,221,.23)';
    ctx.lineWidth = 1;
    for (let i = -9; i <= 9; i += 1) {
      ctx.beginPath();
      ctx.moveTo(vanishingX, 277);
      ctx.lineTo(vanishingX + i * 110, h);
      ctx.stroke();
    }
    for (const band of [294, 314, 341, 375, 422, 482]) {
      ctx.beginPath();
      ctx.moveTo(0, band);
      ctx.lineTo(w, band);
      ctx.stroke();
    }

    // Distance-sorted scene anchors mimic a first-person camera moving
    // around a privately owned synthetic level. No real VRChat footage.
    const objects = [];
    for (const [x, y] of nav.WALLS) {
      objects.push({x, y, id: 'wall', label: '', color: colors.wall});
    }
    for (const f of nav.FEATURES) {
      objects.push({x: f.x, y: f.y, id: f.id, label: f.label, color: f.tint});
    }
    for (const o of objects) {
      const dx = o.x - frame.x, dy = o.y - frame.y;
      const forward = dx * Math.cos(frame.yaw) + dy * Math.sin(frame.yaw);
      const lateral = -dx * Math.sin(frame.yaw) + dy * Math.cos(frame.yaw);
      if (forward <= -.7 || forward > 16 || Math.abs(lateral) > forward * 1.9 + 3) continue;
      objects[objects.indexOf(o)].depth = forward;
      objects[objects.indexOf(o)].side = lateral;
    }
    const visible = objects.filter(o => o.depth !== undefined)
      .sort((a, b) => b.depth - a.depth);
    for (const o of visible) {
      const depth = Math.max(.5, o.depth + 2);
      const scale = 230 / depth;
      const sx = vanishingX + o.side * scale;
      if (sx < -160 || sx > w + 160) continue;
      const pillarW = Math.max(8, scale * (o.id === 'wall' ? 1.05 : .65));
      const pillarH = Math.max(18, scale * (o.id === 'wall' ? 2.5 : 1.8));
      const sy = 282 - pillarH / 2 + scale * .1;
      ctx.globalAlpha = Math.min(.98, .36 + 5 / (depth + 6));
      ctx.fillStyle = o.color;
      ctx.fillRect(sx - pillarW / 2, sy, pillarW, pillarH);
      ctx.globalAlpha = 1;
      if (o.id !== 'wall') {
        ctx.shadowColor = o.color;
        ctx.shadowBlur = 20;
        ctx.strokeStyle = o.color;
        ctx.lineWidth = 2;
        ctx.strokeRect(sx - pillarW / 2, sy, pillarW, pillarH);
        ctx.shadowBlur = 0;
        if (o.depth < 10) label(o.label, sx, Math.max(42, sy - 10), '#ffffff', 12, 'center');
      }
    }
    ctx.fillStyle = 'rgba(1,6,15,.74)';
    ctx.fillRect(15, 16, 640, 78);
    label('OFFLINE SYNTHETIC WORLD  /  CAMERA LAB', 28, 43, '#9bf3ed', 17);
    label('DEMO ONLY — NO VRCHAT CLIENT / NO LIVE EQUIPMENT TEST', 28, 73, '#b4c5dc', 12);
    label('TARGET  ' + frame.currentTarget.toUpperCase(), 27, 480, '#ffffff', 17);
    label((frame.state === 'observation' ? 'OBSERVING' : 'NAVIGATING') +
      '    ' + (index + 1) + ' / ' + count, 27, 510, '#b4c5dc', 14);

    // HUD mini-map for reproducible movement and obstacle inspection.
    const left = 687, top = 18, cell = 12;
    ctx.fillStyle = '#111d30';
    ctx.fillRect(677, 0, 283, 540);
    label('AUTONOMOUS ROUTE', left, 46, '#e5ebf8', 16);
    label('Local grid planner (not vision AI)', left, 71, '#95b2ca', 11);
    for (let y = 0; y < nav.HEIGHT; y += 1) {
      for (let x = 0; x < nav.WIDTH; x += 1) {
        const blocked = !nav.isWalkable({x, y});
        ctx.fillStyle = blocked ? '#31455c' : '#17283d';
        ctx.fillRect(left + x * cell, top + 80 + y * cell, cell - 1, cell - 1);
      }
    }
    for (const f of nav.FEATURES) {
      ctx.fillStyle = f.tint;
      ctx.fillRect(left + f.x * cell + 2, top + 80 + f.y * cell + 2, cell - 5, cell - 5);
    }
    ctx.fillStyle = '#fcfcfc';
    ctx.beginPath();
    ctx.arc(left + (frame.x + .5) * cell, top + 80 + (frame.y + .5) * cell, 4.5, 0, Math.PI * 2);
    ctx.fill();

    label('INSPECTION TARGETS', left, 284, '#d4e3f5', 13);
    nav.FEATURES.forEach((f, i) => {
      const seen = frame.visited.includes(f.id);
      label((seen ? '✓ ' : '· ') + f.label, left + 7, 313 + i * 27,
        seen ? '#91e9c2' : '#9eacc3', 13);
    });
    label('Synthetic footage only.', left, 456, '#a2b3cc', 12);
    label('No real DJ or gimmick proof.', left, 479, '#a2b3cc', 12);
    const progress = Math.max(0, Math.min(1, (index + 1) / count));
    ctx.fillStyle = '#31455c';
    ctx.fillRect(left, 507, 252, 9);
    ctx.fillStyle = '#67cce9';
    ctx.fillRect(left, 507, 252 * progress, 9);
  }

  function setBusy(busy) {
    startButton.disabled = busy;
    previewButton.disabled = busy;
    stopButton.disabled = !busy;
  }

  function addDownload(blob, name, text) {
    const url = URL.createObjectURL(blob);
    const link = document.createElement('a');
    link.href = url;
    link.download = name;
    link.textContent = text;
    link.style.color = '#80daed';
    link.style.padding = '10px';
    controls.appendChild(link);
    // Do not revoke until next page load, so the user can retry downloads.
    return link;
  }

  async function sha256(blob) {
    if (!window.crypto || !window.crypto.subtle) return null;
    const bytes = await blob.arrayBuffer();
    const result = await window.crypto.subtle.digest('SHA-256', bytes);
    return Array.from(new Uint8Array(result),
      x => x.toString(16).padStart(2, '0')).join('');
  }

  function finish(reason = 'completed') {
    if (!session || session.finishing) return;
    session.finishing = true;
    window.clearInterval(session.interval);
    session.reason = reason;
    setBusy(false);
    if (session.recorder && session.recorder.state !== 'inactive') {
      session.recorder.stop();
    } else if (!session.recorder) {
      status.textContent = 'プレビュー終了（録画なし）';
      session = null;
    }
  }

  function begin(record) {
    if (session) return;
    if (record && (!canvas.captureStream || !window.MediaRecorder)) {
      status.textContent = 'このブラウザはCanvasのWebM録画に対応していません。Chrome/Edgeで開いてください。';
      return;
    }

    const now = new Date();
    const stamp = now.toISOString().replace(/[:.]/g, '-');
    let recorder = null, stream = null, chunks = [];
    if (record) {
      try {
        const mime = ['video/webm;codecs=vp9', 'video/webm;codecs=vp8', 'video/webm']
          .find(t => MediaRecorder.isTypeSupported(t));
        if (!mime) throw new Error('WebM encoding unsupported');
        stream = canvas.captureStream(FPS);
        recorder = new MediaRecorder(stream, {mimeType: mime});
      } catch (e) {
        if (stream) stream.getTracks().forEach(t => t.stop());
        status.textContent = '録画の初期化に失敗: ' + e.message;
        return;
      }
    }

    session = {recorder, stream, chunks, interval: null, reason: 'completed',
      startedAt: now.toISOString(), framesCaptured: 0, finishing: false, stamp};
    setBusy(true);
    if (recorder) {
      const current = session;
      recorder.addEventListener('dataavailable', e => {
        if (e.data.size > 0) current.chunks.push(e.data);
      });
      recorder.addEventListener('error', e => {
        status.textContent = '録画エラー。保存できた部分のみ取り出します。';
        if (session === current) finish('recording_error');
      });
      recorder.addEventListener('stop', async () => {
        if (current.stream) current.stream.getTracks().forEach(t => t.stop());
        const video = new Blob(current.chunks, {type: recorder.mimeType || 'video/webm'});
        const report = {
          schemaVersion: 1, mode: 'offline-synthetic-only', actualVRChatVisit: false,
          inspectionMethod: 'deterministic-grid-planner', date: current.startedAt,
          stopReason: current.reason, frameRateTarget: FPS,
          framesRendered: current.framesCaptured,
          ...nav.summarize(plan, FPS, current.framesCaptured),
          capturedVideoBytes: video.size,
          capturedVideoSha256: video.size ? await sha256(video) : null,
          evidenceStatus: 'not_real_world_evidence',
        };
        if (video.size) {
          const videoLink = addDownload(video, 'vcc-offline-demo-' + stamp + '.webm',
            '録画した動画を保存');
          // Browser download may require a click; leave the persistent link.
          videoLink.click();
          const audit = new Blob([JSON.stringify(report, null, 2)], {type: 'application/json'});
          addDownload(audit, 'vcc-offline-demo-' + stamp + '.json', '録画ログ（JSON）を保存');
          status.textContent = '録画終了。動画の保存を開始しました。JSONログも保存できます。';
        } else {
          status.textContent = '録画データが生成されませんでした。';
        }
        if (session === current) session = null;
      });
      recorder.start(1000);
    }

    let index = 0;
    const current = session;
    status.textContent = record ? '架空ワールドを自動探索・録画しています…' : '巡回プレビュー中…';
    drawScene(timeline[0], 0, timeline.length);
    current.interval = window.setInterval(() => {
      if (session !== current || current.finishing) return;
      if (index >= timeline.length || index >= MAX_FRAMES) {
        finish('completed');
        return;
      }
      drawScene(timeline[index], index, timeline.length);
      current.framesCaptured = index + 1;
      index += 1;
    }, 1000 / FPS);
  }

  startButton.addEventListener('click', () => begin(true));
  previewButton.addEventListener('click', () => begin(false));
  stopButton.addEventListener('click', () => finish('manual_stop'));
  window.addEventListener('keydown', e => {
    if (e.key === 'Escape') finish('emergency_stop');
  });
  window.addEventListener('pagehide', () => {
    if (session) finish('page_hidden');
  });

  // Initial image is visibly synthetic: it cannot be mistaken for a World visit.
  drawScene({...nav.START, yaw: 0, visited: [],
    currentTarget: plan[0].targetId, state: 'preview'}, 0, timeline.length);
})();
