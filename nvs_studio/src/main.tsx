import { StrictMode } from 'react';
import { createRoot } from 'react-dom/client';
import './index.css';
import App from './App';
import { useStudio } from './store';
import { useKaraoke } from './karaokeStore';
// Móc kiểm thử tự động: chỉ bật khi mở với ?e2e
if (new URLSearchParams(location.search).has('e2e')) Object.assign(window, { __nvs: { studio: useStudio, karaoke: useKaraoke } });
createRoot(document.getElementById('root')!).render(<StrictMode><App /></StrictMode>);
