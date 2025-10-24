const shareButton = document.querySelector('[data-action="share"]');
const reminderButton = document.querySelector('[data-action="reminder"]');
const form = document.querySelector('.contact-form');

const showToast = (message) => {
  let toast = document.querySelector('.toast');
  if (!toast) {
    toast = document.createElement('div');
    toast.className = 'toast';
    toast.setAttribute('role', 'status');
    toast.setAttribute('aria-live', 'polite');
    document.body.appendChild(toast);
  }
  toast.textContent = message;
  toast.classList.add('is-visible');
  setTimeout(() => toast.classList.remove('is-visible'), 3200);
};

if (shareButton) {
  shareButton.addEventListener('click', async () => {
    const shareData = {
      title: 'Meet Riya, your GigBud courier',
      text: 'Just delivered my order — show some love with a 5⭐ rating!',
      url: window.location.href,
    };

    try {
      if (navigator.share) {
        await navigator.share(shareData);
      } else {
        await navigator.clipboard.writeText(shareData.url);
        showToast('Link copied! Share it with your friends.');
      }
    } catch (error) {
      showToast('Unable to share right now, but you can copy the link manually.');
    }
  });
}

if (reminderButton) {
  reminderButton.addEventListener('click', async () => {
    if ('Notification' in window) {
      const permission = await Notification.requestPermission();
      if (permission === 'granted') {
        new Notification('GigBud reminder', {
          body: 'Don\'t forget to leave a 5⭐ rating for Riya! 🎉',
        });
      } else {
        showToast('Reminder saved! Check back in your app in a bit.');
      }
    } else {
      showToast('Set a reminder in your phone to rate the delivery.');
    }
  });
}

if (form) {
  form.addEventListener('submit', (event) => {
    event.preventDefault();
    const nameField = form.querySelector('#name');
    const messageField = form.querySelector('#message');
    const name = nameField.value.trim() || 'GigBud friend';

    showToast(`Thanks, ${name}! Your note made Riya\'s day.`);
    form.reset();
  });
}

const style = document.createElement('style');
style.textContent = `
.toast {
  position: fixed;
  left: 50%;
  bottom: 2.5rem;
  transform: translate(-50%, 100%);
  background: rgba(15, 23, 42, 0.9);
  color: #fff;
  padding: 0.85rem 1.4rem;
  border-radius: 999px;
  box-shadow: 0 12px 30px rgba(15, 23, 42, 0.35);
  opacity: 0;
  transition: transform 0.3s ease, opacity 0.3s ease;
  z-index: 1000;
}

.toast.is-visible {
  transform: translate(-50%, 0);
  opacity: 1;
}
`;
document.head.appendChild(style);
