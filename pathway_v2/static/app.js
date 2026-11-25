(function () {
  document.querySelectorAll('form[data-confirm]').forEach((form) => {
    form.addEventListener('submit', (event) => {
      if (!window.confirm(form.dataset.confirm)) event.preventDefault();
    });
  });

  const role = document.getElementById('role');
  if (!role) return;

  const adviserField = document.getElementById('adviser-field');
  const phoneField = document.getElementById('phone-field');
  const adviserSelect = document.getElementById('assigned_adviser_id');
  const phoneInput = document.getElementById('phone');

  function syncRoleFields() {
    const isJobseeker = role.value === 'jobseeker';
    if (adviserField) adviserField.hidden = !isJobseeker;
    if (phoneField) phoneField.hidden = !isJobseeker;
    if (adviserSelect) adviserSelect.required = isJobseeker && adviserSelect.options.length > 1;
  }

  role.addEventListener('change', syncRoleFields);
  syncRoleFields();
})();
