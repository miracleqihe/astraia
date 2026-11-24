import '@fontsource/cormorant-garamond/latin-600.css';
import '@fontsource/jetbrains-mono/latin-400.css';
import '@fontsource/noto-serif-sc/400.css';
import '@fontsource/noto-serif-sc/600.css';
import '../styles.css';
import './utilities.css';
import './overrides.css';
import '../engraving.css';
import { initViewRouter } from '../viewRouter';
import { mountEngravingCorners } from '../engraving';

initViewRouter();
document.querySelectorAll('#left-drawer, #right-drawer').forEach(mountEngravingCorners);
import('./scene-reference.js').catch((error) => {
  console.error('Syzygy initialization failed', error);
  const status = document.getElementById('syzygy-loading');
  if (status) {
    status.setAttribute('role', 'alert');
    status.textContent = `朔望叠影暂时无法载入：${error instanceof Error ? error.message : '请刷新重试。'}`;
  }
});
