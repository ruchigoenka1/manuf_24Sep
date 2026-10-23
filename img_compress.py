import streamlit as st
from pypdf import PdfReader, PdfWriter
import io

st.set_page_config(page_title="PDF Compressor", page_icon="📄")

st.title("📄 PDF Compressor")
st.write("Upload a PDF file to reduce its file size by compressing internal content streams.")

uploaded_file = st.file_uploader("Choose a PDF file", type="pdf")

if uploaded_file is not None:
    # Get original file size in KB
    original_size = uploaded_file.size / 1024
    st.info(f"**Original File Size:** {original_size:.2f} KB")

    if st.button("Compress PDF"):
        with st.spinner("Compressing..."):
            try:
                # Read the uploaded PDF
                reader = PdfReader(uploaded_file)
                writer = PdfWriter()

                # Add pages and compress them
                for page in reader.pages:
                    writer.add_page(page)
                
                for page in writer.pages:
                    page.compress_content_streams()

                # Save to a bytes buffer
                output_pdf = io.BytesIO()
                writer.write(output_pdf)
                
                # Get compressed size in KB
                compressed_size = output_pdf.getbuffer().nbytes / 1024

                st.success("Compression Complete!")
                st.write(f"**Compressed File Size:** {compressed_size:.2f} KB")
                
                # Calculate reduction percentage
                if original_size > 0:
                    reduction = (1 - (compressed_size / original_size)) * 100
                    st.write(f"**Size reduced by:** {reduction:.2f}%")

                # Download button for the new PDF
                st.download_button(
                    label="⬇️ Download Compressed PDF",
                    data=output_pdf.getvalue(),
                    file_name=f"compressed_{uploaded_file.name}",
                    mime="application/pdf"
                )
                
            except Exception as e:
                st.error(f"An error occurred: {e}")
