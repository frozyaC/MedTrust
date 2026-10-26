import React from 'react';
import ReactDOM from 'react-dom/client';
import App from './App';
import { KnowledgeGapsPage } from './pages/KnowledgeGapsPage';
import './index.css';

const currentPath = window.location.pathname.replace(/\/+$/, '');
const isKnowledgeGapsPage = currentPath === '/admin/knowledge-gaps';
const isAuthenticated = window.localStorage.getItem('medtrust.auth') === 'true';

// Защита админки: если не вошёл — редирект на главную
if (isKnowledgeGapsPage && !isAuthenticated) {
  window.location.assign('/');
}

ReactDOM.createRoot(document.getElementById('root')!).render(
  <React.StrictMode>
    {isKnowledgeGapsPage ? <KnowledgeGapsPage /> : <App />}
  </React.StrictMode>,
);