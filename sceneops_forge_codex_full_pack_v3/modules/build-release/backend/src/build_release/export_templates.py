"""Owned packaging recipes; project scripts/configuration are never executed."""
import json

VITE_VERSION = '8.2.2'
ELECTRON_VERSION = '44.2.0'
BUILDER_VERSION = '26.15.3'
CAPACITOR_VERSION = '8.5.1'
VITE_CONFIG = "export default {base:'/',envDir:false,css:{postcss:{plugins:[]}},build:{outDir:'dist',emptyOutDir:true}};\n"

ELECTRON_MAIN = r'''const {app, BrowserWindow, protocol, net, session} = require('electron');
const path = require('node:path');
const fs = require('node:fs/promises');
const {pathToFileURL} = require('node:url');
protocol.registerSchemesAsPrivileged([{scheme:'game',privileges:{standard:true,secure:true,supportFetchAPI:true,stream:true}}]);
app.enableSandbox();
function createWindow() {
  const win = new BrowserWindow({width:1280,height:800,resizable:true,webPreferences:{sandbox:true,contextIsolation:true,nodeIntegration:false,webSecurity:true}});
  win.webContents.setWindowOpenHandler(() => ({action:'deny'}));
  win.webContents.on('will-navigate', (event,url) => {const parsed = new URL(url); if(parsed.protocol !== 'game:' || parsed.host !== 'local') event.preventDefault();});
  win.loadURL('game://local/index.html');
}
app.whenReady().then(() => {
  const root = path.join(app.getAppPath(),'dist');
  protocol.handle('game', async request => {
    const url = new URL(request.url);
    if(url.host !== 'local' || request.method !== 'GET') return new Response('',{status:403});
    let relative;
    try {relative = decodeURIComponent(url.pathname);} catch {return new Response('',{status:400});}
    const target = path.resolve(root, '.' + relative);
    if(target !== root && !target.startsWith(root + path.sep)) return new Response('',{status:403});
    try {
      const real = await fs.realpath(target === root ? path.join(root,'index.html') : target);
      if(!real.startsWith(root + path.sep)) return new Response('',{status:403});
      const response = await net.fetch(pathToFileURL(real).href);
      response.headers.set('Content-Security-Policy', "default-src 'self'; script-src 'self'; style-src 'self' 'unsafe-inline'; img-src 'self' data: blob: https:; media-src 'self' blob: https:; connect-src 'self' https: wss:; worker-src 'self' blob:");
      return response;
    } catch {return new Response('',{status:404});}
  });
  session.defaultSession.setPermissionRequestHandler((_contents,_permission,callback) => callback(false));
  session.defaultSession.setPermissionCheckHandler(() => false);
  createWindow();
  app.on('activate',() => {if(BrowserWindow.getAllWindows().length === 0) createWindow();});
});
app.on('window-all-closed',() => {if(process.platform !== 'darwin') app.quit();});
'''


def desktop_package(name: str, app_id: str) -> dict:
    return {'name': 'sceneops-export', 'version': '1.0.0', 'private': True,
            'description': name, 'author': 'SceneOps user', 'main': 'main.cjs',
            'devDependencies': {'electron': ELECTRON_VERSION, 'electron-builder': BUILDER_VERSION},
            'build': {'appId': app_id, 'productName': name, 'asar': True,
                      'npmRebuild': False, 'files': ['dist/**/*', 'main.cjs', 'package.json'],
                      'directories': {'output': 'artifacts'},
                      'artifactName': '${productName}-${os}-${arch}.${ext}',
                      'mac': {'target': ['zip'], 'identity': None},
                      'win': {'target': ['zip'], 'signAndEditExecutable': False}}}


def capacitor_config(name: str, app_id: str) -> str:
    return json.dumps({'appId': app_id, 'appName': name, 'webDir': 'dist'}, ensure_ascii=False)
