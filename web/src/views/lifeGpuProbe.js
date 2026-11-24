// Probe in a worker: creating a software WebGL context can otherwise block
// the UI thread for seconds before the Canvas 2D fallback is displayed.
self.onmessage = () => {
  let result = 'unknown';
  try {
    const canvas = new OffscreenCanvas(1, 1);
    const attributes = { antialias: true, alpha: true, failIfMajorPerformanceCaveat: true };
    let gl = canvas.getContext('webgl2', attributes);
    const guarded = !!gl;
    // An unguarded retry is safe here because it cannot block the UI thread.
    if (!gl) gl = canvas.getContext('webgl2', { ...attributes, failIfMajorPerformanceCaveat: false });
    if (gl) {
      const debug = gl.getExtension('WEBGL_debug_renderer_info');
      const name = debug ? String(gl.getParameter(debug.UNMASKED_RENDERER_WEBGL)) : '';
      if (/swiftshader|llvmpipe|software|warp/i.test(name)) result = 'software';
      else if (guarded) result = 'webgl';
      gl.getExtension('WEBGL_lose_context')?.loseContext();
    }
  } catch { /* The main thread can still attempt WebGL when probing is unavailable. */ }
  self.postMessage(result);
};
