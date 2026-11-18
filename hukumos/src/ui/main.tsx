import { StrictMode } from 'react';
import { createRoot } from 'react-dom/client';
import { LabApp } from './lab/LabApp';
import './styles.css';
import './lab/lab.css';

createRoot(document.getElementById('root')!).render(
  <StrictMode>
    <LabApp />
  </StrictMode>,
);
