from pathlib import Path

from reportlab.lib import colors
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib.units import mm
from reportlab.platypus import Paragraph, SimpleDocTemplate, Spacer, Table, TableStyle


ROOT = Path(__file__).resolve().parent.parent
OUTPUT_DIR = ROOT / "output" / "pdf"
OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
PDF_PATH = OUTPUT_DIR / "app_repo_summary_one_page.pdf"


def bullet_list(items, style, bullet_color):
    color = bullet_color.hexval()[2:]
    rows = []
    for item in items:
        rows.append(
            [
                Paragraph(f'<font color="#{color}">-</font>', style),
                Paragraph(item, style),
            ]
        )
    table = Table(rows, colWidths=[4 * mm, None])
    table.setStyle(
        TableStyle(
            [
                ("VALIGN", (0, 0), (-1, -1), "TOP"),
                ("LEFTPADDING", (0, 0), (-1, -1), 0),
                ("RIGHTPADDING", (0, 0), (-1, -1), 0),
                ("TOPPADDING", (0, 0), (-1, -1), 0),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 0),
            ]
        )
    )
    return table


def build_story():
    styles = getSampleStyleSheet()

    title = ParagraphStyle(
        "TitleSmall",
        parent=styles["Title"],
        fontName="Helvetica-Bold",
        fontSize=18,
        leading=21,
        textColor=colors.HexColor("#16324F"),
        spaceAfter=5,
    )
    subtitle = ParagraphStyle(
        "Subtitle",
        parent=styles["BodyText"],
        fontName="Helvetica",
        fontSize=9,
        leading=11,
        textColor=colors.HexColor("#4A6178"),
        spaceAfter=8,
    )
    section = ParagraphStyle(
        "Section",
        parent=styles["Heading2"],
        fontName="Helvetica-Bold",
        fontSize=10,
        leading=12,
        textColor=colors.HexColor("#16324F"),
        spaceBefore=2,
        spaceAfter=3,
    )
    body = ParagraphStyle(
        "BodyCompact",
        parent=styles["BodyText"],
        fontName="Helvetica",
        fontSize=8.2,
        leading=10,
        textColor=colors.HexColor("#1F2933"),
        spaceAfter=1,
    )
    bullet = ParagraphStyle(
        "ItemCompact",
        parent=body,
        leftIndent=0,
        firstLineIndent=0,
        spaceAfter=1,
    )
    small = ParagraphStyle(
        "Small",
        parent=body,
        fontSize=7.4,
        leading=9,
        textColor=colors.HexColor("#4A5568"),
    )

    left_story = [
        Paragraph("App Summary", title),
        Paragraph(
            "Repo-based overview of the TFG climate-risk and geospatial analytics application for Comunidad Valenciana.",
            subtitle,
        ),
        Paragraph("What It Is", section),
        Paragraph(
            "An academic data and analytics app that builds a climate-risk workflow from ERA5-Land weather data through feature engineering, machine learning, and GIS outputs. Repo evidence shows a staged pipeline implemented with Python scripts, notebooks, processed datasets, and generated map/model artifacts.",
            body,
        ),
        Paragraph("Who It&apos;s For", section),
        Paragraph(
            "Primary persona: a TFG student or analyst exploring climate patterns, insurer-oriented risk scoring, and municipal geospatial analysis in Comunidad Valenciana.",
            body,
        ),
        Paragraph("What It Does", section),
        bullet_list(
            [
                "Downloads monthly ERA5-Land NetCDF climate files for Comunidad Valenciana with `cdsapi`.",
                "Flattens NetCDF files into tabular CSV data and standardizes key variables.",
                "Converts raw measures into usable metrics such as precipitation in mm, temperature in C, and wind speed.",
                "Merges monthly processed CSVs into a combined 2019-2024 dataset.",
                "Runs notebook-based feature engineering and climate/geospatial scoring workflows.",
                "Builds predictive and anomaly-analysis outputs with SHAP, PCA, and Isolation Forest.",
                "Produces GIS-style clustering and interactive/static map outputs for municipal analysis.",
            ],
            bullet,
            colors.HexColor("#2B6CB0"),
        ),
        Spacer(1, 3),
        Paragraph("How To Run", section),
        bullet_list(
            [
                "Create and activate a Python virtual environment.",
                "Install packages from `requirements.txt`.",
                "Set up CDS API credentials if you want to download ERA5-Land data.",
                "Run `scripts/download_era5_land_monthly.py`, `scripts/read_era5_land_basic.py`, and `scripts/merge_era5_land_csvs.py`.",
                "Open the notebooks in order: `notebook_1_ing_dato.ipynb` through `notebook_4_an_negocio.ipynb`.",
            ],
            bullet,
            colors.HexColor("#2B6CB0"),
        ),
    ]

    arch_rows = [
        [
            Paragraph("<b>Layer</b>", small),
            Paragraph("<b>Repo Evidence</b>", small),
        ],
        [
            Paragraph("Inputs", body),
            Paragraph("`DATA/RAW/*.nc` ERA5-Land files plus README references to IGN geometries.", body),
        ],
        [
            Paragraph("Ingestion", body),
            Paragraph("`download_era5_land_monthly.py` retrieves climate variables with `cdsapi` into `DATA/RAW`.", body),
        ],
        [
            Paragraph("Processing", body),
            Paragraph("`read_era5_land_basic.py` opens NetCDF via `xarray`, transforms to DataFrame, cleans, converts units, and writes CSVs to `DATA/PROCESSED`.", body),
        ],
        [
            Paragraph("Dataset Build", body),
            Paragraph("`merge_era5_land_csvs.py` appends monthly CSVs into `dataset_clima_cv_2019_2024_merge.csv`.", body),
        ],
        [
            Paragraph("Analytics", body),
            Paragraph("Notebooks 2-4 load prior outputs for feature engineering, model/SHAP analysis, clustering, and maps.", body),
        ],
        [
            Paragraph("Services", body),
            Paragraph("External services beyond CDS API and data files were not found in repo.", body),
        ],
        [
            Paragraph("UI/App Server", body),
            Paragraph("Not found in repo.", body),
        ],
    ]

    arch_table = Table(arch_rows, colWidths=[28 * mm, 65 * mm])
    arch_table.setStyle(
        TableStyle(
            [
                ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#E6EEF5")),
                ("TEXTCOLOR", (0, 0), (-1, 0), colors.HexColor("#16324F")),
                ("GRID", (0, 0), (-1, -1), 0.3, colors.HexColor("#B8C7D9")),
                ("VALIGN", (0, 0), (-1, -1), "TOP"),
                ("LEFTPADDING", (0, 0), (-1, -1), 4),
                ("RIGHTPADDING", (0, 0), (-1, -1), 4),
                ("TOPPADDING", (0, 0), (-1, -1), 3),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 3),
            ]
        )
    )

    right_story = [
        Paragraph("How It Works", section),
        Paragraph(
            "Compact architecture overview based only on files and notebook/readme content present in the repo:",
            body,
        ),
        arch_table,
        Spacer(1, 4),
        Paragraph("Evidence Notes", section),
        bullet_list(
            [
                "The repo contains scripts, notebooks, raw/processed datasets, and outputs, but no packaged web/mobile frontend.",
                "A direct app entrypoint under `src/` was not found; `src/__init__.py` is empty.",
                "README and notebook headings describe a four-stage pipeline from ingestion to business analysis maps.",
            ],
            bullet,
            colors.HexColor("#2B6CB0"),
        ),
    ]

    col_widths = [94 * mm, 88 * mm]
    wrapper = Table([[left_story, right_story]], colWidths=col_widths)
    wrapper.setStyle(
        TableStyle(
            [
                ("VALIGN", (0, 0), (-1, -1), "TOP"),
                ("LEFTPADDING", (0, 0), (-1, -1), 0),
                ("RIGHTPADDING", (0, 0), (-1, -1), 0),
                ("TOPPADDING", (0, 0), (-1, -1), 0),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 0),
            ]
        )
    )

    return [wrapper]


def main():
    doc = SimpleDocTemplate(
        str(PDF_PATH),
        pagesize=A4,
        leftMargin=12 * mm,
        rightMargin=12 * mm,
        topMargin=11 * mm,
        bottomMargin=10 * mm,
    )
    doc.build(build_story())
    print(PDF_PATH)


if __name__ == "__main__":
    main()
