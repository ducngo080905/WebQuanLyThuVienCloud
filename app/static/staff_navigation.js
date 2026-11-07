(() => {
  const sidebar = document.getElementById('staffSidebar');
  const drawer = document.getElementById('staffDrawer');
  const toggle = document.querySelector('.staff-menu-toggle');
  if (!sidebar || !drawer || !toggle) return;

  const mobile = matchMedia('(max-width: 1024px)');
  document.body.classList.add('staff-shell-ready');

  function updateToggle() {
    const expanded = mobile.matches
      ? drawer.open
      : !document.body.classList.contains('staff-sidebar-collapsed');
    toggle.setAttribute('aria-expanded', String(expanded));
    toggle.setAttribute('aria-label', expanded ? 'Thu gọn menu quản trị' : 'Mở menu quản trị');
  }

  toggle.addEventListener('click', () => {
    if (mobile.matches) {
      drawer.append(sidebar);
      drawer.showModal();
    } else {
      document.body.classList.toggle('staff-sidebar-collapsed');
    }
    updateToggle();
  });

  sidebar.querySelector('.staff-menu-close').addEventListener('click', () => drawer.close());
  drawer.addEventListener('click', event => {
    if (event.target === drawer) drawer.close();
  });
  drawer.addEventListener('close', () => {
    drawer.before(sidebar);
    updateToggle();
    toggle.focus({preventScroll: true});
  });
  mobile.addEventListener('change', () => {
    if (drawer.open) drawer.close();
    updateToggle();
  });
  updateToggle();
})();
