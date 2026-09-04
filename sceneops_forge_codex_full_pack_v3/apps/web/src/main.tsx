import React from 'react';
import { createRoot } from 'react-dom/client';
import { ShellWorkbench } from './app/ShellWorkbench';
createRoot(document.getElementById('root')!).render(<ShellWorkbench unified />);
