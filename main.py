import os
import shutil
import subprocess
import tempfile
from typing import List, Optional

from pypdf import PdfWriter, PdfReader
from fastapi import FastAPI, UploadFile, File, Form, HTTPException, BackgroundTasks
from fastapi.responses import FileResponse

# Initialize FastAPI app
app = FastAPI(title="PDF Merge API", description="API to merge up to 10 PDF files into a single PDF", version="1.0.0")


@app.post("/merge-pdfs/", summary="Merge multiple PDF files", response_description="Merged PDF file")
async def merge_pdf_files(
    background_tasks: BackgroundTasks,
    files: List[UploadFile] = File(...),
    compress: str = Form(default="none"),
    quality: str = Form(default="ebook"),
    password: Optional[str] = Form(default=None),
) -> FileResponse:
    """
    Merge multiple PDF files into a single PDF with optional compression and password protection.

    Parameters:
    - files: List of uploaded PDF files (required)
    - compress: Compression type ('none', 'builtin', 'ghostscript'), default 'none'
    - quality: Quality for Ghostscript compression ('ebook', 'printer', 'prepress'), default 'ebook'
    - password: Optional password to encrypt the output PDF
    """
    valid_compress = {"none", "builtin", "ghostscript"}
    if compress not in valid_compress:
        raise HTTPException(status_code=400, detail=f"Invalid compress method. Allowed values: {list(valid_compress)}")

    valid_quality = {"ebook", "printer", "prepress"}
    if compress == "ghostscript" and quality not in valid_quality:
        raise HTTPException(status_code=400, detail=f"Invalid quality for Ghostscript. Allowed values: {list(valid_quality)}")

    # Create one temporary directory and set up subdirectories for input and output
    temp_dir = tempfile.TemporaryDirectory()
    temp_path = temp_dir.name
    input_dir = os.path.join(temp_path, "input")
    output_dir = os.path.join(temp_path, "output")
    os.makedirs(input_dir, exist_ok=True)
    os.makedirs(output_dir, exist_ok=True)
    # Schedule cleanup of the entire temporary directory after the response is sent.
    background_tasks.add_task(temp_dir.cleanup)

    try:
        # Save uploaded PDF files after validating file extension
        for file in files:
            if not file.filename or not file.filename.lower().endswith(".pdf"):
                raise HTTPException(status_code=400, detail="Only PDF files are allowed")
            file_path = os.path.join(input_dir, file.filename)
            content = await file.read()
            with open(file_path, "wb") as f:
                f.write(content)

        # Get sorted PDF paths from input directory
        pdf_paths = get_sorted_pdf_paths(input_dir)
        if not pdf_paths:
            raise HTTPException(status_code=400, detail="No valid PDF files found in the uploaded files.")

        merged_pdf_path = os.path.join(output_dir, "merged.pdf")

        # Merge PDFs using built-in compression/encryption if chosen.
        if compress in {"builtin", "none"}:
            merge_pdfs(pdf_paths, merged_pdf_path, compress_builtin=(compress == "builtin"), password=password)
        else:
            # For ghostscript compression, merge without applying password initially.
            merge_pdfs(pdf_paths, merged_pdf_path, compress_builtin=False, password=None)

        # Apply Ghostscript compression if selected.
        if compress == "ghostscript":
            temp_merged = os.path.join(output_dir, "merged.tmp.pdf")
            os.rename(merged_pdf_path, temp_merged)
            success = compress_with_ghostscript(temp_merged, merged_pdf_path, quality=quality)
            if success:
                os.remove(temp_merged)
            else:
                os.rename(temp_merged, merged_pdf_path)

        # If a password is provided and ghostscript was used, encrypt after compression.
        if password and compress == "ghostscript":
            temp_encrypted = os.path.join(output_dir, "merged.encrypted.pdf")
            encrypt_pdf(merged_pdf_path, temp_encrypted, password)
            os.replace(temp_encrypted, merged_pdf_path)

        return FileResponse(path=merged_pdf_path, filename="merged.pdf", media_type="application/pdf")

    except Exception as exc:
        # Clean up immediately if an error occurs
        temp_dir.cleanup()
        raise HTTPException(status_code=500, detail=f"An error occurred: {str(exc)}") from exc


def get_sorted_pdf_paths(input_dir: str) -> List[str]:
    """Collect and sort PDF files from the given directory alphabetically."""
    pdf_files: List[str] = []
    for filename in os.listdir(input_dir):
        if filename.lower().endswith(".pdf"):
            pdf_files.append(os.path.join(input_dir, filename))
    return sorted(pdf_files)


def merge_pdfs(input_paths: List[str], output_path: str, compress_builtin: bool = False, password: Optional[str] = None) -> None:
    """Merge multiple PDF files into a single PDF, with optional built-in compression and encryption."""
    writer = PdfWriter()
    for path in input_paths:
        writer.append(path)
    if compress_builtin:
        for page in writer.pages:
            page.compress_content_streams()
    if password:
        writer.encrypt(password)
    os.makedirs(os.path.dirname(output_path), exist_ok=True)
    with open(output_path, "wb") as output_file:
        writer.write(output_file)


def compress_with_ghostscript(input_pdf: str, output_pdf: str, quality: str = "ebook") -> bool:
    """Compress a PDF file using Ghostscript if available."""
    gs_executable = shutil.which("gs") or shutil.which("gswin64c") or shutil.which("gswin32c")
    if not gs_executable:
        print("Ghostscript not found. Please install Ghostscript or use built-in compression.")
        return False
    gs_command = [
        gs_executable,
        "-sDEVICE=pdfwrite",
        "-dCompatibilityLevel=1.4",
        f"-dPDFSETTINGS=/{quality}",
        "-dNOPAUSE",
        "-dQUIET",
        "-dBATCH",
        f"-sOutputFile={output_pdf}",
        input_pdf,
    ]
    try:
        print("Running Ghostscript to compress the PDF...")
        subprocess.run(gs_command, check=True)
        print(f"Compressed PDF saved to {output_pdf}")
        return True
    except subprocess.CalledProcessError as exception:
        print(f"Error running Ghostscript: {exception}")
        return False


def encrypt_pdf(input_pdf: str, output_pdf: str, password: str) -> None:
    """Encrypt an existing PDF file using the given password."""
    reader = PdfReader(input_pdf)
    writer = PdfWriter()
    for page in reader.pages:
        writer.add_page(page)
    writer.encrypt(password)
    with open(output_pdf, "wb") as f:
        writer.write(f)
