/* Privacy-safe optional events: never read or transmit form values. */
const startedAssessments = new WeakSet();

document.addEventListener('focusin', function (event) {
  const form = event.target.closest?.('form[data-analytics-category]');
  if (!form || startedAssessments.has(form) || typeof window.gtag !== 'function') return;
  startedAssessments.add(form);
  window.gtag('event', 'assessment_start', {
    category: form.dataset.analyticsCategory,
    transport_type: 'beacon'
  });
}, true);

document.addEventListener('submit', function (event) {
  const form = event.target;
  if (!(form instanceof HTMLFormElement) || !form.dataset.analyticsEvent) return;
  if (typeof window.gtag !== 'function') return;
  window.gtag('event', form.dataset.analyticsEvent, {
    category: form.dataset.analyticsCategory || 'unknown',
    transport_type: 'beacon'
  });
}, true);
