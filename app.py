import io
import math
import zipfile
import streamlit as st
from PIL import Image, ImageOps, ImageDraw

# Configuración de página
st.set_page_config(
    page_title="Estudio de Impresión Fotográfica & Póster",
    page_icon="📸",
    layout="wide",
)

# Diccionario de tamaños fotográficos estándar en centímetros (Ancho x Alto)
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

DPI = 300  # Resolución estándar de impresión fotográfica


def cm_to_px(cm: float, dpi: int = DPI) -> int:
    return int(round((cm / 2.54) * dpi))


def load_image_corrected(uploaded_file) -> Image.Image:
    """Carga la imagen corrigiendo la orientación EXIF (fotos de celular) y convirtiendo a RGB."""
    img = Image.open(uploaded_file)
    img = ImageOps.exif_transpose(img)
    if img.mode in ("RGBA", "P"):
        background = Image.new("RGB", img.size, (255, 255, 255))
        if img.mode == "P":
            img = img.convert("RGBA")
        background.paste(img, mask=img.split()[3])
        return background
    return img.convert("RGB")


def process_single_photo(
    img: Image.Image,
    target_w_px: int,
    target_h_px: int,
    fit_mode: str,
    auto_rotate: bool,
    bg_color: tuple = (255, 255, 255),
    inner_margin_px: int = 0,
) -> Image.Image:
    """Ajusta una fotografía a las dimensiones exactas en píxeles a 300 DPI."""
    # Rotación automática si la orientación de la foto no coincide con el papel
    if auto_rotate:
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
        # Ajustar sin recortar (mantiene foto completa y deja margen blanco/color)
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
    draw_cut_guides: bool = True,
) -> list:
    """Acomoda múltiples fotos de tamaño estándar dentro de hojas Carta o A4 para ahorrar papel."""
    sheets = []
    margin_px = cm_to_px(0.5)  # 5mm margen exterior

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


def export_image_bytes(img: Image.Image, fmt: str = "JPEG") -> bytes:
    buf = io.BytesIO()
    if fmt.upper() == "PDF":
        img.save(buf, format="PDF", resolution=float(DPI))
    else:
        img.save(buf, format="JPEG", quality=95, subsampling=0, dpi=(DPI, DPI))
    return buf.getvalue()


# --- INTERFAZ DE USUARIO ---
st.title("📸 Estudio de Impresión Fotográfica y Póster")
st.markdown(
    "Prepara tus fotografías a **300 DPI** en tamaños estándar de laboratorio o diseña **pósteres fotográficos** listos para imprimir."
)

tab1, tab2 = st.tabs(["🖼️ Ajustar Fotos para Impresión", "🧩 Crear Póster Fotográfico"])

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

        st.subheader("2. Configuración de Tamaño")
        size_label = st.selectbox(
            "Tamaño de fotografía deseado",
            options=list(PHOTO_SIZES_CM.keys())[:8],
            index=1,  # 10 x 15 cm por defecto
        )
        orientation = st.radio(
            "Orientación del papel",
            ["Automática (según cada foto)", "Vertical (Retrato)", "Horizontal (Paisaje)"],
        )
        fit_mode = st.radio(
            "Modo de ajuste",
            [
                "Rellenar (Recortar bordes para cubrir todo el papel)",
                "Ajustar completa (Sin recortar, con bordes blancos)",
            ],
        )
        border_mm = st.slider("Margen blanco interior (mm)", 0, 15, 0)

        st.subheader("3. Ahorro de Papel (Opcional)")
        pack_on_sheet = st.checkbox(
            "Agrupar varias fotos en hoja Carta o A4 para imprimir en casa",
            value=False,
        )
        if pack_on_sheet:
            sheet_type = st.selectbox(
                "Tamaño de hoja de impresora",
                ["Carta (21.6 x 27.9 cm)", "A4 (21.0 x 29.7 cm)"],
            )
            cut_guides = st.checkbox("Dibujar líneas guía de corte", value=True)

        export_fmt_1 = st.selectbox("Formato de descarga", ["JPEG (300 DPI)", "PDF (Listo para imprimir)"])

    with col_prev:
        st.subheader("Vista Previa y Descarga")
        if uploaded_photos:
            w_cm, h_cm = PHOTO_SIZES_CM[size_label]
            if orientation == "Horizontal (Paisaje)":
                w_cm, h_cm = max(w_cm, h_cm), min(w_cm, h_cm)
            elif orientation == "Vertical (Retrato)":
                w_cm, h_cm = min(w_cm, h_cm), max(w_cm, h_cm)

            target_w = cm_to_px(w_cm)
            target_h = cm_to_px(h_cm)
            auto_rot = orientation == "Automática (según cada foto)"

            processed_list = []
            for up in uploaded_photos:
                raw_img = load_image_corrected(up)
                proc = process_single_photo(
                    raw_img,
                    target_w,
                    target_h,
                    fit_mode=fit_mode,
                    auto_rotate=auto_rot,
                    inner_margin_px=cm_to_px(border_mm / 10.0),
                )
                processed_list.append((up.name, proc))

            fmt_code = "PDF" if "PDF" in export_fmt_1 else "JPEG"
            ext = "pdf" if fmt_code == "PDF" else "jpg"

            if pack_on_sheet:
                sw_cm, sh_cm = PHOTO_SIZES_CM[sheet_type]
                # Para agrupar usamos orientación fija de cada foto
                fixed_photos = [
                    process_single_photo(
                        load_image_corrected(up),
                        target_w,
                        target_h,
                        fit_mode=fit_mode,
                        auto_rotate=False,
                        inner_margin_px=cm_to_px(border_mm / 10.0),
                    )
                    for up in uploaded_photos
                ]
                sheets = build_multi_print_sheet(
                    fixed_photos,
                    cm_to_px(sw_cm),
                    cm_to_px(sh_cm),
                    target_w,
                    target_h,
                    gap_px=cm_to_px(0.3),
                    draw_cut_guides=cut_guides,
                )
                st.info(f"Se generaron **{len(sheets)} hoja(s)** tamaño {sheet_type} con tus fotos acomodadas.")
                st.image(sheets[0], caption="Vista previa Hoja 1", use_container_width=True)

                if fmt_code == "PDF":
                    pdf_buf = io.BytesIO()
                    sheets[0].save(
                        pdf_buf,
                        format="PDF",
                        resolution=float(DPI),
                        save_all=True,
                        append_images=sheets[1:],
                    )
                    st.download_button(
                        "⬇️ Descargar Hojas en PDF",
                        data=pdf_buf.getvalue(),
                        file_name="hojas_fotograficas.pdf",
                        mime="application/pdf",
                        use_container_width=True,
                    )
                else:
                    zip_buf = io.BytesIO()
                    with zipfile.ZipFile(zip_buf, "w") as zf:
                        for i, sh in enumerate(sheets, 1):
                            zf.writestr(f"hoja_{i}.jpg", export_image_bytes(sh, "JPEG"))
                    st.download_button(
                        "⬇️ Descargar Hojas en ZIP (JPG 300 DPI)",
                        data=zip_buf.getvalue(),
                        file_name="hojas_fotograficas.zip",
                        mime="application/zip",
                        use_container_width=True,
                    )
            else:
                # Mostrar vista previa en cuadrícula
                prev_cols = st.columns(min(3, len(processed_list)))
                for idx, (fname, pimg) in enumerate(processed_list):
                    with prev_cols[idx % 3]:
                        st.image(
                            pimg,
                            caption=f"{fname} ({pimg.width}x{pimg.height} px)",
                            use_container_width=True,
                        )

                if len(processed_list) == 1:
                    fname, single_img = processed_list[0]
                    base_name = fname.rsplit(".", 1)[0]
                    st.download_button(
                        f"⬇️ Descargar Foto Ajustada ({ext.upper()})",
                        data=export_image_bytes(single_img, fmt_code),
                        file_name=f"{base_name}_{w_cm:.0f}x{h_cm:.0f}cm.{ext}",
                        mime="application/pdf" if fmt_code == "PDF" else "image/jpeg",
                        use_container_width=True,
                    )
                else:
                    if fmt_code == "PDF":
                        pdf_buf = io.BytesIO()
                        imgs_only = [x[1] for x in processed_list]
                        imgs_only[0].save(
                            pdf_buf,
                            format="PDF",
                            resolution=float(DPI),
                            save_all=True,
                            append_images=imgs_only[1:],
                        )
                        st.download_button(
                            "⬇️ Descargar Todas las Fotos en 1 PDF",
                            data=pdf_buf.getvalue(),
                            file_name=f"fotos_{w_cm:.0f}x{h_cm:.0f}cm.pdf",
                            mime="application/pdf",
                            use_container_width=True,
                        )
                    else:
                        zip_buf = io.BytesIO()
                        with zipfile.ZipFile(zip_buf, "w") as zf:
                            for idx, (fname, pimg) in enumerate(processed_list, 1):
                                base_name = fname.rsplit(".", 1)[0]
                                zf.writestr(
                                    f"{idx:02d}_{base_name}_{w_cm:.0f}x{h_cm:.0f}cm.jpg",
                                    export_image_bytes(pimg, "JPEG"),
                                )
                        st.download_button(
                            "⬇️ Descargar Todas las Fotos en ZIP (JPG 300 DPI)",
                            data=zip_buf.getvalue(),
                            file_name=f"fotos_{w_cm:.0f}x{h_cm:.0f}cm.zip",
                            mime="application/zip",
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

        st.subheader("2. Tamaño del Póster")
        poster_size_label = st.selectbox(
            "Dimensiones finales de impresión",
            options=list(PHOTO_SIZES_CM.keys())[4:],
            index=4,  # 30 x 40 cm por defecto
        )
        poster_orient = st.radio(
            "Orientación del Póster",
            ["Vertical", "Horizontal"],
            key="poster_orient",
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
        export_fmt_poster = st.selectbox(
            "Formato de salida del Póster",
            ["JPEG Alta Calidad (300 DPI)", "PDF para Impresión Gran Formato"],
        )

    with p_col_prev:
        st.subheader("Vista Previa del Póster")
        if poster_files:
            pw_cm, ph_cm = PHOTO_SIZES_CM[poster_size_label]
            if poster_orient == "Horizontal":
                pw_cm, ph_cm = max(pw_cm, ph_cm), min(pw_cm, ph_cm)
            else:
                pw_cm, ph_cm = min(pw_cm, ph_cm), max(pw_cm, ph_cm)

            pw_px = cm_to_px(pw_cm)
            ph_px = cm_to_px(ph_cm)

            loaded_poster_imgs = [load_image_corrected(f) for f in poster_files]
            capacity = grid_cols * grid_rows
            if len(loaded_poster_imgs) > capacity:
                st.warning(
                    f"Subiste {len(loaded_poster_imgs)} fotos, pero la cuadrícula de {grid_cols}x{grid_rows} solo tiene espacio para {capacity}. Aumenta filas o columnas para incluirlas todas."
                )

            poster_img = build_poster_collage(
                images=loaded_poster_imgs,
                poster_w_px=pw_px,
                poster_h_px=ph_px,
                cols=grid_cols,
                rows=grid_rows,
                margin_px=cm_to_px(poster_margin_mm / 10.0),
                gap_px=cm_to_px(poster_gap_mm / 10.0),
                bg_color=bg_rgb,
                cell_fit_mode=cell_fit,
            )

            # Vista previa optimizada en pantalla para evitar lag en resoluciones 50x70 / 60x90 cm
            preview_copy = poster_img.copy()
            preview_copy.thumbnail((1400, 1400), Image.Resampling.LANCZOS)
            st.image(
                preview_copy,
                caption=f"Póster {pw_cm:.0f} x {ph_cm:.0f} cm | Resolución real: {pw_px} x {ph_px} px (300 DPI)",
                use_container_width=True,
            )

            p_fmt = "PDF" if "PDF" in export_fmt_poster else "JPEG"
            p_ext = "pdf" if p_fmt == "PDF" else "jpg"

            st.download_button(
                f"⬇️ Descargar Póster ({pw_cm:.0f}x{ph_cm:.0f} cm - {p_ext.upper()})",
                data=export_image_bytes(poster_img, p_fmt),
                file_name=f"poster_{pw_cm:.0f}x{ph_cm:.0f}cm.{p_ext}",
                mime="application/pdf" if p_fmt == "PDF" else "image/jpeg",
                use_container_width=True,
            )
        else:
            st.info("👈 Selecciona varias fotografías en el panel izquierdo para armar tu póster.")
