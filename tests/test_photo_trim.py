"""店家照片去白邊：只裁「補上去」的對稱白邊，不誤裁照片本身的白色區塊。"""

import pytest

PIL = pytest.importorskip('PIL')
from PIL import Image  # noqa: E402

from scripts.sync_cafe_photos import trim_white_padding  # noqa: E402


def _padded(photo_size, canvas=(100, 100)):
    """把一張深色「照片」置中貼到白色正方形上，模擬補白後的檔案。"""
    canvas_im = Image.new('RGB', canvas, (255, 255, 255))
    photo = Image.new('RGB', photo_size, (90, 60, 40))
    canvas_im.paste(photo, ((canvas[0] - photo_size[0]) // 2, (canvas[1] - photo_size[1]) // 2))
    return canvas_im


def test_side_padding_is_removed():
    assert trim_white_padding(_padded((80, 100))).size == (80, 100)


def test_top_bottom_padding_is_removed():
    assert trim_white_padding(_padded((100, 70))).size == (100, 70)


def test_photo_without_padding_is_untouched():
    im = Image.new('RGB', (100, 100), (90, 60, 40))
    assert trim_white_padding(im).size == (100, 100)


def test_one_sided_white_area_is_not_cropped():
    """照片左邊剛好是一片白牆：只有一側是白的，不是補白，不能裁。"""
    im = Image.new('RGB', (100, 100), (90, 60, 40))
    im.paste(Image.new('RGB', (30, 100), (255, 255, 255)), (0, 0))
    assert trim_white_padding(im).size == (100, 100)
