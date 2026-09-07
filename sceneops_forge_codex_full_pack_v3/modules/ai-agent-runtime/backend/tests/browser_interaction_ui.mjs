// Real workbench click against the isolated live service, not a mocked HTTP result.
import { createRequire } from 'node:module';
import path from 'node:path';
import { fileURLToPath } from 'node:url';
const root = path.resolve(path.dirname(fileURLToPath(import.meta.url)), '../../../..');
const require = createRequire(path.join(root, 'package.json'));
import { createServer } from 'vite';
const { chromium } = require(process.env.SCENEOPS_PLAYWRIGHT_MODULE);
const [apiPort, screenshot] = process.argv.slice(2);
const server = await createServer({configFile:false,root:path.join(root,'apps/web'),
  resolve:{dedupe:['react','react-dom','@tanstack/react-query']},
  server:{host:'127.0.0.1',port:0,proxy:{'/api':{target:`http://127.0.0.1:${apiPort}`}}}});
let browser;
let page;
try {
  await server.listen();
  browser = await chromium.launch({headless:true});
  page = await browser.newPage({viewport:{width:1440,height:1000}});
  page.on('pageerror',error=>process.stderr.write(error.stack+'\n'));
  page.on('console',message=>{if(message.type()==='error')process.stderr.write(message.text()+'\n');});
  page.on('response',response=>{if(response.status()>=400)process.stderr.write(`${response.status()} ${response.url()}\n`);});
  await page.goto(`http://127.0.0.1:${server.httpServer.address().port}/s3-workbench.html`);
  const panel = page.getByRole('region',{name:'受控输入检查'});
  const [response] = await Promise.all([
    page.waitForResponse(r=>r.url().endsWith('/game/interaction') && r.request().method()==='POST',{timeout:40000}),
    panel.getByRole('button',{name:'检查移动与收集',exact:true}).click(),
  ]);
  const run = (await response.json()).interaction;
  if(run.status!=='succeeded')throw Error(JSON.stringify(run));
  const screenshotImage = panel.getByRole('img',{name:'受控输入后的实际构建截图'});
  await screenshotImage.waitFor({state:'visible'});
  await page.waitForFunction(()=>[...document.images].some(image=>image.alt==='受控输入后的实际构建截图'&&image.complete&&image.naturalWidth>0));
  await panel.screenshot({path:screenshot});
  process.stdout.write(JSON.stringify({workbench_clicked:true,run_id:run.id,screenshot_displayed:true,screenshot}));
} catch(error) {
  if(page)process.stderr.write((await page.content())+'\n');
  throw error;
} finally {if(browser)await browser.close();await server.close();}
