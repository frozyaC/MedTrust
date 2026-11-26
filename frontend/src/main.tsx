import React from 'react';
import ReactDOM from 'react-dom/client';
import { AuthProvider } from './auth/AuthContext';
import { AuthenticatedApp } from './auth/AuthenticatedApp';
import './index.css';

ReactDOM.createRoot(document.getElementById('root')!).render(
  <React.StrictMode>
    <AuthProvider><AuthenticatedApp /></AuthProvider>
  </React.StrictMode>,
);
