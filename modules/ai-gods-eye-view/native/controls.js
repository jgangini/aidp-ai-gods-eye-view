export async function mountControls({ request, signal }) {
  try { await request('/api/admin/session', { signal }); }
  catch { return; }
  if (signal.aborted) return;
  const host = document.querySelector('#title-bar');
  if (!host) return;
  const button = document.createElement('button');
  button.type = 'button'; button.className = 'gev-controls-button'; button.textContent = 'Source controls';
  button.setAttribute('aria-haspopup', 'dialog');
  const dialog = document.createElement('dialog');
  dialog.className = 'gev-controls-dialog'; dialog.setAttribute('aria-label', 'Source controls');
  const header = document.createElement('header');
  const title = document.createElement('strong'); title.textContent = 'God’s Eye View · Source controls';
  const close = document.createElement('button'); close.type = 'button'; close.textContent = 'Close';
  const frame = document.createElement('iframe'); frame.title = 'Social, sensor and provider controls';
  header.append(title, close); dialog.append(header, frame); document.body.append(dialog); host.append(button);
  let loaded = false;
  const open = (section = '') => {
    if (!loaded) { frame.src = '/controls/' + section; loaded = true; }
    else if (section) { if (frame.contentWindow) frame.contentWindow.location.hash = section; else frame.src = '/controls/' + section; }
    dialog.showModal(); close.focus();
  };
  button.addEventListener('click', () => open(), { signal });
  close.addEventListener('click', () => dialog.close(), { signal });
  dialog.addEventListener('close', () => button.focus(), { signal });
  const show = (event) => open(event.detail === 'parameters' ? '#parameters' : '');
  window.addEventListener('gev-open-controls', show, { signal });
  signal.addEventListener('abort', () => { dialog.close(); dialog.remove(); button.remove(); }, { once: true });
}
