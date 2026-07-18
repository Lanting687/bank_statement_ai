## OCR Engine

This project uses [docTR](https://github.com/mindee/doctr) (Document Text Recognition), 
a deep-learning OCR library that handles both scanned and digital PDFs without any 
manual configuration.

It runs two neural networks in sequence:
- **Detection** — finds where text is on the page
- **Recognition** — reads what the text says in each detected region

Both networks use pre-trained weights, so no training or labelled data is required.