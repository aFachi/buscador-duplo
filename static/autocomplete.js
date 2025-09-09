function setupAutocomplete(inputId, dataListId, endpoint, formatItem) {
  const input = document.getElementById(inputId);
  const dl = document.getElementById(dataListId);
  if (!input || !dl) return;
  let controller;
  input.addEventListener('input', async () => {
    const q = input.value.trim();
    if (q.length < 2) {
      dl.innerHTML = '';
      if (controller) controller.abort();
      return;
    }
    if (controller) controller.abort();
    controller = new AbortController();
    try {
      const res = await fetch(`${endpoint}?q=${encodeURIComponent(q)}`, {
        signal: controller.signal,
      });
      if (!res.ok) return;
      const data = await res.json();
      dl.innerHTML = '';
      data.forEach((item) => {
        const opt = document.createElement('option');
        opt.value = formatItem(item);
        dl.appendChild(opt);
      });
    } catch (err) {
      if (err.name !== 'AbortError') console.error(err);
    }
  });
}

setupAutocomplete(
  'produto',
  'produto-suggestions',
  '/api/suggest/produto',
  (item) => `${item.codigo} - ${item.descricao}`
);
setupAutocomplete(
  'veiculo',
  'veiculo-suggestions',
  '/api/suggest/veiculo',
  (item) =>
    `${item.marca} ${item.modelo} ${item.ano_inicio}${item.ano_fim ? '/' + item.ano_fim : ''} ${item.motor}`.trim()
);
