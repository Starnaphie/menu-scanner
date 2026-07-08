import argparse
import json
import time
import uuid
from pathlib import Path
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen


DEFAULT_URL = "http://localhost:8000/extract"
IMAGE_MIME_TYPES = {
    ".jpg": "image/jpeg",
    ".jpeg": "image/jpeg",
    ".png": "image/png",
    ".webp": "image/webp",
    ".gif": "image/gif",
}


def _multipart_body(path: Path, mime_type: str, dietary_restrictions: str) -> tuple[bytes, str]:
    boundary = f"----latency-eval-{uuid.uuid4().hex}"
    parts = [
        f"--{boundary}\r\n".encode("utf-8"),
        b'Content-Disposition: form-data; name="dietary_restrictions"\r\n\r\n',
        dietary_restrictions.encode("utf-8"),
        b"\r\n",
        f"--{boundary}\r\n".encode("utf-8"),
        (
            f'Content-Disposition: form-data; name="file"; filename="{path.name}"\r\n'
            f"Content-Type: {mime_type}\r\n\r\n"
        ).encode("utf-8"),
        path.read_bytes(),
        b"\r\n",
        f"--{boundary}--\r\n".encode("utf-8"),
    ]
    return b"".join(parts), boundary


def _post_image(url: str, path: Path, dietary_restrictions: str) -> dict:
    mime_type = IMAGE_MIME_TYPES[path.suffix.lower()]
    body, boundary = _multipart_body(path, mime_type, dietary_restrictions)
    request = Request(
        url,
        data=body,
        headers={"Content-Type": f"multipart/form-data; boundary={boundary}"},
        method="POST",
    )

    started = time.perf_counter()
    try:
        with urlopen(request) as response:
            response_body = response.read()
    except HTTPError as exc:
        error_body = exc.read().decode("utf-8", errors="replace")
        raise RuntimeError(f"HTTP {exc.code}: {error_body}") from exc
    except URLError as exc:
        raise RuntimeError(f"Request failed: {exc.reason}") from exc

    wall_ms = (time.perf_counter() - started) * 1000
    payload = json.loads(response_body)
    items = payload.get("items", [])
    breakdown = payload.get("latency_breakdown", {})

    return {
        "filename": path.name,
        "ocr_ms": float(breakdown.get("stage1_ocr", 0)),
        "llm_ms": float(breakdown.get("openai_api", 0)),
        "total_ms": wall_ms,
        "pipeline_ms": float(breakdown.get("total_pipeline", 0)),
        "items_returned": len(items) if isinstance(items, list) else 0,
        "response_bytes": len(response_body),
    }


def _iter_images(directory: Path) -> list[Path]:
    return sorted(
        path
        for path in directory.iterdir()
        if path.is_file() and path.suffix.lower() in IMAGE_MIME_TYPES
    )


def _print_table(rows: list[dict]) -> None:
    headers = ["filename", "ocr_ms", "llm_ms", "total_ms", "items_returned", "response_bytes"]
    widths = {
        "filename": max(len("filename"), *(len(row["filename"]) for row in rows)),
        "ocr_ms": len("ocr_ms"),
        "llm_ms": len("llm_ms"),
        "total_ms": len("total_ms"),
        "items_returned": len("items_returned"),
        "response_bytes": len("response_bytes"),
    }

    def format_row(row: dict) -> str:
        return (
            f"{row['filename']:<{widths['filename']}} | "
            f"{row['ocr_ms']:>{widths['ocr_ms']}.0f} | "
            f"{row['llm_ms']:>{widths['llm_ms']}.0f} | "
            f"{row['total_ms']:>{widths['total_ms']}.0f} | "
            f"{row['items_returned']:>{widths['items_returned']}} | "
            f"{row['response_bytes']:>{widths['response_bytes']}}"
        )

    print(
        f"{headers[0]:<{widths['filename']}} | "
        f"{headers[1]:>{widths['ocr_ms']}} | "
        f"{headers[2]:>{widths['llm_ms']}} | "
        f"{headers[3]:>{widths['total_ms']}} | "
        f"{headers[4]:>{widths['items_returned']}} | "
        f"{headers[5]:>{widths['response_bytes']}}"
    )
    print(
        f"{'-' * widths['filename']} | "
        f"{'-' * widths['ocr_ms']} | "
        f"{'-' * widths['llm_ms']} | "
        f"{'-' * widths['total_ms']} | "
        f"{'-' * widths['items_returned']} | "
        f"{'-' * widths['response_bytes']}"
    )

    for row in rows:
        print(format_row(row))

    count = len(rows)
    summary = {
        "filename": "AVG",
        "ocr_ms": sum(row["ocr_ms"] for row in rows) / count,
        "llm_ms": sum(row["llm_ms"] for row in rows) / count,
        "total_ms": sum(row["total_ms"] for row in rows) / count,
        "items_returned": round(sum(row["items_returned"] for row in rows) / count, 1),
        "response_bytes": round(sum(row["response_bytes"] for row in rows) / count, 1),
    }
    print(format_row(summary))


def main() -> int:
    parser = argparse.ArgumentParser(description="Measure /extract latency over a directory of images.")
    parser.add_argument("image_dir", nargs="?", default="demo-docs/")
    parser.add_argument("--url", default=DEFAULT_URL)
    parser.add_argument("--dietary-restrictions", default="[]")
    args = parser.parse_args()

    image_dir = Path(args.image_dir)
    if not image_dir.is_dir():
        print(f"Image directory not found: {image_dir}")
        return 1

    rows = []
    for path in _iter_images(image_dir):
        try:
            rows.append(_post_image(args.url, path, args.dietary_restrictions))
        except RuntimeError as exc:
            print(f"{path.name}: {exc}")

    if not rows:
        print(f"No supported images processed in {image_dir}")
        return 1

    _print_table(rows)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
