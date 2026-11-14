import { StrictMode } from 'react';
import { createRoot } from 'react-dom/client';
import App from './App';
import ProjectApp from './ProjectApp';
import { I18nProvider } from './i18n';
import './styles.css';
import './glass.css';

const legacy = new URLSearchParams(window.location.search).get('legacy') === '1' || import.meta.env.VITE_LEGACY_WORKSPACE === '1';
document.documentElement.classList.toggle('va-project-mode', !legacy);
createRoot(document.getElementById('root')!).render(<StrictMode><I18nProvider>{legacy ? <App /> : <ProjectApp />}</I18nProvider></StrictMode>);
