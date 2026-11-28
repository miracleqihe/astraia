import { createRoot } from 'react-dom/client';
import './fonts';
import { App } from './App';
import { initViewRouter } from './viewRouter';
import './styles.css';
import './review-refinement.css';
import './engraving.css';
import './responsive.css';

initViewRouter();
createRoot(document.getElementById('root')!).render(<App />);
