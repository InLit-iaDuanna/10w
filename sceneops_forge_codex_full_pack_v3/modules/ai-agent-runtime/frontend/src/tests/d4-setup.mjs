import { register } from 'node:module';
import { JSDOM } from 'jsdom';
register('./d4-loader.mjs', import.meta.url);
const dom = new JSDOM('<!doctype html><html><body></body></html>', {url:'http://localhost/'});
for (const name of ['window','document','localStorage','Event','HTMLElement']) Object.defineProperty(globalThis,name,{value:dom.window[name],configurable:true});
Object.defineProperty(globalThis,'navigator',{value:dom.window.navigator,configurable:true});
