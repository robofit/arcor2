import numpy as np
from PIL import Image, ImageChops

from arcor2.image import image_from_str, image_to_str


def test_image_str() -> None:

    imarray = np.random.rand(16, 16, 3) * 255
    img = Image.fromarray(imarray.astype("uint8")).convert("RGB")

    img_str = image_to_str(img, target_format="png")
    assert isinstance(img_str, str)
    img2 = image_from_str(img_str)

    diff = ImageChops.difference(img, img2)
    assert diff.getbbox() is None, "Difference image is not empty!"
