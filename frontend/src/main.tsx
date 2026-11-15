import { StrictMode } from 'react'
import { createRoot } from 'react-dom/client'
import '@fontsource-variable/source-sans-3/wght.css'
import './index.css'
import 'katex/dist/katex.min.css'
import App from './App.tsx'

const rootElement = document.getElementById('root');

if (!rootElement) {
  throw new Error('Root element not found');
}

const root = createRoot(rootElement);

// A tab can outlive a deployment and keep requesting chunks from the previous
// build. Vite emits this event when a dynamic import cannot be loaded. Reload
// once so the browser picks up the current index.html and its chunk names.
const chunkReloadKey = 'bonds-screener:chunk-reload';
try {
  if (sessionStorage.getItem(chunkReloadKey) === '1') {
    window.setTimeout(() => sessionStorage.removeItem(chunkReloadKey), 60_000);
  }
} catch {
  // Storage can be disabled by browser privacy settings.
}
window.addEventListener('vite:preloadError', (event) => {
  try {
    if (sessionStorage.getItem(chunkReloadKey) === '1') return;
    event.preventDefault();
    sessionStorage.setItem(chunkReloadKey, '1');
    window.location.reload();
  } catch {
    // Do not reload repeatedly if browser storage is unavailable.
  }
});

root.render(
  <StrictMode>
    <App />
  </StrictMode>
);

// Log errors that occur during rendering
if (import.meta.env.DEV) {
  window.addEventListener('error', (event) => {
    console.error('Global error:', event.error);
  });
  
  window.addEventListener('unhandledrejection', (event) => {
    console.error('Unhandled promise rejection:', event.reason);
  });
}



