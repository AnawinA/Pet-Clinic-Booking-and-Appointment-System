from __future__ import annotations

import io
from pathlib import Path

from PIL import Image

from app.core.config import settings
from tests.helpers import auth


def make_png(width: int = 1600, height: int = 1200) -> bytes:
    buffer = io.BytesIO()
    Image.new("RGB", (width, height), (120, 170, 90)).save(buffer, format="PNG")
    return buffer.getvalue()


def uploaded_files(directory: Path) -> list[Path]:
    return list(directory.glob("*.webp"))


async def test_owner_upload_is_resized_and_visible_to_staff(
    client, tokens, seeded, tmp_path, monkeypatch
):
    monkeypatch.setattr(settings, "photo_dir", str(tmp_path))

    response = await client.post(
        f"/api/v1/pets/{seeded['pet1_id']}/photo",
        headers=auth(tokens["OWNER"]),
        files={"file": ("dog.png", make_png(), "image/png")},
    )
    assert response.status_code == 200, response.text
    assert response.json()["photo_updated_at"] is not None

    files = uploaded_files(tmp_path)
    assert len(files) == 1
    with Image.open(files[0]) as stored:
        assert stored.format == "WEBP"
        assert max(stored.size) == 1024
        assert stored.size == (1024, 768)

    owner_view = await client.get(
        f"/api/v1/pets/{seeded['pet1_id']}/photo", headers=auth(tokens["OWNER"])
    )
    assert owner_view.status_code == 200
    assert owner_view.headers["content-type"] == "image/webp"
    assert owner_view.content

    staff_view = await client.get(
        f"/api/v1/pets/{seeded['pet1_id']}/photo", headers=auth(tokens["STAFF"])
    )
    assert staff_view.status_code == 200

    other_owner = await client.get(
        f"/api/v1/pets/{seeded['pet1_id']}/photo", headers=auth(tokens["OWNER2"])
    )
    assert other_owner.status_code == 403


async def test_replacing_photo_removes_old_file(client, tokens, seeded, tmp_path, monkeypatch):
    monkeypatch.setattr(settings, "photo_dir", str(tmp_path))

    first = await client.post(
        f"/api/v1/pets/{seeded['pet1_id']}/photo",
        headers=auth(tokens["OWNER"]),
        files={"file": ("first.png", make_png(800, 600), "image/png")},
    )
    assert first.status_code == 200, first.text

    second = await client.post(
        f"/api/v1/pets/{seeded['pet1_id']}/photo",
        headers=auth(tokens["OWNER"]),
        files={"file": ("second.png", make_png(600, 800), "image/png")},
    )
    assert second.status_code == 200, second.text

    files = uploaded_files(tmp_path)
    assert len(files) == 1
    with Image.open(files[0]) as stored:
        assert stored.size == (600, 800)


async def test_owner_can_delete_photo_and_file_is_removed(
    client, tokens, seeded, tmp_path, monkeypatch
):
    monkeypatch.setattr(settings, "photo_dir", str(tmp_path))
    url = f"/api/v1/pets/{seeded['pet1_id']}/photo"

    upload = await client.post(
        url,
        headers=auth(tokens["OWNER"]),
        files={"file": ("dog.png", make_png(400, 300), "image/png")},
    )
    assert upload.status_code == 200, upload.text
    assert len(uploaded_files(tmp_path)) == 1

    denied = await client.delete(url, headers=auth(tokens["OWNER2"]))
    assert denied.status_code == 403
    assert len(uploaded_files(tmp_path)) == 1

    deleted = await client.delete(url, headers=auth(tokens["OWNER"]))
    assert deleted.status_code == 200, deleted.text
    assert deleted.json()["photo_updated_at"] is None
    assert uploaded_files(tmp_path) == []

    missing = await client.get(url, headers=auth(tokens["OWNER"]))
    assert missing.status_code == 404
    assert missing.json()["error"]["code"] == "PET_PHOTO_NOT_FOUND"

    again = await client.delete(url, headers=auth(tokens["OWNER"]))
    assert again.status_code == 404


async def test_invalid_image_and_non_owner_are_rejected(
    client, tokens, seeded, tmp_path, monkeypatch
):
    monkeypatch.setattr(settings, "photo_dir", str(tmp_path))

    invalid = await client.post(
        f"/api/v1/pets/{seeded['pet1_id']}/photo",
        headers=auth(tokens["OWNER"]),
        files={"file": ("not-an-image.png", b"not an image", "image/png")},
    )
    assert invalid.status_code == 422
    assert invalid.json()["error"]["code"] == "INVALID_IMAGE"
    assert uploaded_files(tmp_path) == []

    forbidden = await client.post(
        f"/api/v1/pets/{seeded['pet1_id']}/photo",
        headers=auth(tokens["OWNER2"]),
        files={"file": ("dog.png", make_png(200, 200), "image/png")},
    )
    assert forbidden.status_code == 403
