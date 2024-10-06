import random
import sys
from typing import cast

import cv2
import numpy as np
import torch
from numpy.typing import ArrayLike
from torch import Tensor

from neosr.utils import get_root_logger, tc


def mod_crop(img: np.ndarray, scale: int) -> np.ndarray:
    """Mod crop images, used during testing.

    Args:
    ----
        img (ndarray): Input image.
        scale (int): Scale factor.

    Returns:
    -------
        ndarray: Result image.

    """
    img = img.copy()
    if img.ndim in {2, 3}:
        h, w = img.shape[0], img.shape[1]
        h_remainder, w_remainder = h % scale, w % scale
        img = img[: h - h_remainder, : w - w_remainder, ...]
    else:
        msg = f"Wrong img ndim: {img.ndim}."
        raise ValueError(msg)
    return img


def paired_random_crop(
    img_gts: list[np.ndarray | Tensor] | np.ndarray | Tensor | ArrayLike,
    img_lqs: list[np.ndarray | Tensor] | np.ndarray | Tensor | ArrayLike,
    lq_patch_size: int,
    scale: int,
    gt_path: str | None = None,
) -> tuple[
    list[np.ndarray | Tensor] | np.ndarray | Tensor,
    list[np.ndarray | Tensor] | np.ndarray | Tensor,
]:
    """Paired random crop. Support Numpy array and Tensor inputs.

    It crops lists of lq and gt images with corresponding locations.

    Args:
    ----
        img_gts (list[ndarray] | ndarray | list[Tensor] | Tensor): GT images. Note that all images
            should have the same shape. If the input is an ndarray, it will
            be transformed to a list containing itself.
        img_lqs (list[ndarray] | ndarray): LQ images. Note that all images
            should have the same shape. If the input is an ndarray, it will
            be transformed to a list containing itself.
        lq_patch_size (int): LQ patch size.
        scale (int): Scale factor.
        gt_path (str): Path to ground-truth. Default: None.

    Returns:
    -------
        list[ndarray] | ndarray: GT images and LQ images. If returned results
            only have one element, just return ndarray.

    """
    if not isinstance(img_gts, list):
        img_gts = cast(list[np.ndarray], [img_gts])
    if not isinstance(img_lqs, list):
        img_lqs = cast(list[np.ndarray], [img_lqs])

    # initialize logger
    logger = get_root_logger()

    # determine input type: Numpy array or Tensor
    input_type = "Tensor" if torch.is_tensor(img_gts[0]) else "Numpy"

    if input_type == "Tensor":
        h_lq, w_lq = img_lqs[0].shape[2:]
        h_gt, w_gt = img_gts[0].shape[2:]
    else:
        h_lq, w_lq = img_lqs[0].shape[0:2]
        h_gt, w_gt = img_gts[0].shape[0:2]
    gt_patch_size = lq_patch_size * scale

    if h_gt != h_lq * scale or w_gt != w_lq * scale:
        msg = f"{tc.red}Scale mismatches. GT ({h_gt}, {w_gt}) is not {scale}x of LQ ({h_lq}, {w_lq}). Fix {gt_path}.{tc.end}"
        logger.error(msg)
        sys.exit(1)

    if h_lq < lq_patch_size or w_lq < lq_patch_size:
        msg = f"{tc.red}LQ ({h_lq}, {w_lq}) is smaller than patch size ({lq_patch_size}, {lq_patch_size}). Fix {gt_path}.{tc.end}"
        logger.error(msg)
        sys.exit(1)

    # randomly choose top and left coordinates for lq patch
    top =  (random.randint(0, h_lq - lq_patch_size) // 16) * 16
    left = (random.randint(0, w_lq - lq_patch_size) // 16) * 16

    # crop lq patch
    if input_type == "Tensor":
        img_lqs = [
            v[:, :, top : top + lq_patch_size, left : left + lq_patch_size]
            for v in img_lqs
        ]
    else:
        img_lqs = [
            v[top : top + lq_patch_size, left : left + lq_patch_size, ...]
            for v in img_lqs
        ]

    # crop corresponding gt patch
    top_gt, left_gt = int(top * scale), int(left * scale)
    if input_type == "Tensor":
        img_gts = [
            v[:, :, top_gt : top_gt + gt_patch_size, left_gt : left_gt + gt_patch_size]
            for v in img_gts
        ]
    else:
        img_gts = [
            v[top_gt : top_gt + gt_patch_size, left_gt : left_gt + gt_patch_size, ...]
            for v in img_gts
        ]
    if len(img_gts) == 1:
        img_gts = img_gts[0]
    if len(img_lqs) == 1:
        img_lqs = img_lqs[0]
    return img_gts, img_lqs


def basic_augment(
    imgs: list[np.ndarray] | list[ArrayLike] | np.ndarray | ArrayLike,
    hflip: bool = True,
    rotation: bool = True,
    flip_prob: float = 0.5,
    rotation_prob: float = 0.5,
    return_status: bool = False,
) -> (
    list[ArrayLike]
    | list[np.ndarray]
    | np.ndarray
    | ArrayLike
    | tuple[
        list[np.ndarray] | list[ArrayLike] | np.ndarray | ArrayLike,
        tuple[bool, bool, bool],
    ]
):
    """Augment: horizontal flips OR rotate (0, 90, 180, 270 degrees).

    We use vertical flip and transpose for rotation implementation.
    All the images in the list use the same augmentation.

    Args:
    ----
        imgs (list[ndarray] | ndarray): Images to be augmented. If the input
            is an ndarray, it will be transformed to a list.
        hflip (bool): Horizontal flip. Default: True.
        rotation (bool): Ratotation. Default: True.
        return_status (bool): Return the status of flip and rotation.
            Default: False.

    Returns:
    -------
        list[ndarray] | ndarray: Augmented images. If returned
            results only have one element, just return ndarray.

    """
    hflip = hflip and random.random() <= flip_prob
    vflip = rotation and random.random() <= flip_prob
    rot90 = rotation and random.random() <= rotation_prob

    def _augment(img: np.ndarray) -> np.ndarray | ArrayLike:
        if hflip:  # horizontal
            cv2.flip(img, 1, img)  # type: ignore[arg-type]
        if vflip:  # vertical
            cv2.flip(img, 0, img)  # type: ignore[arg-type]
        if rot90:
            img = img.transpose(1, 0, 2)
        return img

    if not isinstance(imgs, list):
        imgs = [imgs]
    imgs = [_augment(cast(np.ndarray, img)) for img in imgs]
    if len(imgs) == 1:
        imgs = imgs[0]

    if return_status:
        return imgs, (hflip, vflip, rot90)
    return imgs
