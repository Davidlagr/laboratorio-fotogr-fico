import io
import math
import base64
import streamlit as st
import streamlit.components.v1 as components
from PIL import Image, ImageOps, ImageDraw, ImageEnhance

st.set_page_config(
    page_title="Estudio de Impresión Fotográfica & Póster",
    page_icon="📸",
    layout="wide",
)

# Tamaños fotográficos estándar en centímetros (Ancho x Alto)
PHOTO_SIZES_CM = {
    "9 x 13 cm (3.5 x 5 in)": (9.0, 13.0),
    "10 x 15 cm (4 x 6 in - Estándar)": (10.16, 15.24),
    "13 x 18 cm (5 x 7 in)": (12.7, 17.78),
    "15 x 20 cm (6 x 8 in)": (15.24, 20.32),
    "20 x 25 cm (8 x 10 in)": (20.32, 25.4),
    "20 x 30 cm (8 x 12 in / A4 aprox)": (20.32, 30.48),
    "Carta (21.6 x 27.9 cm)": (21.59, 27.94),
    "A4 (21.0 x 29.7 cm)": (21.0, 29.7),
    "30 x 40 cm (Póster Pequeño)": (30.0, 40.0),
    "30 x 45 cm (12 x 18 in)": (30.48, 45.72),
    "40 x 60 cm (Póster Mediano)": (40.0, 60.0),
    "50 x 70 cm (Póster Grande)": (50.0, 70.0),
    "60 x 90 cm (Póster Extra Grande)": (60.0, 90.0),
}

# Perfiles de papel fotográfico
PAPER_PROFILES = {
    "Papel Fotográfico Brillante (Glossy)": {
        "sharpness": 1.12,
        "contrast": 1.05,
        "brightness": 1.0,
        "tip": "En el cuadro de impresión elige: Tipo de papel → Papel Fotográfico Brillante (Photo Paper Plus Glossy II).",
    },
    "Papel Fotográfico Mate (Matte)": {
        "sharpness": 1.18,
        "contrast": 1.08,
        "brightness": 1.04,
        "tip": "En el cuadro de impresión elige: Tipo de papel → Papel Fotográfico Mate (Matte Photo Paper).",
    },
    "Papel Fotográfico Satinado / Semi-Brillante": {
        "sharpness": 1.10,
        "contrast": 1.03,
        "brightness": 1.02,
        "tip": "En el cuadro de impresión elige: Tipo de papel → Papel Fotográfico Semi-brillante / Satinado.",
    },
    "Papel Normal / Opalina (Borrador o Prueba)": {
        "sharpness": 1.0,
        "contrast": 1.0,
        "brightness": 1.0,
        "tip": "En el cuadro de impresión elige: Tipo de papel → Papel Normal.",
    },
}

# Perfiles de calidad de impresión (DPI reales)
QUALITY_PROFILES = {
    "Máxima / Laboratorio (300 DPI - Alta calidad)": 300,
    "Estándar / Rápida (200 DPI - Uso diario)": 200,
    "Borrador / Prueba de encuadre (150 DPI)": 150,
}

# Opciones de rotación manual
ROTATION_OPTIONS = {
    "0° (Original)": 0,
    "90° Derecha (Horario)": -90,
    "90° Izquierda (Antihorario)": 90,
    "180° (Invertida)": 180,
}


def cm_to_px(cm: float, dpi: int) -> int:
    return int(round((cm / 2.54) * dpi))


def load_image_corrected(uploaded_file) -> Image.Image:
    """Carga la imagen corrigiendo la orientación EXIF y convirtiendo a RGB."""
    img = Image.open(uploaded_file)
    img = ImageOps.exif_transpose(img)
    if img.mode in ("RGBA", "P"):
        background = Image.new("RGB", img.size, (255, 255, 255))
        if img.mode == "P":
            img = img.convert("RGBA")
        background.paste(img, mask=img.split()[3])
        return background
    return img.convert("RGB")


def apply_rotation(
    img: Image.Image,
    global_mode: str,
    individual_deg: int,
    target_vertical: bool = True,
) -> Image.Image:
    """
    Aplica rotación inteligente para impresión vertical o ángulos manuales
    (global + individual por foto).
    """
    out = img
    if global_mode == "Auto-girar horizontales a Vertical (90° Derecha)":
        if target_vertical and out.width > out.height:
            out = out.rotate(-90, expand=True)
    elif global_mode == "Auto-girar horizontales a Vertical (90° Izquierda)":
        if target_vertical and out.width > out.height:
            out = out.rotate(90, expand=True)
    elif global_mode in ROTATION_OPTIONS:
        deg = ROTATION_OPTIONS[global_mode]
        if deg != 0:
            out = out.rotate(deg, expand=True)

    if individual_deg != 0:
        out = out.rotate(individual_deg, expand=True)

    return out


def apply_paper_optimization(img: Image.Image, paper_name: str) -> Image.Image:
    """Ajusta nitidez, contraste y brillo según la absorción de tinta del papel seleccionado."""
    profile = PAPER_PROFILES[paper_name]
    out = img
    if profile["brightness"] != 1.0:
        out = ImageEnhance.Brightness(out).enhance(profile["brightness"])
    if profile["contrast"] != 1.0:
        out = ImageEnhance.Contrast(out).enhance(profile["contrast"])
    if profile["sharpness"] != 1.0:
        out = ImageEnhance.Sharpness(out).enhance(profile["sharpness"])
    return out


def process_single_photo(
    img: Image.Image,
    target_w_px: int,
    target_h_px: int,
    fit_mode: str,
    auto_rotate_paper: bool,
    bg_color: tuple = (255, 255, 255),
    inner_margin_px: int = 0,
) -> Image.Image:
    """Ajusta una fotografía a las dimensiones exactas en píxeles."""
    if auto_rotate_paper:
        img_is_landscape = img.width > img.height
        target_is_landscape = target_w_px > target_h_px
        if img_is_landscape != target_is_landscape:
            target_w_px, target_h_px = target_h_px, target_w_px

    canvas = Image.new("RGB", (target_w_px, target_h_px), bg_color)

    work_w = max(10, target_w_px - 2 * inner_margin_px)
    work_h = max(10, target_h_px - 2 * inner_margin_px)

    if fit_mode == "Rellenar (Recortar bordes para cubrir todo el papel)":
        processed = ImageOps.fit(
            img, (work_w, work_h), method=Image.Resampling.LANCZOS, centering=(0.5, 0.5)
        )
        canvas.paste(processed, (inner_margin_px, inner_margin_px))
    else:
        processed = ImageOps.contain(
            img, (work_w, work_h), method=Image.Resampling.LANCZOS
        )
        offset_x = (target_w_px - processed.width) // 2
        offset_y = (target_h_px - processed.height) // 2
        canvas.paste(processed, (offset_x, offset_y))

    return canvas


def build_poster_collage(
    images: list,
    poster_w_px: int,
    poster_h_px: int,
    cols: int,
    rows: int,
    margin_px: int,
    gap_px: int,
    bg_color: tuple,
    cell_fit_mode: str,
) -> Image.Image:
    """Crea un póster fotográfico distribuyendo múltiples fotos en una cuadrícula."""
    poster = Image.new("RGB", (poster_w_px, poster_h_px), bg_color)

    usable_w = poster_w_px - (2 * margin_px) - ((cols - 1) * gap_px)
    usable_h = poster_h_px - (2 * margin_px) - ((rows - 1) * gap_px)

    cell_w = max(20, usable_w // cols)
    cell_h = max(20, usable_h // rows)

    total_cells = cols * rows
    for idx in range(min(len(images), total_cells)):
        r = idx // cols
        c = idx % cols

        x = margin_px + c * (cell_w + gap_px)
        y = margin_px + r * (cell_h + gap_px)

        img = images[idx]
        if cell_fit_mode == "Recortar para llenar cada cuadro":
            cell_img = ImageOps.fit(
                img, (cell_w, cell_h), method=Image.Resampling.LANCZOS, centering=(0.5, 0.5)
            )
            poster.paste(cell_img, (x, y))
        else:
            cell_img = ImageOps.contain(
                img, (cell_w, cell_h), method=Image.Resampling.LANCZOS
            )
            ox = x + (cell_w - cell_img.width) // 2
            oy = y + (cell_h - cell_img.height) // 2
            poster.paste(cell_img, (ox, oy))

    return poster


def build_multi_print_sheet(
    processed_photos: list,
    sheet_w_px: int,
    sheet_h_px: int,
    photo_w_px: int,
    photo_h_px: int,
    gap_px: int,
    dpi: int,
    draw_cut_guides: bool = True,
) -> list:
    """Acomoda múltiples fotos dentro de hojas Carta o A4 para ahorrar papel."""
    sheets = []
    margin_px = cm_to_px(0.5, dpi)

    cols = max(1, (sheet_w_px - 2 * margin_px + gap_px) // (photo_w_px + gap_px))
    rows = max(1, (sheet_h_px - 2 * margin_px + gap_px) // (photo_h_px + gap_px))
    per_sheet = cols * rows

    for page_start in range(0, len(processed_photos), per_sheet):
        sheet = Image.new("RGB", (sheet_w_px, sheet_h_px), (255, 255, 255))
        draw = ImageDraw.Draw(sheet)
        batch = processed_photos[page_start : page_start + per_sheet]

        for idx, photo in enumerate(batch):
            r = idx // cols
            c = idx % cols
            x = margin_px + c * (photo_w_px + gap_px)
            y = margin_px + r * (photo_h_px + gap_px)
            sheet.paste(photo, (x, y))

            if draw_cut_guides:
                draw.rectangle(
                    [x - 1, y - 1, x + photo_w_px, y + photo_h_px],
                    outline=(180, 180, 180),
                    width=2,
                )

        sheets.append(sheet)
    return sheets


def export_image_bytes(img: Image.Image, dpi: int, fmt: str = "JPEG") -> bytes:
    buf = io.BytesIO()
    if fmt.upper() == "PDF":
        img.save(buf, format="PDF", resolution=float(dpi))
    else:
        img.save(buf, format="JPEG", quality=95, subsampling=0, dpi=(dpi, dpi))
    return buf.getvalue()


def trigger_direct_browser_print(images_list: list, page_w_cm: float, page_h_cm: float, dpi: int):
    """
    Inyecta un iframe oculto con reglas CSS @page calibradas al tamaño físico del papel
    y abre automáticamente el cuadro de diálogo de impresión del sistema operativo.
    """
    img_tags = []
    for img in images_list:
        raw_bytes = export_image_bytes(img, dpi=dpi, fmt="JPEG")
        b64 = base64.b64encode(raw_bytes).decode("utf-8")
        is_land = img.width > img.height
        w_page = max(page_w_cm, page_h_cm) if is_land else min(page_w_cm, page_h_cm)
        h_page = min(page_w_cm, page_h_cm) if is_land else max(page_w_cm, page_h_cm)
        img_tags.append(
            f'<div class="print-page" style="width:{w_page}cm; height:{h_page}cm;">'
            f'<img src="data:image/jpeg;base64,{b64}" />'
            f"</div>"
        )

    pages_html = "\n".join(img_tags)

    print_html = f"""
    <!DOCTYPE html>
    <html>
    <head>
    <style>
        @page {{
            size: {page_w_cm}cm {page_h_cm}cm;
            margin: 0mm;
        }}
        html, body {{
            margin: 0;
            padding: 0;
            background: white;
        }}
        .print-page {{
            page-break-after: always;
            break-after: page;
            display: flex;
            align-items: center;
            justify-content: center;
            overflow: hidden;
            margin: 0;
            padding: 0;
        }}
        .print-page:last-child {{
            page-break-after: auto;
            break-after: auto;
        }}
        img {{
            width: 100%;
            height: 100%;
            object-fit: contain;
            display: block;
        }}
    </style>
    </head>
    <body>
        {pages_html}
        <script>
            window.onload = function() {{
                setTimeout(function() {{
                    window.focus();
                    window.print();
                }}, 350);
            }};
        </script>
    </body>
    </html>
    """
    components.html(print_html, height=0, width=0)


# --- INTERFAZ DE USUARIO ---
st.title("📸 Estudio de Impresión Fotográfica y Póster")
st.markdown(
    "Ajusta tus fotos a tamaños estándar, **rótalas para impresión vertical**, calibra el **papel y calidad**, e **imprime directamente**."
)

tab1, tab2 = st.tabs(["🖨️ Ajustar e Imprimir Fotos", "🧩 Crear e Imprimir Póster"])

# ==========================================
# PESTAÑA 1: IMPRESIÓN DE FOTOS ESTÁNDAR
# ==========================================
with tab1:
    col_cfg, col_prev = st.columns([1, 1.4], gap="large")

    with col_cfg:
        st.subheader("1. Sube tus fotografías")
        uploaded_photos = st.file_uploader(
            "Selecciona una o varias imágenes (JPG, PNG, WEBP)",
            type=["jpg", "jpeg", "png", "webp"],
            accept_multiple_files=True,
            key="uploader_std",
        )

        st.subheader("2. Papel, Calidad y Tamaño")
        paper_choice_1 = st.selectbox(
            "Tipo de papel fotográfico",
            options=list(PAPER_PROFILES.keys()),
            index=0,
            key="paper_1",
        )
        quality_choice_1 = st.selectbox(
            "Calidad de impresión",
            options=list(QUALITY_PROFILES.keys()),
            index=0,
            key="qual_1",
        )
        selected_dpi_1 = QUALITY_PROFILES[quality_choice_1]

        size_label = st.selectbox(
            "Tamaño de fotografía",
            options=list(PHOTO_SIZES_CM.keys())[:8],
            index=1,  # 10 x 15 cm por defecto
        )
        orientation = st.radio(
            "Orientación del papel",
            [
                "Vertical (Retrato - Fijo)",
                "Horizontal (Paisaje - Fijo)",
                "Automática (según cada foto)",
            ],
            index=0,
        )

        st.subheader("3. Rotación de Fotografías")
        global_rot_1 = st.selectbox(
            "Rotación general para encuadre",
            options=[
                "0° (Original)",
                "Auto-girar horizontales a Vertical (90° Derecha)",
                "Auto-girar horizontales a Vertical (90° Izquierda)",
                "90° Derecha (Horario)",
                "90° Izquierda (Antihorario)",
                "180° (Invertida)",
            ],
            index=0,
            help="Usa 'Auto-girar horizontales a Vertical' para rotar automáticamente fotos apaisadas y aprovechar toda la hoja vertical.",
        )

        fit_mode = st.radio(
            "Modo de ajuste",
            [
                "Rellenar (Recortar bordes para cubrir todo el papel)",
                "Ajustar completa (Sin recortar, con bordes blancos)",
            ],
        )
        border_mm = st.slider("Margen blanco interior (mm)", 0, 15, 0)

        st.subheader("4. Ahorro de Papel (Opcional)")
        pack_on_sheet = st.checkbox(
            "Agrupar varias fotos en hoja Carta o A4",
            value=False,
        )
        if pack_on_sheet:
            sheet_type = st.selectbox(
                "Tamaño de hoja de impresora",
                ["Carta (21.6 x 27.9 cm)", "A4 (21.0 x 29.7 cm)"],
            )
            cut_guides = st.checkbox("Dibujar líneas guía de corte", value=True)

    with col_prev:
        st.subheader("Vista Previa, Ajuste Individual e Impresión")
        if uploaded_photos:
            w_cm, h_cm = PHOTO_SIZES_CM[size_label]
            if "Horizontal" in orientation:
                w_cm, h_cm = max(w_cm, h_cm), min(w_cm, h_cm)
            elif "Vertical" in orientation:
                w_cm, h_cm = min(w_cm, h_cm), max(w_cm, h_cm)

            target_w = cm_to_px(w_cm, selected_dpi_1)
            target_h = cm_to_px(h_cm, selected_dpi_1)
            auto_rot_paper = "Automática" in orientation
            is_target_vertical = "Vertical" in orientation

            # Controles de rotación individual por foto
            indiv_rotations_1 = []
            with st.expander("🔄 Rotar fotos individualmente (opcional)", expanded=len(uploaded_photos) == 1):
                rot_cols = st.columns(min(3, len(uploaded_photos)))
                for idx, up in enumerate(uploaded_photos):
                    with rot_cols[idx % 3]:
                        r_choice = st.selectbox(
                            f"Girar: {up.name[:18]}",
                            options=list(ROTATION_OPTIONS.keys()),
                            key=f"rot_std_{idx}_{up.name}",
                        )
                        indiv_rotations_1.append(ROTATION_OPTIONS[r_choice])

            processed_list = []
            for idx, up in enumerate(uploaded_photos):
                raw_img = load_image_corrected(up)
                rot_img = apply_rotation(
                    raw_img,
                    global_mode=global_rot_1,
                    individual_deg=indiv_rotations_1[idx],
                    target_vertical=is_target_vertical,
                )
                opt_img = apply_paper_optimization(rot_img, paper_choice_1)
                proc = process_single_photo(
                    opt_img,
                    target_w,
                    target_h,
                    fit_mode=fit_mode,
                    auto_rotate_paper=auto_rot_paper,
                    inner_margin_px=cm_to_px(border_mm / 10.0, selected_dpi_1),
                )
                processed_list.append((up.name, proc))

            if pack_on_sheet:
                sw_cm, sh_cm = PHOTO_SIZES_CM[sheet_type]
                fixed_photos = [x[1] for x in processed_list]
                final_pages = build_multi_print_sheet(
                    fixed_photos,
                    cm_to_px(sw_cm, selected_dpi_1),
                    cm_to_px(sh_cm, selected_dpi_1),
                    target_w,
                    target_h,
                    gap_px=cm_to_px(0.3, selected_dpi_1),
                    dpi=selected_dpi_1,
                    draw_cut_guides=cut_guides,
                )
                print_w_cm, print_h_cm = sw_cm, sh_cm
                st.info(f"Se prepararon **{len(final_pages)} hoja(s)** tamaño {sheet_type} a **{selected_dpi_1} DPI**.")
                st.image(final_pages[0], caption="Vista previa Hoja 1", use_container_width=True)
            else:
                final_pages = [x[1] for x in processed_list]
                print_w_cm, print_h_cm = w_cm, h_cm
                prev_cols = st.columns(min(3, len(processed_list)))
                for idx, (fname, pimg) in enumerate(processed_list):
                    with prev_cols[idx % 3]:
                        st.image(
                            pimg,
                            caption=f"{fname} ({pimg.width}x{pimg.height} px)",
                            use_container_width=True,
                        )

            st.caption(f"💡 **Ajuste recomendado en tu impresora:** {PAPER_PROFILES[paper_choice_1]['tip']}")

            btn_col1, btn_col2 = st.columns(2)
            with btn_col1:
                if st.button("🖨️ Imprimir Directamente Ahora", type="primary", use_container_width=True, key="btn_print_1"):
                    trigger_direct_browser_print(final_pages, print_w_cm, print_h_cm, selected_dpi_1)

            with btn_col2:
                if len(final_pages) == 1:
                    st.download_button(
                        f"⬇️ Descargar JPG ({selected_dpi_1} DPI)",
                        data=export_image_bytes(final_pages[0], selected_dpi_1, "JPEG"),
                        file_name=f"foto_{print_w_cm:.0f}x{print_h_cm:.0f}cm_{selected_dpi_1}dpi.jpg",
                        mime="image/jpeg",
                        use_container_width=True,
                    )
                else:
                    pdf_buf = io.BytesIO()
                    final_pages[0].save(
                        pdf_buf,
                        format="PDF",
                        resolution=float(selected_dpi_1),
                        save_all=True,
                        append_images=final_pages[1:],
                    )
                    st.download_button(
                        f"⬇️ Descargar PDF ({len(final_pages)} págs)",
                        data=pdf_buf.getvalue(),
                        file_name=f"lote_fotos_{selected_dpi_1}dpi.pdf",
                        mime="application/pdf",
                        use_container_width=True,
                    )
        else:
            st.info("👈 Sube una o varias fotografías en el panel izquierdo para comenzar.")

# ==========================================
# PESTAÑA 2: CREAR PÓSTER FOTOGRÁFICO
# ==========================================
with tab2:
    p_col_cfg, p_col_prev = st.columns([1, 1.5], gap="large")

    with p_col_cfg:
        st.subheader("1. Selecciona las fotos del Póster")
        poster_files = st.file_uploader(
            "Sube las fotos que formarán el póster (en orden)",
            type=["jpg", "jpeg", "png", "webp"],
            accept_multiple_files=True,
            key="uploader_poster",
        )

        st.subheader("2. Papel, Calidad y Tamaño")
        paper_choice_2 = st.selectbox(
            "Tipo de papel del póster",
            options=list(PAPER_PROFILES.keys()),
            index=0,
            key="paper_2",
        )
        quality_choice_2 = st.selectbox(
            "Calidad / Resolución de salida",
            options=list(QUALITY_PROFILES.keys()),
            index=0,
            key="qual_2",
        )
        selected_dpi_2 = QUALITY_PROFILES[quality_choice_2]

        poster_size_label = st.selectbox(
            "Dimensiones finales del póster",
            options=list(PHOTO_SIZES_CM.keys())[4:],
            index=4,  # 30 x 40 cm por defecto
        )
        poster_orient = st.radio(
            "Orientación del Póster",
            ["Vertical", "Horizontal"],
            key="poster_orient",
        )

        global_rot_2 = st.selectbox(
            "Rotación general de las fotos",
            options=[
                "0° (Original)",
                "Auto-girar horizontales a Vertical (90° Derecha)",
                "Auto-girar horizontales a Vertical (90° Izquierda)",
                "90° Derecha (Horario)",
                "90° Izquierda (Antihorario)",
                "180° (Invertida)",
            ],
            index=0,
            key="global_rot_2",
        )

        st.subheader("3. Diseño y Cuadrícula")
        num_imgs = len(poster_files) if poster_files else 4
        default_cols = max(1, int(math.sqrt(num_imgs)))
        default_rows = max(1, math.ceil(num_imgs / default_cols))

        c1, c2 = st.columns(2)
        with c1:
            grid_cols = st.number_input("Columnas", min_value=1, max_value=12, value=default_cols)
        with c2:
            grid_rows = st.number_input("Filas", min_value=1, max_value=12, value=default_rows)

        poster_margin_mm = st.slider("Margen exterior del póster (mm)", 0, 50, 15)
        poster_gap_mm = st.slider("Separación entre fotos (mm)", 0, 30, 5)
        bg_hex = st.color_picker("Color de fondo / bordes", "#FFFFFF")
        bg_rgb = tuple(int(bg_hex.lstrip("#")[i : i + 2], 16) for i in (0, 2, 4))

        cell_fit = st.radio(
            "Ajuste dentro de cada celda",
            ["Recortar para llenar cada cuadro", "Mostrar foto completa sin recortar"],
        )

    with p_col_prev:
        st.subheader("Vista Previa e Impresión del Póster")
        if poster_files:
            pw_cm, ph_cm = PHOTO_SIZES_CM[poster_size_label]
            if poster_orient == "Horizontal":
                pw_cm, ph_cm = max(pw_cm, ph_cm), min(pw_cm, ph_cm)
            else:
                pw_cm, ph_cm = min(pw_cm, ph_cm), max(pw_cm, ph_cm)

            pw_px = cm_to_px(pw_cm, selected_dpi_2)
            ph_px = cm_to_px(ph_cm, selected_dpi_2)

            # Controles de rotación individual por foto en el póster
            indiv_rotations_2 = []
            with st.expander("🔄 Rotar fotos individuales del póster (opcional)", expanded=False):
                p_rot_cols = st.columns(min(3, len(poster_files)))
                for idx, pf in enumerate(poster_files):
                    with p_rot_cols[idx % 3]:
                        r_choice_p = st.selectbox(
                            f"Foto #{idx + 1}: {pf.name[:14]}",
                            options=list(ROTATION_OPTIONS.keys()),
                            key=f"rot_poster_{idx}_{pf.name}",
                        )
                        indiv_rotations_2.append(ROTATION_OPTIONS[r_choice_p])

            loaded_poster_imgs = []
            for idx, f in enumerate(poster_files):
                raw_p = load_image_corrected(f)
                rot_p = apply_rotation(
                    raw_p,
                    global_mode=global_rot_2,
                    individual_deg=indiv_rotations_2[idx],
                    target_vertical=(poster_orient == "Vertical"),
                )
                opt_p = apply_paper_optimization(rot_p, paper_choice_2)
                loaded_poster_imgs.append(opt_p)

            capacity = grid_cols * grid_rows
            if len(loaded_poster_imgs) > capacity:
                st.warning(
                    f"Subiste {len(loaded_poster_imgs)} fotos, pero la cuadrícula de {grid_cols}x{grid_rows} solo tiene espacio para {capacity}. Aumenta filas o columnas."
                )

            poster_img = build_poster_collage(
                images=loaded_poster_imgs,
                poster_w_px=pw_px,
                poster_h_px=ph_px,
                cols=grid_cols,
                rows=grid_rows,
                margin_px=cm_to_px(poster_margin_mm / 10.0, selected_dpi_2),
                gap_px=cm_to_px(poster_gap_mm / 10.0, selected_dpi_2),
                bg_color=bg_rgb,
                cell_fit_mode=cell_fit,
            )

            preview_copy = poster_img.copy()
            preview_copy.thumbnail((1400, 1400), Image.Resampling.LANCZOS)
            st.image(
                preview_copy,
                caption=f"Póster {pw_cm:.0f} x {ph_cm:.0f} cm | {pw_px} x {ph_px} px ({selected_dpi_2} DPI)",
                use_container_width=True,
            )

            st.caption(f"💡 **Ajuste recomendado en tu impresora:** {PAPER_PROFILES[paper_choice_2]['tip']}")

            p_btn1, p_btn2, p_btn3 = st.columns(3)
            with p_btn1:
                if st.button("🖨️ Imprimir Póster Ahora", type="primary", use_container_width=True, key="btn_print_poster"):
                    trigger_direct_browser_print([poster_img], pw_cm, ph_cm, selected_dpi_2)
            with p_btn2:
                st.download_button(
                    "⬇️ Descargar JPG",
                    data=export_image_bytes(poster_img, selected_dpi_2, "JPEG"),
                    file_name=f"poster_{pw_cm:.0f}x{ph_cm:.0f}cm_{selected_dpi_2}dpi.jpg",
                    mime="image/jpeg",
                    use_container_width=True,
                )
            with p_btn3:
                st.download_button(
                    "⬇️ Descargar PDF",
                    data=export_image_bytes(poster_img, selected_dpi_2, "PDF"),
                    file_name=f"poster_{pw_cm:.0f}x{ph_cm:.0f}cm_{selected_dpi_2}dpi.pdf",
                    mime="application/pdf",
                    use_container_width=True,
                )
        else:
            st.info("👈 Selecciona varias fotografías en el panel izquierdo para armar tu póster.")
