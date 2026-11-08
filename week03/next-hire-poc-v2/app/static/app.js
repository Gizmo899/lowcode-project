document.addEventListener('click', async (event) => {
  const button = event.target.closest('[data-copy]');
  if (!button) return;
  const value = button.getAttribute('data-copy') || '';
  const original = button.textContent;
  try {
    await navigator.clipboard.writeText(value);
    button.textContent = 'Copied';
    button.classList.add('copy-success');
  } catch (error) {
    const helper = document.createElement('textarea');
    helper.value = value;
    helper.setAttribute('readonly', '');
    helper.style.position = 'absolute';
    helper.style.left = '-9999px';
    document.body.appendChild(helper);
    helper.select();
    try {
      document.execCommand('copy');
      button.textContent = 'Copied';
      button.classList.add('copy-success');
    } catch (_fallbackError) {
      button.textContent = 'Copy unavailable';
    }
    helper.remove();
  }
  window.setTimeout(() => {
    button.textContent = original;
    button.classList.remove('copy-success');
  }, 1800);
});
