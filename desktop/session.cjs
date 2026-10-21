'use strict';
const crypto = require('node:crypto');
const path = require('node:path');
function createSession() { return crypto.randomBytes(32).toString('hex'); }
function isLocalAddress(url) {
  try { const parsed = new URL(url); return parsed.protocol === 'http:' && parsed.hostname === '127.0.0.1' && Boolean(parsed.port) && !parsed.username && !parsed.password; }
  catch { return false; }
}
function isApplicationUrl(candidate, address) {
  try { return isLocalAddress(address) && new URL(candidate).origin === new URL(address).origin; }
  catch { return false; }
}
function backendCommand({ packaged, resourcesPath, root }) {
  if (packaged) return { command: path.join(resourcesPath, 'runtime', 'video-anatomy-backend', 'video-anatomy-backend'), args: [], cwd: resourcesPath, mediaBin: path.join(resourcesPath, 'runtime', 'media-bin') };
  return { command: path.join(root, '.venv', 'bin', 'python'), args: [path.join(root, 'scripts', 'local_server.py')], cwd: root, mediaBin: '' };
}
function privateEnvironment(mediaBin) {
  const environment = { ...process.env };
  delete environment.OPENAI_API_KEY;
  delete environment.ELECTRON_RUN_AS_NODE;
  if (mediaBin) environment.PATH = `${mediaBin}${path.delimiter}${environment.PATH || ''}`;
  return environment;
}
module.exports = { createSession, isLocalAddress, isApplicationUrl, backendCommand, privateEnvironment };
