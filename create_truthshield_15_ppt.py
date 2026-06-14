from pathlib import Path
from zipfile import ZipFile, ZIP_DEFLATED
from xml.sax.saxutils import escape


BASE_DIR = Path(__file__).resolve().parent
OUT = BASE_DIR / "TruthShield_15_Slide_Presentation.pptx"

SLIDES = [
    (
        "TruthShield",
        "AI Deepfake Fraud Detection System",
        [
            "Project presentation",
            "Media verification for image, video, and audio",
            "Frontend, backend, database, and detection workflow",
        ],
    ),
    (
        "Introduction",
        "Deepfake media is a growing digital trust issue.",
        [
            "Deepfakes can create fake images, videos, and audio that appear real.",
            "They may be used for misinformation, impersonation, and fraud.",
            "TruthShield helps users verify suspicious digital media.",
        ],
    ),
    (
        "Problem Statement",
        "Normal users need a simple way to check suspicious media.",
        [
            "Manual verification is difficult and time consuming.",
            "Fake media spreads quickly through social media and messaging apps.",
            "Realistic AI-generated content can mislead users and organizations.",
        ],
    ),
    (
        "Objective",
        "The objective is to classify media as Authenticated or Manipulated.",
        [
            "Allow users to upload image, video, or audio files.",
            "Analyse uploaded media through backend detection logic.",
            "Display a clear result with confidence and signal explanation.",
            "Store detection history for users and admin review.",
        ],
    ),
    (
        "Existing System",
        "Existing methods are often manual, complex, or limited.",
        [
            "Many systems focus only on one media type.",
            "Some tools require expert knowledge or powerful hardware.",
            "Poor lighting, blur, and compression can affect detection quality.",
        ],
    ),
    (
        "Proposed System",
        "TruthShield provides a complete web-based verification workflow.",
        [
            "User registration and login",
            "Media upload and detection",
            "Result display with confidence value",
            "Detection history and admin monitoring",
        ],
    ),
    (
        "Technologies Used",
        "The project uses a practical web and Python technology stack.",
        [
            "Frontend: HTML, CSS, JavaScript",
            "Backend: Python Flask",
            "Database: SQLite",
            "Media processing: OpenCV and NumPy",
        ],
    ),
    (
        "System Architecture",
        "The system connects frontend, backend, detection logic, and database.",
        [
            "User interacts with the web interface.",
            "Flask backend receives requests and uploaded files.",
            "Detection module analyses the media.",
            "SQLite stores user data and detection history.",
        ],
    ),
    (
        "Working Process",
        "The workflow moves from user upload to final detection result.",
        [
            "User registers or logs in.",
            "User uploads suspicious media.",
            "Backend identifies media type and preprocesses the file.",
            "System displays Authenticated or Manipulated result.",
        ],
    ),
    (
        "Dataset Description",
        "The model path uses labelled real and fake media samples.",
        [
            "Dataset contains authenticated and manipulated video samples.",
            "Videos are separated into real and fake categories.",
            "Frames can be extracted from videos for training and testing.",
            "Larger balanced datasets can improve future accuracy.",
        ],
    ),
    (
        "Detection Techniques",
        "The system uses visual screening and model-based analysis.",
        [
            "Face visibility and facial consistency checking",
            "Lighting and scene stability analysis",
            "Texture and frame irregularity screening",
            "Motion continuity checking for videos",
        ],
    ),
    (
        "Model Implementation",
        "The backend combines preprocessing, model output, and decision logic.",
        [
            "Uploaded media is prepared by the backend.",
            "Video files are sampled into selected frames.",
            "The model generates verification scores.",
            "Final output is generated with confidence and explanation signals.",
        ],
    ),
    (
        "Features, Advantages and Limitations",
        "The project is useful, but detection can still be improved.",
        [
            "Features: login, upload, result, history, and admin page",
            "Advantages: simple interface, quick workflow, and stored history",
            "Limitations: result depends on media quality and model strength",
            "It is a project-level detector, not a forensic replacement.",
        ],
    ),
    (
        "Future Enhancements and Conclusion",
        "TruthShield is a strong foundation for future deepfake detection work.",
        [
            "Train with larger and more balanced datasets.",
            "Add stronger image, video, and audio detection models.",
            "Improve real-time webcam and mobile support.",
            "The project supports safer digital media verification.",
        ],
    ),
    (
        "References and Thank You",
        "Thank You",
        [
            "FaceForensics++ and DFDC deepfake detection research",
            "Deepfake video detection and media forensic studies",
            "Python Flask, SQLite, OpenCV, HTML, CSS, and JavaScript documentation",
            "Questions and Answers",
        ],
    ),
]


def tx(text):
    return escape(text).replace("\n", "&#10;")


def text_box(text, x, y, w, h, size=2400, bold=False, color="111111"):
    bold_xml = "<a:b/>" if bold else ""
    return f"""
    <p:sp>
      <p:nvSpPr><p:cNvPr id="1" name="TextBox"/><p:cNvSpPr txBox="1"/><p:nvPr/></p:nvSpPr>
      <p:spPr><a:xfrm><a:off x="{x}" y="{y}"/><a:ext cx="{w}" cy="{h}"/></a:xfrm><a:prstGeom prst="rect"><a:avLst/></a:prstGeom><a:noFill/><a:ln><a:noFill/></a:ln></p:spPr>
      <p:txBody>
        <a:bodyPr wrap="square" anchor="t"/>
        <a:lstStyle/>
        <a:p><a:r><a:rPr lang="en-US" sz="{size}">{bold_xml}<a:solidFill><a:srgbClr val="{color}"/></a:solidFill><a:latin typeface="Aptos"/></a:rPr><a:t>{tx(text)}</a:t></a:r></a:p>
      </p:txBody>
    </p:sp>"""


def bullet_box(items, x, y, w, h):
    paragraphs = []
    for item in items:
        paragraphs.append(
            f"""
        <a:p>
          <a:pPr marL="342900" indent="-228600"><a:buChar char="•"/></a:pPr>
          <a:r><a:rPr lang="en-US" sz="2150"><a:solidFill><a:srgbClr val="222222"/></a:solidFill><a:latin typeface="Aptos"/></a:rPr><a:t>{tx(item)}</a:t></a:r>
        </a:p>"""
        )
    return f"""
    <p:sp>
      <p:nvSpPr><p:cNvPr id="2" name="Bullets"/><p:cNvSpPr txBox="1"/><p:nvPr/></p:nvSpPr>
      <p:spPr><a:xfrm><a:off x="{x}" y="{y}"/><a:ext cx="{w}" cy="{h}"/></a:xfrm><a:prstGeom prst="rect"><a:avLst/></a:prstGeom><a:noFill/><a:ln><a:noFill/></a:ln></p:spPr>
      <p:txBody><a:bodyPr wrap="square" anchor="t"/><a:lstStyle/>{''.join(paragraphs)}</p:txBody>
    </p:sp>"""


def rect(x, y, w, h, fill, line="FFFFFF"):
    return f"""
    <p:sp>
      <p:nvSpPr><p:cNvPr id="3" name="Shape"/><p:cNvSpPr/><p:nvPr/></p:nvSpPr>
      <p:spPr><a:xfrm><a:off x="{x}" y="{y}"/><a:ext cx="{w}" cy="{h}"/></a:xfrm><a:prstGeom prst="rect"><a:avLst/></a:prstGeom><a:solidFill><a:srgbClr val="{fill}"/></a:solidFill><a:ln><a:solidFill><a:srgbClr val="{line}"/></a:solidFill></a:ln></p:spPr>
    </p:sp>"""


def slide_xml(index, kicker, title, bullets):
    bg = rect(0, 0, 12192000, 6858000, "F8F9F4", "F8F9F4")
    top = rect(0, 0, 12192000, 160000, "0E2F37", "0E2F37")
    accent = rect(609600, 480000, 400000, 50000, "0B7285", "0B7285")
    page = text_box(str(index).zfill(2), 11000000, 390000, 700000, 250000, 1250, True, "5F6D7A")
    footer = text_box("AI Deepfake Fraud Detection | Project Presentation", 609600, 6500000, 6000000, 220000, 1050, False, "5F6D7A")
    return f"""<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<p:sld xmlns:a="http://schemas.openxmlformats.org/drawingml/2006/main" xmlns:r="http://schemas.openxmlformats.org/officeDocument/2006/relationships" xmlns:p="http://schemas.openxmlformats.org/presentationml/2006/main">
  <p:cSld><p:spTree>
    <p:nvGrpSpPr><p:cNvPr id="1" name=""/><p:cNvGrpSpPr/><p:nvPr/></p:nvGrpSpPr>
    <p:grpSpPr><a:xfrm><a:off x="0" y="0"/><a:ext cx="0" cy="0"/><a:chOff x="0" y="0"/><a:chExt cx="0" cy="0"/></a:xfrm></p:grpSpPr>
    {bg}{top}{accent}
    {text_box(kicker.upper(), 1100000, 390000, 5600000, 260000, 1150, True, "0B7285")}
    {page}
    {text_box(title, 609600, 1050000, 9000000, 1100000, 3100, True, "17212B")}
    {bullet_box(bullets, 900000, 2550000, 9700000, 3100000)}
    {footer}
  </p:spTree></p:cSld>
  <p:clrMapOvr><a:masterClrMapping/></p:clrMapOvr>
</p:sld>"""


def write_pptx():
    slide_count = len(SLIDES)
    content_types = [
        '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>',
        '<Types xmlns="http://schemas.openxmlformats.org/package/2006/content-types">',
        '<Default Extension="rels" ContentType="application/vnd.openxmlformats-package.relationships+xml"/>',
        '<Default Extension="xml" ContentType="application/xml"/>',
        '<Override PartName="/ppt/presentation.xml" ContentType="application/vnd.openxmlformats-officedocument.presentationml.presentation.main+xml"/>',
        '<Override PartName="/ppt/slideMasters/slideMaster1.xml" ContentType="application/vnd.openxmlformats-officedocument.presentationml.slideMaster+xml"/>',
        '<Override PartName="/ppt/slideLayouts/slideLayout1.xml" ContentType="application/vnd.openxmlformats-officedocument.presentationml.slideLayout+xml"/>',
        '<Override PartName="/ppt/theme/theme1.xml" ContentType="application/vnd.openxmlformats-officedocument.theme+xml"/>',
    ]
    for i in range(1, slide_count + 1):
        content_types.append(f'<Override PartName="/ppt/slides/slide{i}.xml" ContentType="application/vnd.openxmlformats-officedocument.presentationml.slide+xml"/>')
    content_types.append("</Types>")

    presentation_rels = [
        '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>',
        '<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">',
        '<Relationship Id="rId1" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/slideMaster" Target="slideMasters/slideMaster1.xml"/>',
    ]
    for i in range(1, slide_count + 1):
        presentation_rels.append(f'<Relationship Id="rId{i+1}" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/slide" Target="slides/slide{i}.xml"/>')
    presentation_rels.append("</Relationships>")

    slide_ids = "".join([f'<p:sldId id="{255+i}" r:id="rId{i+1}"/>' for i in range(1, slide_count + 1)])
    presentation_xml = f"""<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<p:presentation xmlns:a="http://schemas.openxmlformats.org/drawingml/2006/main" xmlns:r="http://schemas.openxmlformats.org/officeDocument/2006/relationships" xmlns:p="http://schemas.openxmlformats.org/presentationml/2006/main">
  <p:sldMasterIdLst><p:sldMasterId id="2147483648" r:id="rId1"/></p:sldMasterIdLst>
  <p:sldIdLst>{slide_ids}</p:sldIdLst>
  <p:sldSz cx="12192000" cy="6858000" type="screen16x9"/>
  <p:notesSz cx="6858000" cy="9144000"/>
</p:presentation>"""

    rels_root = """<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">
  <Relationship Id="rId1" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/officeDocument" Target="ppt/presentation.xml"/>
</Relationships>"""

    master = """<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<p:sldMaster xmlns:a="http://schemas.openxmlformats.org/drawingml/2006/main" xmlns:r="http://schemas.openxmlformats.org/officeDocument/2006/relationships" xmlns:p="http://schemas.openxmlformats.org/presentationml/2006/main">
<p:cSld><p:spTree><p:nvGrpSpPr><p:cNvPr id="1" name=""/><p:cNvGrpSpPr/><p:nvPr/></p:nvGrpSpPr><p:grpSpPr><a:xfrm><a:off x="0" y="0"/><a:ext cx="0" cy="0"/><a:chOff x="0" y="0"/><a:chExt cx="0" cy="0"/></a:xfrm></p:grpSpPr></p:spTree></p:cSld><p:sldLayoutIdLst><p:sldLayoutId id="2147483649" r:id="rId1"/></p:sldLayoutIdLst><p:txStyles><p:titleStyle/><p:bodyStyle/><p:otherStyle/></p:txStyles></p:sldMaster>"""

    master_rels = """<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">
  <Relationship Id="rId1" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/slideLayout" Target="../slideLayouts/slideLayout1.xml"/>
  <Relationship Id="rId2" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/theme" Target="../theme/theme1.xml"/>
</Relationships>"""

    layout = """<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<p:sldLayout xmlns:a="http://schemas.openxmlformats.org/drawingml/2006/main" xmlns:r="http://schemas.openxmlformats.org/officeDocument/2006/relationships" xmlns:p="http://schemas.openxmlformats.org/presentationml/2006/main" type="blank" preserve="1"><p:cSld name="Blank"><p:spTree><p:nvGrpSpPr><p:cNvPr id="1" name=""/><p:cNvGrpSpPr/><p:nvPr/></p:nvGrpSpPr><p:grpSpPr><a:xfrm><a:off x="0" y="0"/><a:ext cx="0" cy="0"/><a:chOff x="0" y="0"/><a:chExt cx="0" cy="0"/></a:xfrm></p:grpSpPr></p:spTree></p:cSld><p:clrMapOvr><a:masterClrMapping/></p:clrMapOvr></p:sldLayout>"""

    layout_rels = """<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">
  <Relationship Id="rId1" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/slideMaster" Target="../slideMasters/slideMaster1.xml"/>
</Relationships>"""

    theme = """<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<a:theme xmlns:a="http://schemas.openxmlformats.org/drawingml/2006/main" name="TruthShield"><a:themeElements><a:clrScheme name="TruthShield"><a:dk1><a:srgbClr val="17212B"/></a:dk1><a:lt1><a:srgbClr val="F8F9F4"/></a:lt1><a:dk2><a:srgbClr val="102A33"/></a:dk2><a:lt2><a:srgbClr val="FFFFFF"/></a:lt2><a:accent1><a:srgbClr val="0B7285"/></a:accent1><a:accent2><a:srgbClr val="D9480F"/></a:accent2><a:accent3><a:srgbClr val="5F6D7A"/></a:accent3><a:accent4><a:srgbClr val="CFD8DC"/></a:accent4><a:accent5><a:srgbClr val="E9F3F5"/></a:accent5><a:accent6><a:srgbClr val="111111"/></a:accent6><a:hlink><a:srgbClr val="0B7285"/></a:hlink><a:folHlink><a:srgbClr val="5F6D7A"/></a:folHlink></a:clrScheme><a:fontScheme name="TruthShield"><a:majorFont><a:latin typeface="Georgia"/></a:majorFont><a:minorFont><a:latin typeface="Aptos"/></a:minorFont></a:fontScheme><a:fmtScheme name="TruthShield"><a:fillStyleLst/><a:lnStyleLst/><a:effectStyleLst/><a:bgFillStyleLst/></a:fmtScheme></a:themeElements></a:theme>"""

    with ZipFile(OUT, "w", ZIP_DEFLATED) as z:
        z.writestr("[Content_Types].xml", "\n".join(content_types))
        z.writestr("_rels/.rels", rels_root)
        z.writestr("ppt/presentation.xml", presentation_xml)
        z.writestr("ppt/_rels/presentation.xml.rels", "\n".join(presentation_rels))
        z.writestr("ppt/slideMasters/slideMaster1.xml", master)
        z.writestr("ppt/slideMasters/_rels/slideMaster1.xml.rels", master_rels)
        z.writestr("ppt/slideLayouts/slideLayout1.xml", layout)
        z.writestr("ppt/slideLayouts/_rels/slideLayout1.xml.rels", layout_rels)
        z.writestr("ppt/theme/theme1.xml", theme)
        for i, (kicker, title, bullets) in enumerate(SLIDES, 1):
            z.writestr(f"ppt/slides/slide{i}.xml", slide_xml(i, kicker, title, bullets))


if __name__ == "__main__":
    write_pptx()
    print(OUT)
