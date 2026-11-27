/* Accessible, reduced-motion-aware typewriter motion for page and section headings. */
(() => {
  const reduceMotion = window.matchMedia('(prefers-reduced-motion: reduce)').matches;
  if (reduceMotion) return;

  const cycles = [...document.querySelectorAll('[data-type-cycle]')];

  function typeText(heading, loop = false) {
    if (!heading || heading.dataset.typewriterDone === 'true') return;

    const fullText = heading.textContent.replace(/\s+/g, ' ').trim();
    if (!fullText || fullText.length > 120) return;

    const originalMinHeight = heading.style.minHeight;
    const reservedHeight = heading.getBoundingClientRect().height;
    if (reservedHeight) heading.style.minHeight = `${reservedHeight}px`;
    if (!heading.hasAttribute('aria-label')) heading.setAttribute('aria-label', fullText);
    heading.dataset.typewriterDone = 'true';
    heading.classList.add('typewriter-active');

    const queue = [];
    function prepareText(node) {
      [...node.childNodes].forEach((child) => {
        if (child.nodeType === Node.TEXT_NODE && child.textContent) {
          const run = document.createElement('span');
          run.className = 'typewriter-run';
          run.setAttribute('aria-hidden', 'true');
          const characters = [...child.textContent.replace(/\s+/g, ' ')];
          child.replaceWith(run);
          characters.forEach((character) => queue.push({ run, character }));
        } else if (child.nodeType === Node.ELEMENT_NODE && !child.matches('script,style,svg')) {
          prepareText(child);
        }
      });
    }
    prepareText(heading);

    const pace = Math.min(38, Math.max(24, 1050 / Math.max(queue.length, 1)));
    const letters = queue.map(({ character }) => {
      const letter = document.createElement('span');
      letter.className = 'typewriter-char';
      letter.textContent = character;
      return letter;
    });
    let typed = 0;
    let timer = null;
    let pendingAction = null;
    let pendingDelay = 0;

    function schedule(action, delay) {
      pendingAction = action;
      pendingDelay = delay;
      if (document.hidden) return;
      timer = window.setTimeout(() => {
        timer = null;
        pendingAction = null;
        action();
      }, delay);
    }

    function typeNext() {
      if (!heading.isConnected) return;
      if (typed >= letters.length) {
        if (loop) {
          schedule(eraseNext, 1350);
        } else {
          heading.classList.remove('typewriter-active');
          heading.classList.add('typewriter-complete');
          heading.style.minHeight = originalMinHeight;
        }
        return;
      }
      queue[typed].run.append(letters[typed]);
      const character = queue[typed].character;
      typed += 1;
      schedule(typeNext, pace + (/[,.!?;:]/.test(character) ? 95 : 0));
    }

    function eraseNext() {
      if (!heading.isConnected) return;
      if (typed <= 0) {
        schedule(typeNext, 420);
        return;
      }
      typed -= 1;
      letters[typed].remove();
      schedule(eraseNext, Math.max(14, pace * .48));
    }

    document.addEventListener('visibilitychange', () => {
      if (document.hidden) {
        window.clearTimeout(timer);
        timer = null;
      } else if (pendingAction && !timer) {
        schedule(pendingAction, pendingDelay);
      }
    });
    schedule(typeNext, 80);
  }

  function typePageHeading() {
    const heading = [...document.querySelectorAll('h1')].find((node) => {
      const rect = node.getBoundingClientRect();
      const style = getComputedStyle(node);
      return rect.width > 2 && rect.height > 2 && style.display !== 'none' &&
        style.visibility !== 'hidden' && !node.closest('[aria-hidden="true"]');
    });
    typeText(heading, true);
  }

  function typeSectionHeadings() {
    const headings = [...document.querySelectorAll('.section-title-home')];
    if (!headings.length) return;
    if (!('IntersectionObserver' in window)) {
      headings.forEach((heading) => typeText(heading));
      return;
    }
    const observer = new IntersectionObserver((entries, activeObserver) => {
      entries.forEach((entry) => {
        if (entry.isIntersecting) {
          typeText(entry.target, true);
          activeObserver.unobserve(entry.target);
        }
      });
    }, { threshold: .35, rootMargin: '0px 0px -5% 0px' });
    headings.forEach((heading) => observer.observe(heading));
  }

  function initTypeCycle() {
    if (!cycles.length || !('IntersectionObserver' in window)) return;
    const node = cycles[0];
    const phrases = node.dataset.typeCycle.split('|').filter(Boolean).slice(0, 8);
    const output = node.querySelector('[aria-hidden="true"]') || node.firstElementChild;
    if (phrases.length < 2 || phrases.some((phrase) => phrase.length > 42) || !output) return;

    let index = 0;
    let timer = null;
    const observer = new IntersectionObserver(([entry]) => {
      window.clearTimeout(timer);
      if (entry.isIntersecting && !document.hidden) timer = window.setTimeout(showNext, 2600);
    });
    function showNext() {
      index = (index + 1) % phrases.length;
      output.textContent = phrases[index];
      output.classList.remove('cycle-in');
      requestAnimationFrame(() => output.classList.add('cycle-in'));
      timer = window.setTimeout(showNext, 3200);
    }
    observer.observe(node);
    document.addEventListener('visibilitychange', () => {
      window.clearTimeout(timer);
      if (!document.hidden && node.getBoundingClientRect().bottom > 0) timer = window.setTimeout(showNext, 2600);
    }, { passive: true });
  }

  requestAnimationFrame(() => {
    typePageHeading();
    typeSectionHeadings();
    initTypeCycle();
  });
})();
