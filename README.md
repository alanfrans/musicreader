# MusicReader

MusicReader is a free, offline Windows tool that reconstructs parallel hymn
verses from sheet-music images and PDFs. It detects the paired staves, isolates
the lyric area, keeps OCR coordinates, reads each verse row from left to right,
and joins the matching rows across music systems.

No cloud service, API key, or separate Tesseract installation is required.
RapidOCR and ONNX Runtime perform recognition locally.

## Install on Windows

1. Install [Python 3.10 or newer](https://www.python.org/downloads/windows/).
   Enable **Add Python to PATH** during installation.
2. Put this project in `C:\gitdev\sheet-lyrics`.
3. Double-click `MusicReader.bat`.

The first launch creates `.venv` and downloads the Python packages and OCR
models. Later launches reuse that environment.

## Use the desktop tool

1. Choose a JPG, PNG, TIFF, or PDF.
2. Leave **Verses** set to **Auto**, or select the count if automatic detection
   gets it wrong.
3. Select **Extract lyrics**.
4. Proofread the result and select **Save text**.

For best results, use straight, uncropped pages at 300–400 DPI. The tool is
designed for hymns where multiple lyric rows appear between a treble and bass
staff. It is not intended to recognize musical notes.

OCR can still confuse similar characters or unusual typefaces. MusicReader
reconstructs layout and joins printed syllables deterministically; it does not
invent or language-correct words.

## Command line

After the first GUI launch:

```powershell
cd C:\gitdev\sheet-lyrics
.\.venv\Scripts\musicreader.exe "C:\scans\hymn.jpg" -o lyrics.txt
```

Useful options:

```text
--verses 4          Force four parallel verse rows
--dpi 400           Render PDF pages at 400 DPI
--confidence 0.35   Retain lower-confidence OCR text
--debug-dir debug   Save lyric crops and marked-up page images
```

Run `.\.venv\Scripts\musicreader.exe --help` for all options.

## Development

```powershell
py -3 -m venv .venv
.\.venv\Scripts\python.exe -m pip install -e .
.\.venv\Scripts\python.exe -m unittest discover -s tests
```

The main stages are:

- `musicreader/layout.py`: PDF/image loading and staff detection
- `musicreader/extractor.py`: local OCR and extraction orchestration
- `musicreader/reconstruct.py`: row clustering and verse reconstruction
- `musicreader/gui.py`: Windows desktop interface

## Privacy

Images and recognized text remain on the computer. Package installation may
access Python package servers during initial setup; extraction itself does not
upload documents.
