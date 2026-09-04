import { dirname, resolve } from 'node:path';
import { fileURLToPath } from 'node:url';
export const directory = dirname(fileURLToPath(import.meta.url));
export const root = resolve(directory, '../../..');
export const modules = ['ui-studio', 'audio-studio', 'vfx-shader'];
export const python = process.env.LAB_PYTHON ?? resolve(directory, '.venv/bin/python');
export const env = { ...process.env, PYTHONDONTWRITEBYTECODE: '1',
  PYTHONPATH: modules.map(id => resolve(root, 'modules', id, 'backend/src')).join(':') };
