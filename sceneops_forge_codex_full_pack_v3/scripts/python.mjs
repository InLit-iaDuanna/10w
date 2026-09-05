import { spawn } from 'node:child_process';
import path from 'node:path';
import { applicationRoot, pythonEnvironment } from './python-workspace.mjs';

const python = process.env.SCENEOPS_PYTHON ?? path.join(applicationRoot, '.venv/bin/python');
const child = spawn(python, process.argv.slice(2), {cwd:applicationRoot, env:pythonEnvironment(), stdio:'inherit'});
child.on('error', error => {console.error(error.message);process.exitCode=1;});
child.on('exit', (code, signal) => {process.exitCode=code??(signal?1:0);});
for (const signal of ['SIGINT','SIGTERM']) process.on(signal,()=>child.kill(signal));
