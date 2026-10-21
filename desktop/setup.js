'use strict';
const $ = selector => document.querySelector(selector);
(async () => {
  const status = await window.videoAnatomySetup.status();
  $('#use-saved').disabled = !status.hasSavedKey;
  $('#use-saved').checked = status.hasSavedKey;
  $('#remember').disabled = !status.canRemember;
  $('#library').textContent = `Library: ${status.library}`;
})();
async function start(offline) {
  const buttons = document.querySelectorAll('button');
  buttons.forEach(button => { button.disabled = true; });
  $('#status').textContent = 'Opening your workspace…';
  const key = $('#key').value; $('#key').value = '';
  try {
    const result = await window.videoAnatomySetup.start({ key, offline, useSaved: $('#use-saved').checked, remember: $('#remember').checked });
    if (!result.ok) $('#status').textContent = result.message;
  } catch { $('#status').textContent = 'Startup could not complete. Reopen the app to try again.'; }
  finally { buttons.forEach(button => { button.disabled = false; }); }
}
$('#setup').addEventListener('submit', event => { event.preventDefault(); start(false); });
$('#offline').addEventListener('click', () => start(true));
$('#choose').addEventListener('click', async () => { $('#chosen').textContent = await window.videoAnatomySetup.chooseLibrary(); });
