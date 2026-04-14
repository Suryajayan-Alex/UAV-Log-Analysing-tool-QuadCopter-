import re

log_path = r'C:\Users\suryajayan.alex\.gemini\antigravity\brain\3ceaa934-1fbb-4332-9c7c-31e991d21416\.system_generated\logs\overview.txt'

with open(log_path, 'r', encoding='utf-8') as f:
    text = f.read()

# Part 1: lines 1 to 500
part1_start = text.find('Showing lines 1 to 500')
part1_end = text.find('The above content does NOT show the entire file contents.', part1_start)
part1_lines = text[part1_start:part1_end].split('\n')[2:-1]
part1_code = [re.sub(r'^\d+:\s', '', line) for line in part1_lines]

# Part 2: lines 568 to 1367
part2_start = text.find('Showing lines 568 to 1367')
part2_end = text.find('The above content does NOT show the entire file contents.', part2_start)
part2_lines = text[part2_start:part2_end].split('\n')[2:-1]
part2_code = [re.sub(r'^\d+:\s', '', line) for line in part2_lines]

missing_code = """    c.setFont("Helvetica-Bold", 13)
    c.drawString(40, page_height - 28, title)

    if logo_path and logo_path.exists():
        try:
            logo = ImageReader(str(logo_path))
            lw, lh = logo.getSize()
            scale = min(120 / lw, 28 / lh)
            w = lw * scale
            h = lh * scale
            c.drawImage(logo, page_width - 42 - w, page_height - 36, width=w, height=h, mask="auto")
        except Exception:
            pass

    return page_height - 56


def _draw_cover_page(
    c: canvas.Canvas,
    page_width: float,
    page_height: float,
    metadata: dict[str, str],
    plot_count: int,
    logo_path: Path | None = None,
) -> None:
    top_y = _draw_page_header(c, page_width, page_height, "UAV Flight Log Analysis Report", logo_path=logo_path)

    c.setFillColorRGB(*_hex_to_reportlab_rgb(ASTERIA.text_dark))
    c.setFont("Helvetica", 12)

    y = top_y - 18
    c.drawString(48, y, f"Generated On: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    y -= 22
    c.drawString(48, y, f"Log File: {metadata.get('log_file', '')}")
    y -= 22
    c.drawString(48, y, f"Air Vehicle: {metadata.get('vehicle', '')}")
    y -= 22
    c.drawString(48, y, f"Pilot: {metadata.get('pilot', '')}")
    y -= 22
    c.drawString(48, y, f"Co-Pilot: {metadata.get('copilot', '')}")
    y -= 22
    c.drawString(48, y, f"Mission: {metadata.get('mission', '')}")
    y -= 30

    c.setFont("Helvetica-Bold", 13)
    c.setFillColorRGB(*_hex_to_reportlab_rgb(ASTERIA.primary))
    c.drawString(48, y, f"Generated Plots: {plot_count}")

    _draw_page_footer(c, page_width)
    c.showPage()


def _draw_stats_pages(c: canvas.Canvas, page_width: float, page_height: float, stats: list[SignalStats], logo_path: Path | None = None) -> None:
    if not stats:
        _draw_page_header(c, page_width, page_height, "Min/Max Summary by Plot Signal", logo_path=logo_path)
        c.setFillColorRGB(*_hex_to_reportlab_rgb(ASTERIA.text_dark))
        c.setFont("Helvetica", 11)
        c.drawString(42, page_height - 90, "No plottable numeric signals were found.")
        _draw_page_footer(c, page_width)
        c.showPage()
        return

    ordered = sorted(stats, key=lambda s: (s.plot_title, s.signal))

    columns = [
        ("Plot", 42, 310, "left"),
        ("Signal", 310, 500, "left"),""".split('\n')

with open('reporting.py', 'w', encoding='utf-8') as f:
    f.write('\n'.join(part1_code) + '\n' + '\n'.join(missing_code) + '\n' + '\n'.join(part2_code) + '\n')

print("Reconstruction complete.")
