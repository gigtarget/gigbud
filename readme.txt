GigBud Courier Microsite
=========================

This repository contains a printable QR code sticker and a playful landing page that introduces
customers to the courier who delivered their order.

Quick start
-----------

1. Open `qr-card.html` in a browser and print it on sticker paper to attach to delivery bags. The
   card includes a static QR code that opens the profile page encoded with the URL
   `https://gbd.to/r1`.
2. Host the `index.html` file (and the `css`, `js`, and `assets` folders) on any static site
   provider. After scanning the QR code, customers will land on this page to learn more about the
   courier and get a friendly reminder to leave a 5-star rating.

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

- `index.html` – Main profile landing page for customers.
- `css/styles.css` – Visual design for the landing page.
- `js/main.js` – Small enhancements (sharing, reminders, thank-you toast).
- `qr-card.html` – Print-ready sticker with the static QR code.
- `assets/qr-code.svg` – Generated QR code asset.
- `tools_generate_qr.py` – Dependency-free QR code generator supporting URLs up to version 4-L.

Enjoy connecting with customers after every delivery!
