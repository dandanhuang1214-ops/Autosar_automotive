"""Create a deterministic, public two-signal DOCX for the Generate-Arxml bridge."""

from __future__ import annotations

import argparse
import zipfile
from pathlib import Path
from xml.sax.saxutils import escape


def create_document(
    path: Path, *, resolution: str = "1", omit_init: bool = False
) -> None:
    def paragraph(text: str) -> str:
        return f'<w:p><w:r><w:t xml:space="preserve">{escape(text)}</w:t></w:r></w:p>'

    def table(rows: list[list[str]]) -> str:
        return (
            "<w:tbl>"
            + "".join(
                "<w:tr>"
                + "".join("<w:tc>" + paragraph(cell) + "</w:tc>" for cell in row)
                + "</w:tr>"
                for row in rows
            )
            + "</w:tbl>"
        )

    headers = [
        "SignalName",
        "Direction",
        "ProviderSWC",
        "ConsumerSWC",
        "ValueType",
        "ApplicationDataType",
        "InternalDataType",
        "InternalRange",
        "PhysicalRange",
        "Resolution",
        "Offset",
        "Unit",
        "InitValue",
        "PeriodMs",
        "Description",
    ]
    rows = [
        headers,
        [
            "WindowPosition",
            "output",
            "WindowControlSwc",
            "BODY_ECU",
            "Value",
            "App_WindowPosition",
            "uint8",
            "0-100",
            "0-100",
            resolution,
            "0",
            "%",
            "" if omit_init else "0",
            "10",
            "Public fixture; position output",
        ],
        [
            "RequestedDirection",
            "input",
            "TESTER",
            "WindowControlSwc",
            "Value",
            "App_RequestedDirection",
            "uint8",
            "0-3",
            "0-3",
            "1",
            "0",
            "",
            "0",
            "10",
            "Public fixture; requested direction 0..3",
        ],
    ]
    body = paragraph("WindowControlPublicSample ARXML delivery") + paragraph(
        "Public synthetic input; not an OEM or production specification."
    )
    body += table(
        [
            ["字段", "填写值"],
            ["项目/系统名称", "WindowControlPublicSample"],
            ["目标 AUTOSAR 版本", "4-3-0"],
            ["生成模式", "signal_atomic_davinci"],
        ]
    )
    body += paragraph("Signal interface") + table(rows)
    body += paragraph("Runnable") + table(
        [
            [
                "SWC",
                "RunnableName",
                "TriggerType",
                "PeriodMs",
                "ReadSignals",
                "WriteSignals",
            ],
            [
                "WindowControlSwc",
                "WindowControl_Step",
                "Periodic",
                "10",
                "RequestedDirection",
                "WindowPosition",
            ],
        ]
    )
    document = (
        '<?xml version="1.0" encoding="UTF-8" standalone="yes"?><w:document xmlns:w="http://schemas.openxmlformats.org/wordprocessingml/2006/main"><w:body>'
        + body
        + "<w:sectPr/></w:body></w:document>"
    )
    parts = {
        "[Content_Types].xml": '<?xml version="1.0"?><Types xmlns="http://schemas.openxmlformats.org/package/2006/content-types"><Default Extension="rels" ContentType="application/vnd.openxmlformats-package.relationships+xml"/><Default Extension="xml" ContentType="application/xml"/><Override PartName="/word/document.xml" ContentType="application/vnd.openxmlformats-officedocument.wordprocessingml.document.main+xml"/></Types>',
        "_rels/.rels": '<?xml version="1.0"?><Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships"><Relationship Id="rId1" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/officeDocument" Target="word/document.xml"/></Relationships>',
        "word/document.xml": document,
    }
    if path.exists():
        raise ValueError("DOCX output must not already exist")
    path.parent.mkdir(parents=True, exist_ok=True)
    with zipfile.ZipFile(path, "w") as archive:
        for name, content in sorted(parts.items()):
            info = zipfile.ZipInfo(name, (1980, 1, 1, 0, 0, 0))
            # Match the checked-in ZIP metadata on every host, including Windows.
            info.create_system = 3
            info.external_attr = 0o600 << 16
            archive.writestr(info, content.encode("utf-8"))


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--resolution", choices=["1", "2"], default="1")
    parser.add_argument("--omit-init", action="store_true")
    args = parser.parse_args()
    create_document(args.output, resolution=args.resolution, omit_init=args.omit_init)


if __name__ == "__main__":
    main()
