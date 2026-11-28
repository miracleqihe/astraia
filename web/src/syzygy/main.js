import '../fonts';
import '../styles.css';
import './utilities.css';
import './overrides.css';
import '../engraving.css';
import { initViewRouter } from '../viewRouter';
import { mountEngravingCorners } from '../engraving';
import { initSyzygyShell } from './shell';

initViewRouter();
initSyzygyShell();
document.querySelectorAll('#left-drawer, #right-drawer').forEach(mountEngravingCorners);
import('./scene-reference.js').catch((error) => {
  console.error('Syzygy initialization failed', error);
  const status = document.getElementById('syzygy-loading');
  if (status) {
    status.setAttribute('role', 'alert');
    status.textContent = `朔望叠影暂时无法载入：${error instanceof Error ? error.message : '请刷新重试。'}`;
    const retry = document.createElement('button');
    retry.type = 'button';
    retry.textContent = '重新载入';
    retry.className = 'syzygy-loading-retry';
    retry.addEventListener('click', () => window.location.reload());
    status.append(' ', retry);
  }
});
