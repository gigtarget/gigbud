const state = {
  product: null,
  design: null,
};

const PROMPT = `Generate a realistic product photoshoot-style image by combining the uploaded garden photo and the design image.\n\nThe result should look like a professional studio product photograph — softly lit with smooth, diffused shadows. Use a seamless matte light-gray background that gradually fades into white, creating a clean, neutral tone without visible edges or horizon lines.\n\nPlace the product centrally on a minimal reflective surface that casts a gentle, natural shadow underneath. Maintain sharp focus on the product with a shallow depth of field so that the background appears softly blurred.\n\nThe camera angle should be slightly low and front-facing (eye level with the product) to highlight form and texture. Lighting must be balanced from both sides with a subtle top fill — no harsh highlights, just soft, even illumination to emphasize the contours.\n\nThe final image should have a premium, high-end aesthetic suitable for catalogs or brand presentations, showcasing realism, symmetry, and clarity.`;

const GOOGLE_API_KEY = 'AIzaSyCme1xZWmmPyWX7AzQhZaunSVRg3xvvW4c';
const MODEL_URL = `https://generativelanguage.googleapis.com/v1beta/models/gemini-1.5-flash-latest:generateContent?key=${GOOGLE_API_KEY}`;

const generateButton = document.getElementById('generateButton');
const feedback = document.getElementById('feedback');
const resultFigure = document.querySelector('.result__figure');
const resultPlaceholder = document.querySelector('.result__placeholder');
const resultImage = document.getElementById('resultImage');
const loadingOverlay = document.getElementById('loadingOverlay');

const readFileAsDataURL = (file) =>
  new Promise((resolve, reject) => {
    const reader = new FileReader();
    reader.onload = () => resolve(reader.result);
    reader.onerror = (error) => reject(error);
    reader.readAsDataURL(file);
  });

const base64FromDataURL = (dataUrl) => {
  if (typeof dataUrl !== 'string') return '';
  const [, base64] = dataUrl.split('base64,');
  return base64 ?? '';
};

const setLoading = (isLoading) => {
  loadingOverlay.classList.toggle('is-visible', isLoading);
  loadingOverlay.setAttribute('aria-hidden', String(!isLoading));
  if (isLoading) {
    generateButton.disabled = true;
  } else {
    updateGenerateButtonVisibility();
  }
};

const updateGenerateButtonVisibility = () => {
  const ready = Boolean(state.product && state.design);
  generateButton.hidden = !ready;
  generateButton.disabled = !ready;
};

const updatePreview = (type, file) => {
  const card = document.querySelector(`.upload-card[data-upload="${type}"]`);
  if (!card) return;

  const preview = card.querySelector('.upload-card__preview');
  const body = card.querySelector('.upload-card__body');
  const filename = card.querySelector('.upload-card__filename');
  const img = preview?.querySelector('img');

  if (!file) {
    preview?.setAttribute('hidden', '');
    body.removeAttribute('hidden');
    if (filename) filename.textContent = '';
    if (img) img.src = '';
    card.classList.remove('has-file');
    return;
  }

  readFileAsDataURL(file)
    .then((dataUrl) => {
      if (img) {
        img.src = dataUrl;
      }
      if (filename) {
        filename.textContent = file.name;
      }
      body.setAttribute('hidden', '');
      preview?.removeAttribute('hidden');
      card.classList.add('has-file');
    })
    .catch(() => {
      feedback.textContent = 'We could not preview that file. Try another image.';
      state[type] = null;
      updateGenerateButtonVisibility();
    });
};

const handleFileSelection = (type, fileList) => {
  if (!fileList?.length) return;
  const file = fileList[0];
  if (!file.type.startsWith('image/')) {
    feedback.textContent = 'Please choose an image file (PNG, JPG, or WEBP).';
    return;
  }

  state[type] = file;
  feedback.textContent = '';
  updatePreview(type, file);
  updateGenerateButtonVisibility();
};

const setupUploadCard = (card) => {
  const input = card.querySelector('input[type="file"]');
  const trigger = card.querySelector('.upload-card__trigger');
  const type = card.dataset.upload;

  const openFilePicker = () => input?.click();

  trigger?.addEventListener('click', (event) => {
    event.stopPropagation();
    openFilePicker();
  });

  card.addEventListener('click', () => {
    openFilePicker();
  });

  card.addEventListener('dragover', (event) => {
    event.preventDefault();
    card.classList.add('is-dragging');
  });

  card.addEventListener('dragleave', () => {
    card.classList.remove('is-dragging');
  });

  card.addEventListener('drop', (event) => {
    event.preventDefault();
    card.classList.remove('is-dragging');
    handleFileSelection(type, event.dataTransfer?.files);
  });

  input?.addEventListener('change', (event) => {
    handleFileSelection(type, event.target.files);
  });
};

const uploadCards = document.querySelectorAll('.upload-card');
uploadCards.forEach(setupUploadCard);
updateGenerateButtonVisibility();

const collectInlineData = async () => {
  const [productDataUrl, designDataUrl] = await Promise.all([
    readFileAsDataURL(state.product),
    readFileAsDataURL(state.design),
  ]);

  return [
    {
      inline_data: {
        mime_type: state.product?.type || 'image/png',
        data: base64FromDataURL(productDataUrl),
      },
    },
    {
      inline_data: {
        mime_type: state.design?.type || 'image/png',
        data: base64FromDataURL(designDataUrl),
      },
    },
  ];
};

const extractImageFromResponse = (payload) => {
  const candidates = payload?.candidates || [];
  for (const candidate of candidates) {
    const parts = candidate?.content?.parts || [];
    for (const part of parts) {
      if (part.inline_data?.data) {
        return part.inline_data.data;
      }
      if (part.text?.startsWith('data:image')) {
        return part.text.split('base64,')[1];
      }
    }
  }
  return '';
};

const generateMockup = async () => {
  if (!state.product || !state.design) return;

  feedback.textContent = '';
  setLoading(true);

  try {
    const inlineDataParts = await collectInlineData();

    const response = await fetch(MODEL_URL, {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
      },
      body: JSON.stringify({
        contents: [
          {
            role: 'user',
            parts: [{ text: PROMPT }, ...inlineDataParts],
          },
        ],
      }),
    });

    if (!response.ok) {
      throw new Error(`Request failed with status ${response.status}`);
    }

    const payload = await response.json();
    const imageData = extractImageFromResponse(payload);

    if (!imageData) {
      throw new Error('The API response did not include an image.');
    }

    resultImage.src = `data:image/png;base64,${imageData}`;
    resultFigure?.removeAttribute('hidden');
    resultPlaceholder?.setAttribute('hidden', '');
    resultImage.focus?.();
    feedback.textContent = 'Mockup ready! Save the image or tweak your inputs for another version.';
  } catch (error) {
    console.error(error);
    feedback.textContent =
      'We ran into a problem generating the mockup. Please try again in a moment.';
  } finally {
    setLoading(false);
  }
};

generateButton?.addEventListener('click', generateMockup);

const loadingText = document.getElementById('loadingText');
loadingOverlay?.addEventListener('transitionstart', (event) => {
  if (event.propertyName === 'opacity' && loadingOverlay.classList.contains('is-visible')) {
    loadingText.textContent = 'Blending your images…';
  }
});
