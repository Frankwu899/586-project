'use strict';
const fs = require('node:fs');
const path = require('node:path');
const crypto = require('node:crypto');
module.exports = async function verifyRuntime(context) {
  if (process.platform !== 'darwin') throw new Error('Build and validate the macOS installer on macOS.');
  const targetArch = require('builder-util').Arch[context.arch];
  if (targetArch !== process.arch) throw new Error('Build the installer on a Mac matching its target architecture.');
  const runtime = path.join(__dirname, 'runtime');
  for (const required of ['manifest.json', 'video-anatomy-backend/video-anatomy-backend', 'media-bin/ffmpeg', 'media-bin/ffprobe', 'notices/FFmpeg.txt']) {
    if (!fs.existsSync(path.join(runtime, required))) throw new Error(`Missing bundled runtime file: ${required}`);
  }
  const manifest = JSON.parse(fs.readFileSync(path.join(runtime, 'manifest.json'), 'utf8'));
  if (manifest.platform !== 'darwin' || manifest.architecture !== (process.arch === 'x64' ? 'x86_64' : process.arch)) throw new Error('Runtime architecture must match the packaging machine. Build each architecture separately.');
  for (const [relative, expected] of Object.entries(manifest.files)) {
    const full = path.resolve(runtime, relative);
    if (!full.startsWith(runtime + path.sep)) throw new Error('Invalid runtime manifest path.');
    const actual = crypto.createHash('sha256').update(fs.readFileSync(full)).digest('hex');
    if (actual !== expected) throw new Error(`Bundled runtime verification failed: ${relative}`);
  }
};
