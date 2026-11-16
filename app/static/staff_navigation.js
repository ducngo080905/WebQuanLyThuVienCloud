(() => {
  const sidebar = document.getElementById('staffSidebar');
  const drawer = document.getElementById('staffDrawer');
  const toggle = document.querySelector('.staff-menu-toggle');
  if (!sidebar || !drawer || !toggle) return;

  const mobile = matchMedia('(max-width: 1024px)');
  const reduced = matchMedia('(prefers-reduced-motion: reduce)');
  const root = document.documentElement;
  const layoutAnimations = new Map();
  document.body.classList.add('staff-shell-ready');

  function updateToggle() {
    const expanded = mobile.matches
      ? drawer.open
      : !root.classList.contains('staff-sidebar-collapsed');
    sidebar.inert = !mobile.matches && !expanded;
    toggle.setAttribute('aria-expanded', String(expanded));
    toggle.setAttribute('aria-label', expanded ? 'Thu gọn menu quản trị' : 'Mở menu quản trị');
  }

  toggle.addEventListener('click', () => {
    if (mobile.matches) {
      drawer.append(sidebar);
      drawer.showModal();
    } else {
      // Resize once, then animate only the composited position of the new layout.
      const panels = [document.querySelector('.main'), document.querySelector('.topbar')].filter(Boolean);
      const previous = panels.map(panel => panel.getBoundingClientRect().left);
      layoutAnimations.forEach(animation => animation.cancel()); layoutAnimations.clear();
      const collapsed = root.classList.toggle('staff-sidebar-collapsed');
      try { sessionStorage.setItem('library-staff-sidebar-collapsed', collapsed ? '1' : '0'); } catch (_) {}
      if (!reduced.matches) panels.forEach((panel, index) => {
        const delta = previous[index] - panel.getBoundingClientRect().left;
        if (!delta || !panel.animate) return;
        const animation = panel.animate([{transform: `translateX(${delta}px)`}, {transform: 'translateX(0)'}],
          {duration: 190, easing: 'cubic-bezier(.2,.8,.2,1)'});
        layoutAnimations.set(panel, animation);
        animation.finished.then(() => { if (layoutAnimations.get(panel) === animation) layoutAnimations.delete(panel); }, () => {});
      });
    }
    updateToggle();
  });

  sidebar.querySelector('.staff-menu-close').addEventListener('click', () => drawer.close());
  drawer.addEventListener('click', event => {
    if (event.target === drawer) drawer.close();
  });
  drawer.addEventListener('close', () => {
    if (!mobile.matches) drawer.before(sidebar);
    updateToggle();
    toggle.focus({preventScroll: true});
  });
  mobile.addEventListener('change', () => {
    layoutAnimations.forEach(animation => animation.cancel()); layoutAnimations.clear();
    if (drawer.open) drawer.close();
    if (!mobile.matches) drawer.before(sidebar);
    updateToggle();
  });
  updateToggle();
})();
