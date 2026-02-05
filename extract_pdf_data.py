import re
import pdfplumber
import pandas as pd

TEST_PDF_PATH = "TEST.pdf"
ANSWER_PDF_PATH = "ANWSER.pdf"
OUTPUT_CSV_PATH = "test_with_answers.csv"

# Character maps for sub/superscripts
SUBSCRIPT_MAP = str.maketrans("0123456789", "₀₁₂₃₄₅₆₇₈₉")
SUPERSCRIPT_MAP = str.maketrans("0123456789+-", "⁰¹²³⁴⁵⁶⁷⁸⁹⁺⁻")

def extract_text_with_subscripts(pdf_path: str) -> str:
    """
    Extract text from PDF, preserving subscripts and superscripts 
    based on character size and vertical position.
    """
    full_text = []

    with pdfplumber.open(pdf_path) as pdf:
        for page in pdf.pages:
            # 1. Inspect all characters to determine the "mode" (dominant) font size
            chars = page.chars
            if not chars:
                full_text.append("")
                continue

            sizes = [c['size'] for c in chars]
            # Use a simple frequency count to find the mode size
            if sizes:
                mode_size = max(set(sizes), key=sizes.count)
            else:
                mode_size = 11.0  # Default fallback

            # 2. Sort characters by vertical position (top), then horizontal (x0)
            # Grouping by lines is tricky, but pdfplumber's extract_text does it well.
            # We will try to reconstruct lines manually.
            # Simple approach: Sort by 'top', then 'x0'. iterate and build string.
            # However, exact 'top' alignment varies. We need line grouping.
            
            # Use pdfplumber's internal utility if possible, or a simple clustering.
            # Let's use a tolerance for 'top' to group lines.
            
            sorted_chars = sorted(chars, key=lambda c: (c['top'], c['x0']))
            
            lines = []
            current_line_chars = []
            current_line_top = -1
            
            # Heuristic: if 'top' is within 50% of font size, consider same line
            # or simply use the previous char's implicit line bottom?
            # A common tolerance is mode_size * 0.5
            
            for char in sorted_chars:
                if current_line_top == -1:
                    current_line_top = char['top']
                    current_line_chars.append(char)
                else:
                    # Check if checks belong to a new line
                    # If vertical distance > threshold, new line.
                    # Note: characters on same line can have slightly diff 'top' (e.g. superscripts)
                    if abs(char['top'] - current_line_top) > (mode_size * 0.5):
                        lines.append(current_line_chars)
                        current_line_chars = [char]
                        current_line_top = char['top']
                    else:
                        current_line_chars.append(char)
                        # Re-average top? Or just keep first char's top? 
                        # Keep first char's top is usually fine for grouping.
            
            if current_line_chars:
                lines.append(current_line_chars)

            # 3. Process each line to detect sub/super
            page_content = []
            for line_chars in lines:
                # Sort line by x0 purely
                line_chars.sort(key=lambda c: c['x0'])
                
                line_str = ""
                prev_char = None
                
                for char in line_chars:
                    text = char['text']
                    
                    # Insert spaces if distant from prev char?
                    if prev_char:
                        dist = char['x0'] - prev_char['x1']
                        if dist > 2.0: # Arbitrary space width threshold
                             line_str += " "
                    
                    is_digit = text.isdigit() or text in "+-"
                    
                    # Logic: if significantly smaller than mode_size 
                    # AND vertical shift indicates sub/super
                    if is_digit and char['size'] < (mode_size * 0.85):
                        # Determine shift relative to neighbors.
                        # Using prev_char is best context.
                        if prev_char:
                            # Diff in 'bottom'
                            # Positive diff => char is lower (subscript, but usually diff is small negative for sub)
                            # Large Negative diff => char is higher (superscript)
                            # Based on inspection:
                            # Subscript (O2) shift ~ -1.10
                            # Superscript (m2) shift ~ -6.63
                            
                            diff = char['bottom'] - prev_char['bottom']
                            
                            # Threshold: -3.5 (midpoint between -1.1 and -6.6)
                            if diff < -3.5:
                                # Superscript
                                text = text.translate(SUPERSCRIPT_MAP)
                            else:
                                # Subscript
                                text = text.translate(SUBSCRIPT_MAP)
                        else:
                            # No prev char? assume subscript if default, or check 'top'?
                            # Rare to start line with subscript. Leave as is.
                            pass

                    line_str += text
                    prev_char = char
                
                page_content.append(line_str)
            
            full_text.append("\n".join(page_content))

    return "\n".join(full_text)

def extract_text(pdf_path: str) -> str:
    """Wrapper to choose extraction method based on file type."""
    if "TEST.pdf" in pdf_path:
        return extract_text_with_subscripts(pdf_path)
    
    # Fallback to standard extraction for other PDFs (like ANSWER.pdf)
    with pdfplumber.open(pdf_path) as pdf:
        pages = [(page.extract_text() or "") for page in pdf.pages]
    return "\n".join(pages)

def parse_answers(answer_pdf_text: str) -> dict[int, str]:
    """
    Parse ANWSER.pdf into {question_number: 'A'/'B'/'C'/'D'}.
    ANWSER.pdf uses fullwidth letters ＡＢＣＤ sometimes, so normalize first.
    """
    fw_map = str.maketrans({"Ａ": "A", "Ｂ": "B", "Ｃ": "C", "Ｄ": "D", "　": " "})
    norm = answer_pdf_text.translate(fw_map)

    # Grab answer tokens in order (1..80). The PDF contains answers as a sequence.
    tokens = re.findall(r"\b[ABCD]\b", norm)
    if len(tokens) < 80:
        # Fallback: allow letters not separated by spaces (rare layouts)
        tokens = re.findall(r"[ABCD]", norm)

    answers = tokens[:80]
    if len(answers) != 80:
        raise ValueError(f"Could not parse 80 answers. Got {len(answers)}")

    return {i + 1: answers[i] for i in range(80)}

def parse_questions(test_pdf_text: str, answer_map: dict[int, str]) -> pd.DataFrame:
    """
    Parse TEST.pdf questions into a dataframe with:
    number, Question, A, B, C, D, answer
    """
    text = test_pdf_text.replace("\r", "\n")

    # Capture blocks starting with "1." "2." ... until next "n." or end
    block_pat = re.compile(r"(?m)^\s*(\d{1,3})\.(.*?)(?=^\s*\d{1,3}\.|$\Z)", re.S)
    blocks = block_pat.findall(text)

    rows = []
    for num_str, body in blocks:
        n = int(num_str)
        if not (1 <= n <= 80):
            continue

        body = body.strip()

        # Find where options start (A.)
        mA = re.search(r"\n\s*A\.", body) or re.search(r"\sA\.", body)
        if not mA:
            continue

        q_text = body[:mA.start()].strip()
        opts_part = body[mA.start():].strip()

        # Extract options A/B/C/D; allow multiline option text
        opt_pat = re.compile(
            r"(?:^|\n)\s*([ABCD])\.\s*(.*?)(?=(?:\n\s*[ABCD]\.)|\Z)",
            re.S
        )
        opts = {k: re.sub(r"\s*\n\s*", " ", v).strip() for k, v in opt_pat.findall("\n" + opts_part)}
        for k in "ABCD":
            opts.setdefault(k, "")

        rows.append({
            "number": n,
            "Question": re.sub(r"\s*\n\s*", " ", q_text).strip(),
            "A": opts["A"],
            "B": opts["B"],
            "C": opts["C"],
            "D": opts["D"],
            "answer": answer_map.get(n, "")
        })

    df = pd.DataFrame(rows).sort_values("number").reset_index(drop=True)

    # Optional sanity check
    missing = sorted(set(range(1, 81)) - set(df["number"].tolist()))
    if missing:
        print("Warning: Missing question numbers:", missing)

    return df

# ... imports ...
import os

OUTPUT_EXCEL_PATH = "test_with_answers.xlsx"
FIGURE_DIR = "figures"

# ... (Previous helper functions like extract_text_with_subscripts, parse_answers) ...

def extract_image_metadata(pdf_path: str) -> list[dict]:
    """
    Extract metadata for all images in PDF.
    Returns list of {page_index, x0, top, x1, bottom}.
    Does NOT save images to disk yet.
    """
    image_metadata = []
    
    with pdfplumber.open(pdf_path) as pdf:
        for i, page in enumerate(pdf.pages):
            for img in page.images:
                 # Define bounding box for the image
                p_width = page.width
                p_height = page.height
                
                x0 = max(0, min(img['x0'], p_width))
                top = max(0, min(img['top'], p_height))
                x1 = max(0, min(img['x1'], p_width))
                bottom = max(0, min(img['bottom'], p_height))
                
                # Skip invalid boxes
                if x1 <= x0 or bottom <= top:
                    continue

                image_metadata.append({
                    "page_index": i,
                    "x0": x0,
                    "top": top,
                    "x1": x1,
                    "bottom": bottom
                })

    return image_metadata

def parse_questions_with_images(test_pdf_text: str, answer_map: dict[int, str], image_meta: list[dict], pdf_path: str) -> pd.DataFrame:
    """
    Parse questions and associate images.
    If multiple images fall within a question's range, merge them by taking the union bbox.
    """
    if not os.path.exists(FIGURE_DIR):
        os.makedirs(FIGURE_DIR)
        
    rows = []
    
    with pdfplumber.open(pdf_path) as pdf:
        for page_idx, page in enumerate(pdf.pages):
            # 1. Identify Question Locations
            text = page.extract_text() or ""
            words = page.extract_words()
            question_locs = []
            
            for w in words:
                # Match "78." or "1." at start of word
                m = re.match(r"^(\d{1,3})\.", w['text'])
                if m:
                    q_num = int(m.group(1))
                    if 1 <= q_num <= 80:
                        question_locs.append({
                            "number": q_num,
                            "top": w['top'],
                            "bottom": w['bottom'],
                            "page_index": page_idx
                        })
            
            question_locs.sort(key=lambda x: x['top'])
            
            # 2. Identify images on this page
            page_images = [img for img in image_meta if img['page_index'] == page_idx]
            
            # 3. Map images to questions
            for i, q in enumerate(question_locs):
                q_start = q['top']
                # Determine end of this question section
                if i < len(question_locs) - 1:
                    q_end = question_locs[i+1]['top']
                else:
                    q_end = 9999 # End of page
                
                # Find all images in this range
                # Image top should be > q_start (below question title)
                related_imgs = [
                    img for img in page_images 
                    if q_start < img['top'] < q_end
                ]
                
                figure_path = None
                
                if related_imgs:
                    # Calculate Union Bounding Box
                    min_x0 = min(img['x0'] for img in related_imgs)
                    min_top = min(img['top'] for img in related_imgs)
                    max_x1 = max(img['x1'] for img in related_imgs)
                    max_bottom = max(img['bottom'] for img in related_imgs)
                    
                    # Crop the full figure from the page
                    bbox = (min_x0, min_top, max_x1, max_bottom)
                    
                    try:
                        cropped_page = page.crop(bbox)
                        im = cropped_page.to_image(resolution=300)
                        
                        filename = f"q_{q['number']}_figure.png"
                        filepath = os.path.join(FIGURE_DIR, filename)
                        im.save(filepath, format="PNG")
                        figure_path = filepath
                        print(f"Saved merged figure for Q{q['number']} to {filepath}")
                    except Exception as e:
                        print(f"Failed to crop merged figure for Q{q['number']}: {e}")

                q['figure_path'] = figure_path
            
            rows.extend(question_locs)

    # Now we have a map: Question Number -> Figure Path
    q_to_fig = {r['number']: r.get('figure_path') for r in rows}
    
    # Use original robust text parsing to get texts
    full_text = extract_text_with_subscripts(pdf_path)
    df = parse_questions(full_text, answer_map)
    
    # Add Figure column
    df['Figure'] = df['number'].map(q_to_fig)
    
    # Reorder columns
    cols = ['number', 'Question', 'A', 'B', 'C', 'D', 'answer', 'Figure']
    for c in cols:
        if c not in df.columns:
            df[c] = None
    
    return df[cols]

def main():
    print("Extracting image metadata...")
    image_meta = extract_image_metadata(TEST_PDF_PATH)
    
    print("Extracting text and answers...")
    with pdfplumber.open(ANSWER_PDF_PATH) as pdf:
         ans_text = "\n".join([(page.extract_text() or "") for page in pdf.pages])

    answer_map = parse_answers(ans_text)
    
    print("Parsing questions and generating figures...")
    df = parse_questions_with_images(TEST_PDF_PATH, answer_map, image_meta, TEST_PDF_PATH)
    
    # Export to Excel with Images
    print(f"Writing to {OUTPUT_EXCEL_PATH}...")
    
    with pd.ExcelWriter(OUTPUT_EXCEL_PATH, engine='xlsxwriter') as writer:
        df.to_excel(writer, index=False, sheet_name='Sheet1')
        workbook = writer.book
        worksheet = writer.sheets['Sheet1']
        
        # Set column width for Figure
        worksheet.set_column('H:H', 50) 
        
        # Insert images
        for idx, row in df.iterrows():
            fig_path = row['Figure']
            if fig_path and isinstance(fig_path, str) and os.path.exists(fig_path):
                # Excel row index
                excel_row = idx + 1
                
                try:
                    # Get image dimensions to scale it properly
                    from PIL import Image
                    with Image.open(fig_path) as img:
                        width, height = img.size
                    
                    # Target cell size in pixels (approx)
                    # Width 50 chars ~ 350 pixels?
                    # Let's verify defaults. xlsxwriter col width 1 is ~7 pixels. 50 ~ 350px.
                    cell_width_px = 350
                    
                    # We want to scale image to fit width, or limit height
                    # Let's set a fixed max height for the row, e.g. 200px
                    max_row_height_px = 200
                    
                    # Calculate scale
                    scale_w = cell_width_px / width
                    scale_h = max_row_height_px / height
                    
                    # Use smaller scale to fit both dimensions
                    scale = min(scale_w, scale_h, 1.0) # Don't upscale if small
                    
                    # Set row height (units are points, 1 px approx 0.75 points)
                    # xlsxwriter set_row takes height in points.
                    # height in px * 0.75
                    row_height_points = (height * scale) * 0.75
                    # Add some padding
                    row_height_points += 10 
                    
                    worksheet.set_row(excel_row, row_height_points)
                    
                    # Insert with calculated scale
                    # position it with a small offset
                    worksheet.insert_image(excel_row, 7, fig_path, {
                        'x_scale': scale, 'y_scale': scale,
                        'x_offset': 5, 'y_offset': 5,
                        'object_position': 1 # Move and size with cells
                    })
                except Exception as e:
                    print(f"Warning: Could not insert image {fig_path}: {e}")
                
    print(f"Done! Wrote {len(df)} rows to {OUTPUT_EXCEL_PATH}")

if __name__ == "__main__":
    main()
