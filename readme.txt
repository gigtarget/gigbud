GigBud Courier Story Experience
================================

This repository pairs a printable QR sticker with a scroll-powered microsite that lets customers
ride along with their courier from order ping to doorstep celebration.

Quick start
-----------

1. Open `qr-card.html` in a browser and print it on sticker paper to attach to delivery bags. The
   card includes a static QR code that opens the story page encoded with the URL `https://gbd.to/r1`.
2. Host `index.html` together with the `css`, `js`, and `assets` folders on any static site provider.
   After scanning the QR code, customers arrive at the animated story timeline.

What you get
------------

- **Spotlight hero** that morphs with each scroll scene, highlighting timestamps, emojis, and vibrant
gradients.
- **Six interactive chapters** covering the full delivery adventure with animated visuals and
  immersive storytelling beats.
- **Sparkle toast** finish that nudges for a rating in a light-hearted way (with optional haptic
  feedback on supported devices).

Customising the QR code
-----------------------

Need the QR to point to a different link? Use the included Python script:

```
python tools_generate_qr.py https://your-url-here assets/qr-code.svg
```

This regenerates the `assets/qr-code.svg` file with the new destination. Reload `qr-card.html` to
print updated stickers.

Structure
---------

- `index.html` – Scroll narrative landing page.
- `css/styles.css` – Visual design for the storytelling experience.
- `js/main.js` – Scroll-driven spotlight updates and sparkle toast interaction.
- `qr-card.html` – Print-ready sticker with the static QR code.
- `assets/qr-code.svg` – Generated QR code asset.
- `tools_generate_qr.py` – Dependency-free QR code generator supporting URLs up to version 4-L.

Enjoy sharing the micro-adventure with every delivery!
