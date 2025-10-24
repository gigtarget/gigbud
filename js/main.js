const scenes = Array.from(document.querySelectorAll('.scene'));
const spotlightLabel = document.getElementById('spotlightLabel');
const spotlightEmoji = document.getElementById('spotlightEmoji');
const spotlightTitle = document.getElementById('spotlightTitle');
const spotlightSubtitle = document.getElementById('spotlightSubtitle');
const progressBar = document.getElementById('progressBar');
const sparkleButton = document.querySelector('[data-action="spark"]');
const toast = document.querySelector('.sparkle-toast');
const root = document.documentElement;

const setActiveScene = (scene) => {
  if (!scene) return;
  scenes.forEach((item) => item.classList.toggle('scene--active', item === scene));

  const { label, emoji, title, subtitle, gradient, accent } = scene.dataset;

  if (label) {
    spotlightLabel.textContent = label;
  }
  if (emoji) {
    spotlightEmoji.textContent = emoji;
  }
  if (title) {
    spotlightTitle.textContent = title;
  }
  if (subtitle) {
    spotlightSubtitle.textContent = subtitle;
  }
  if (gradient) {
    root.style.setProperty('--spotlight-gradient', gradient);
  }
  if (accent) {
    root.style.setProperty('--accent', accent);
    progressBar.style.background = accent;
    progressBar.style.boxShadow = `0 10px 30px ${accent}55`;
  }

  const index = scenes.indexOf(scene);
  const progress = scenes.length > 1 ? index / (scenes.length - 1) : 1;
  progressBar.style.transform = `scaleX(${progress})`;
};

const observer = new IntersectionObserver(
  (entries) => {
    entries.forEach((entry) => {
      if (entry.isIntersecting) {
        setActiveScene(entry.target);
      }
    });
  },
  {
    root: null,
    threshold: window.matchMedia('(min-width: 1180px)').matches ? 0.5 : 0.35,
  }
);

scenes.forEach((scene) => observer.observe(scene));
setActiveScene(scenes[0]);

const showToast = (message) => {
  if (!toast) return;
  toast.hidden = false;
  toast.textContent = message;
  toast.classList.add('is-visible');
  window.setTimeout(() => {
    toast.classList.remove('is-visible');
  }, 2600);
};

if (sparkleButton) {
  sparkleButton.addEventListener('click', () => {
    if (navigator.vibrate) {
      navigator.vibrate(40);
    }
    showToast('Sparkle launched! Thanks for the high-five ✨');
  });
}

window.addEventListener('load', () => {
  const prefersReducedMotion = window.matchMedia('(prefers-reduced-motion: reduce)').matches;
  if (prefersReducedMotion) {
    progressBar.style.transform = 'scaleX(1)';
  }
});
