# -*- coding: utf-8 -*-
# Copyright (c) Facebook, Inc. and its affiliates. All Rights Reserved

"""
Common data processing utilities that are used in a
typical object detection data pipeline.
"""
import logging
import numpy as np
import pycocotools.mask as mask_util
import torch
from fvcore.common.file_io import PathManager
from PIL import Image, ImageOps
import pdb
import cv2
from detectron2.utils.flow_utils import readFlow

from detectron2.structures import (
    BitMasks,
    Boxes,
    BoxMode,
    Instances,
    Keypoints,
    PolygonMasks,
    RotatedBoxes,
    polygons_to_bitmask,
)

from . import transforms as T
from .catalog import MetadataCatalog


class SizeMismatchError(ValueError):
    """
    When loaded image has difference width/height compared with annotation.
    """


def read_image(file_name, format=None):
    """
    Read an image into the given format.
    Will apply rotation and flipping if the image has such exif information.

    Args:
        file_name (str): image file path
        format (str): one of the supported image modes in PIL, or "BGR"

    Returns:
        image (np.ndarray): an HWC image
    """
    with PathManager.open(file_name, "rb") as f:
        if format == "BGRT":            
            """
            # KAIST
            folder = file_name.split('visible')[0]
            img_name = file_name.split('visible/')[1]
            path_rgb = file_name
            path_thermal = folder + 'lwir/' + img_name
            img_rgb = cv2.imread(path_rgb)
            img_thermal = cv2.imread(path_thermal)
                        
            image = np.zeros((img_thermal.shape[0], img_thermal.shape[1], 4))
            image [:,:,0:3] = img_rgb
            image [:,:,3] = img_thermal[:,:,0]
            
            """
            # FLIR
            folder = file_name.split('thermal_8_bit/')[0]
            img_name = file_name.split('thermal_8_bit/')[1]
            img_name = img_name.split('.')[0] + '.jpg'
            rgb_path = folder + 'RGB/' + img_name
            #print(rgb_path)
            rgb_img = cv2.imread(rgb_path)
            thermal_img = cv2.imread(file_name)
            #import pdb; pdb.set_trace()
            rgb_img = cv2.resize(rgb_img,(thermal_img.shape[1], thermal_img.shape[0]))
            image = np.zeros((thermal_img.shape[0], thermal_img.shape[1], 4))
            image [:,:,0:3] = rgb_img
            image [:,:,3] = thermal_img[:,:,0]
            #"""
        elif format == 'BGR_only':            
            folder = file_name.split('thermal_8_bit/')[0]
            img_name = file_name.split('thermal_8_bit/')[1]
            img_name = img_name.split('.')[0] + '.jpg'
            rgb_path = folder + 'resized_RGB/' + img_name            
            image = cv2.imread(rgb_path)            
        elif format == 'BGRTTT': # middle fusion   
            """
            # KAIST
            folder = file_name.split('visible')[0]
            img_name = file_name.split('visible/')[1]
            path_rgb = file_name
            path_thermal = folder + 'lwir/' + img_name
            img_rgb = cv2.imread(path_rgb)
            img_thermal = cv2.imread(path_thermal)                        
            image = np.zeros((img_thermal.shape[0], img_thermal.shape[1], 6))
            image [:,:,0:3] = img_rgb
            image [:,:,3:] = img_thermal
            """ 
            # FLIR
            folder = file_name.split('thermal_8_bit/')[0]
            img_name = file_name.split('thermal_8_bit/')[-1]
            
            img_name = img_name.split('.')[0] + '.jpg'
            rgb_path = folder + 'RGB/' + img_name                        
            rgb_img = cv2.imread(rgb_path)
            thermal_img = cv2.imread(file_name)

            rgb_img = cv2.resize(rgb_img,(thermal_img.shape[1], thermal_img.shape[0]))
            image = np.zeros((thermal_img.shape[0], thermal_img.shape[1], 6))
            image [:,:,0:3] = rgb_img
            image [:,:,3:6] = thermal_img
            #"""
        elif format == 'BGRTTT_perturb':
            
            folder = file_name.split('thermal_8_bit/')[0]
            img_name = file_name.split('thermal_8_bit/')[1]
            img_name = img_name.split('.')[0] + '.jpg'
            rgb_path = folder + 'RGB/' + img_name                        
            rgb_img = cv2.imread(rgb_path)

            import os
            number = int(file_name.split('video_')[-1].split('.')[0])
            #number = int(file_name.split('FLIR')[-1].split('_')[1].split('.')[0])
            number -= 1
            number_str = '{:05d}'.format(number)
            new_file_name = file_name.split('thermal')[0] + 'thermal_8_bit/FLIR_video_'+number_str+'.jpeg'            
            if os.path.exists(new_file_name):
                thermal_img = cv2.imread(new_file_name)
                print(new_file_name, '  RGB: ', rgb_path)
            else:
                thermal_img = cv2.imread(file_name)
                print(file_name, '  RGB: ', rgb_path)            
            rgb_img = cv2.resize(rgb_img,(thermal_img.shape[1], thermal_img.shape[0]))
            """
            # Random resize
            import random
            ratio = random.randrange(100,121) / 100
            width_new = int(640*ratio+0.5)
            height_new = int(512*ratio+0.5)            
            rgb_img = cv2.resize(rgb_img, (width_new, height_new))
            
            # Random crop
            [height, width, _] = thermal_img.shape
            diff_w = width_new - width
            diff_h = height_new - height
            if diff_w > 0: shift_x = random.randrange(0, diff_w)
            else: shift_x = 0
            if diff_h > 0: shift_y = random.randrange(0, diff_h)
            else: shift_y = 0            
            
            rgb_img = rgb_img[shift_y:shift_y+height, shift_x:shift_x+width, :]
            """
            #import pdb; pdb.set_trace()
            image = np.zeros((thermal_img.shape[0], thermal_img.shape[1], 6))
            image [:,:,0:3] = rgb_img
            image [:,:,3:6] = thermal_img
        elif format == "mid_RGB_out":
            thermal_img = cv2.imread(file_name)
            image = np.zeros((thermal_img.shape[0], thermal_img.shape[1], 6))
            image [:,:,3:6] = thermal_img
        elif format =='T_TCONV':
            #import pdb;pdb.set_trace()
            folder = file_name.split('thermal_8_bit/')[0]
            img_name = file_name.split('thermal_8_bit/')[1]
            img_name = img_name.split('.')[0] + '.jpeg'
            t_conv_path = folder + 'thermal_convert/' + img_name
            t_conv_img = cv2.imread(t_conv_path)
            thermal_img = cv2.imread(file_name)
            image = np.zeros((thermal_img.shape[0], thermal_img.shape[1], 2))
            image [:,:,0] = t_conv_img[:,:,0]
            image [:,:,1] = thermal_img[:,:,0]
        elif format == 'T_TCONV_MASK':
            folder = file_name.split('thermal_convert/')[0]
            img_name = file_name.split('thermal_convert/')[1]
            #img_name = img_name.split('.')[0] + '.jpeg'
            t_conv_path = folder + 'thermal_convert/' + img_name
            t_conv_img = cv2.imread(t_conv_path)
            t_mask_path = folder + 'thermal_analysis/' + file_name.split('thermal_convert/')[1].split(".")[0] + '_mask.jpg'
            mask_img = cv2.imread(t_mask_path)
            thermal_img = cv2.imread(file_name)
            image = np.zeros((thermal_img.shape[0], thermal_img.shape[1], 3))
            image [:,:,0] = t_conv_img[:,:,0]
            image [:,:,1] = thermal_img[:,:,0]
            image [:,:,2] = mask_img[:,:,0]
        elif format == 'UVV': # UV in first two channel, 0 in third channel     
            if 'train' in file_name:
                folder = '../../../Datasets/KAIST/train/KAIST_flow_train_sanitized/'
            else:
                folder = '../../../Datasets/KAIST/test/KAIST_flow_test_sanitized/'
            
            fname = file_name.split('/')[-1].split('.')[0] + '.flo'
            fpath = folder + fname
            flow = readFlow(fpath)
            image = np.zeros((flow.shape[0], flow.shape[1], 3))
            image[:,:,0] = flow[:,:,0]
            image[:,:,1] = flow[:,:,1]
            image[:,:,2] = flow[:,:,1]
            image *= 4.0
            #image += 128.0
            image[image>255] = 255.0
            #pdb.set_trace()
            """
            image = np.abs(image) / 40.0 * 255.0
            image[image>255] = 255.0
            """
        elif format == 'UVM': # UV + magnitude(uv)
            if 'train' in file_name:
                folder = '../../../Datasets/KAIST/train/KAIST_flow_train_sanitized/'
            else:
                folder = '../../../Datasets/KAIST/test/KAIST_flow_test_sanitized/'
            
            fname = file_name.split('/')[-1].split('.')[0] + '.flo'
            fpath = folder + fname
            flow = readFlow(fpath)
            flow_s = flow * flow
            magnitude = np.sqrt(flow_s[:,:,0] + flow_s[:,:,1])

            image = np.zeros((flow.shape[0], flow.shape[1], 3))
            image[:,:,0] = flow[:,:,0]
            image[:,:,1] = flow[:,:,1]
            image[:,:,2] = magnitude
            image *= 4.0
            #image += 128.0
            image[image>255] = 255.0
            """
            image = np.abs(image) / 40.0 * 255.0
            image[image>255] = 255.0
            """
        elif format == 'BGRTUV':
            if 'train' in file_name:
                flow_folder = '../../../Datasets/KAIST/train/KAIST_flow_train_sanitized/'
                img_folder = '../../../Datasets/KAIST/train/'
            else:
                flow_folder = '../../../Datasets/KAIST/test/KAIST_flow_test_sanitized/'
                img_folder = '../../../Datasets/KAIST/test/'
            
            fname = file_name.split('/')[-1].split('.')[0] + '.flo'
            fpath = flow_folder + fname
            flow = readFlow(fpath)
            
            image = np.zeros((flow.shape[0], flow.shape[1], 6))
            image[:,:,4] = flow[:,:,0]
            image[:,:,5] = flow[:,:,1]    
            image *= 3
            image += 128.0
            image[image>255] = 255.0

            set_name = file_name.split('/')[-1].split('_')[0]
            V_name = file_name.split('/')[-1].split('_')[1]
            img_name = file_name.split('/')[-1].split('_')[2]

            fname_bgr = img_folder + set_name + '/' + V_name + '/visible/' + img_name
            fname_thr = img_folder + set_name + '/' + V_name + '/lwir/' + img_name
            bgr = cv2.imread(fname_bgr)
            thr = cv2.imread(fname_thr)

            image[:,:,0:3] = bgr
            image[:,:,3] = thr[:,:,0]
            
        else:
            #import pdb; pdb.set_trace()
            image = Image.open(f)

            # capture and ignore this bug: https://github.com/python-pillow/Pillow/issues/3973
            try:
                image = ImageOps.exif_transpose(image)
            except Exception:
                pass

            if format is not None:
                # PIL only supports RGB, so convert to RGB and flip channels over below
                conversion_format = format
                if format == "BGR":
                    conversion_format = "RGB"
                image = image.convert(conversion_format)
            image = np.asarray(image)
            if format == "BGR":
                # flip channels if needed
                image = image[:, :, ::-1]
            # PIL squeezes out the channel dimension for "L", so make it HWC
            if format == "L":
                image = np.expand_dims(image, -1)
        return image


def check_image_size(dataset_dict, image):
    """
    Raise an error if the image does not match the size specified in the dict.
    """
    if "width" in dataset_dict or "height" in dataset_dict:
        image_wh = (image.shape[1], image.shape[0])
        expected_wh = (dataset_dict["width"], dataset_dict["height"])
        if not image_wh == expected_wh:
            raise SizeMismatchError(
                "Mismatched (W,H){}, got {}, expect {}".format(
                    " for image " + dataset_dict["file_name"]
                    if "file_name" in dataset_dict
                    else "",
                    image_wh,
                    expected_wh,
                )
            )

    # To ensure bbox always remap to original image size
    if "width" not in dataset_dict:
        dataset_dict["width"] = image.shape[1]
    if "height" not in dataset_dict:
        dataset_dict["height"] = image.shape[0]


def transform_proposals(dataset_dict, image_shape, transforms, min_box_side_len, proposal_topk):
    """
    Apply transformations to the proposals in dataset_dict, if any.

    Args:
        dataset_dict (dict): a dict read from the dataset, possibly
            contains fields "proposal_boxes", "proposal_objectness_logits", "proposal_bbox_mode"
        image_shape (tuple): height, width
        transforms (TransformList):
        min_box_side_len (int): keep proposals with at least this size
        proposal_topk (int): only keep top-K scoring proposals

    The input dict is modified in-place, with abovementioned keys removed. A new
    key "proposals" will be added. Its value is an `Instances`
    object which contains the transformed proposals in its field
    "proposal_boxes" and "objectness_logits".
    """
    if "proposal_boxes" in dataset_dict:
        # Transform proposal boxes
        boxes = transforms.apply_box(
            BoxMode.convert(
                dataset_dict.pop("proposal_boxes"),
                dataset_dict.pop("proposal_bbox_mode"),
                BoxMode.XYXY_ABS,
            )
        )
        boxes = Boxes(boxes)
        objectness_logits = torch.as_tensor(
            dataset_dict.pop("proposal_objectness_logits").astype("float32")
        )

        boxes.clip(image_shape)
        keep = boxes.nonempty(threshold=min_box_side_len)
        boxes = boxes[keep]
        objectness_logits = objectness_logits[keep]

        proposals = Instances(image_shape)
        proposals.proposal_boxes = boxes[:proposal_topk]
        proposals.objectness_logits = objectness_logits[:proposal_topk]
        dataset_dict["proposals"] = proposals
        #pdb.set_trace()

def transform_instance_annotations(
    annotation, transforms, image_size, *, keypoint_hflip_indices=None
):
    """
    Apply transforms to box, segmentation and keypoints annotations of a single instance.

    It will use `transforms.apply_box` for the box, and
    `transforms.apply_coords` for segmentation polygons & keypoints.
    If you need anything more specially designed for each data structure,
    you'll need to implement your own version of this function or the transforms.

    Args:
        annotation (dict): dict of instance annotations for a single instance.
            It will be modified in-place.
        transforms (TransformList):
        image_size (tuple): the height, width of the transformed image
        keypoint_hflip_indices (ndarray[int]): see `create_keypoint_hflip_indices`.

    Returns:
        dict:
            the same input dict with fields "bbox", "segmentation", "keypoints"
            transformed according to `transforms`.
            The "bbox_mode" field will be set to XYXY_ABS.
    """
    bbox = BoxMode.convert(annotation["bbox"], annotation["bbox_mode"], BoxMode.XYXY_ABS)
    # Note that bbox is 1d (per-instance bounding box)
    annotation["bbox"] = transforms.apply_box([bbox])[0]
    annotation["bbox_mode"] = BoxMode.XYXY_ABS

    if "segmentation" in annotation:
        # each instance contains 1 or more polygons
        segm = annotation["segmentation"]
        if isinstance(segm, list):
            # polygons
            polygons = [np.asarray(p).reshape(-1, 2) for p in segm]
            annotation["segmentation"] = [
                p.reshape(-1) for p in transforms.apply_polygons(polygons)
            ]
        elif isinstance(segm, dict):
            # RLE
            mask = mask_util.decode(segm)
            mask = transforms.apply_segmentation(mask)
            assert tuple(mask.shape[:2]) == image_size
            annotation["segmentation"] = mask
        else:
            raise ValueError(
                "Cannot transform segmentation of type '{}'!"
                "Supported types are: polygons as list[list[float] or ndarray],"
                " COCO-style RLE as a dict.".format(type(segm))
            )

    if "keypoints" in annotation:
        keypoints = transform_keypoint_annotations(
            annotation["keypoints"], transforms, image_size, keypoint_hflip_indices
        )
        annotation["keypoints"] = keypoints

    return annotation


def transform_keypoint_annotations(keypoints, transforms, image_size, keypoint_hflip_indices=None):
    """
    Transform keypoint annotations of an image.

    Args:
        keypoints (list[float]): Nx3 float in Detectron2 Dataset format.
        transforms (TransformList):
        image_size (tuple): the height, width of the transformed image
        keypoint_hflip_indices (ndarray[int]): see `create_keypoint_hflip_indices`.
    """
    # (N*3,) -> (N, 3)
    keypoints = np.asarray(keypoints, dtype="float64").reshape(-1, 3)
    keypoints[:, :2] = transforms.apply_coords(keypoints[:, :2])

    # This assumes that HorizFlipTransform is the only one that does flip
    do_hflip = sum(isinstance(t, T.HFlipTransform) for t in transforms.transforms) % 2 == 1

    # Alternative way: check if probe points was horizontally flipped.
    # probe = np.asarray([[0.0, 0.0], [image_width, 0.0]])
    # probe_aug = transforms.apply_coords(probe.copy())
    # do_hflip = np.sign(probe[1][0] - probe[0][0]) != np.sign(probe_aug[1][0] - probe_aug[0][0])  # noqa

    # If flipped, swap each keypoint with its opposite-handed equivalent
    if do_hflip:
        assert keypoint_hflip_indices is not None
        keypoints = keypoints[keypoint_hflip_indices, :]

    # Maintain COCO convention that if visibility == 0, then x, y = 0
    # TODO may need to reset visibility for cropped keypoints,
    # but it does not matter for our existing algorithms
    keypoints[keypoints[:, 2] == 0] = 0
    return keypoints


def annotations_to_instances(annos, image_size, mask_format="polygon"):
    """
    Create an :class:`Instances` object used by the models,
    from instance annotations in the dataset dict.

    Args:
        annos (list[dict]): a list of instance annotations in one image, each
            element for one instance.
        image_size (tuple): height, width

    Returns:
        Instances:
            It will contain fields "gt_boxes", "gt_classes",
            "gt_masks", "gt_keypoints", if they can be obtained from `annos`.
            This is the format that builtin models expect.
    """
    boxes = [BoxMode.convert(obj["bbox"], obj["bbox_mode"], BoxMode.XYXY_ABS) for obj in annos]
    target = Instances(image_size)
    boxes = target.gt_boxes = Boxes(boxes)
    boxes.clip(image_size)

    classes = [obj["category_id"] for obj in annos]
    classes = torch.tensor(classes, dtype=torch.int64)
    target.gt_classes = classes

    if len(annos) and "segmentation" in annos[0]:
        segms = [obj["segmentation"] for obj in annos]
        if mask_format == "polygon":
            masks = PolygonMasks(segms)
        else:
            assert mask_format == "bitmask", mask_format
            masks = []
            for segm in segms:
                if isinstance(segm, list):
                    # polygon
                    masks.append(polygons_to_bitmask(segm, *image_size))
                elif isinstance(segm, dict):
                    # COCO RLE
                    masks.append(mask_util.decode(segm))
                elif isinstance(segm, np.ndarray):
                    assert segm.ndim == 2, "Expect segmentation of 2 dimensions, got {}.".format(
                        segm.ndim
                    )
                    # mask array
                    masks.append(segm)
                else:
                    raise ValueError(
                        "Cannot convert segmentation of type '{}' to BitMasks!"
                        "Supported types are: polygons as list[list[float] or ndarray],"
                        " COCO-style RLE as a dict, or a full-image segmentation mask "
                        "as a 2D ndarray.".format(type(segm))
                    )
            masks = BitMasks(torch.stack([torch.from_numpy(x) for x in masks]))
        target.gt_masks = masks

    if len(annos) and "keypoints" in annos[0]:
        kpts = [obj.get("keypoints", []) for obj in annos]
        target.gt_keypoints = Keypoints(kpts)

    return target


def annotations_to_instances_rotated(annos, image_size):
    """
    Create an :class:`Instances` object used by the models,
    from instance annotations in the dataset dict.
    Compared to `annotations_to_instances`, this function is for rotated boxes only

    Args:
        annos (list[dict]): a list of instance annotations in one image, each
            element for one instance.
        image_size (tuple): height, width

    Returns:
        Instances:
            Containing fields "gt_boxes", "gt_classes",
            if they can be obtained from `annos`.
            This is the format that builtin models expect.
    """
    boxes = [obj["bbox"] for obj in annos]
    target = Instances(image_size)
    boxes = target.gt_boxes = RotatedBoxes(boxes)
    boxes.clip(image_size)

    classes = [obj["category_id"] for obj in annos]
    classes = torch.tensor(classes, dtype=torch.int64)
    target.gt_classes = classes

    return target


def filter_empty_instances(instances, by_box=True, by_mask=True):
    """
    Filter out empty instances in an `Instances` object.

    Args:
        instances (Instances):
        by_box (bool): whether to filter out instances with empty boxes
        by_mask (bool): whether to filter out instances with empty masks

    Returns:
        Instances: the filtered instances.
    """
    assert by_box or by_mask
    r = []
    if by_box:
        r.append(instances.gt_boxes.nonempty())
    if instances.has("gt_masks") and by_mask:
        r.append(instances.gt_masks.nonempty())

    # TODO: can also filter visible keypoints

    if not r:
        return instances
    m = r[0]
    for x in r[1:]:
        m = m & x
    return instances[m]


def create_keypoint_hflip_indices(dataset_names):
    """
    Args:
        dataset_names (list[str]): list of dataset names
    Returns:
        ndarray[int]: a vector of size=#keypoints, storing the
        horizontally-flipped keypoint indices.
    """

    check_metadata_consistency("keypoint_names", dataset_names)
    check_metadata_consistency("keypoint_flip_map", dataset_names)

    meta = MetadataCatalog.get(dataset_names[0])
    names = meta.keypoint_names
    # TODO flip -> hflip
    flip_map = dict(meta.keypoint_flip_map)
    flip_map.update({v: k for k, v in flip_map.items()})
    flipped_names = [i if i not in flip_map else flip_map[i] for i in names]
    flip_indices = [names.index(i) for i in flipped_names]
    return np.asarray(flip_indices)


def gen_crop_transform_with_instance(crop_size, image_size, instance):
    """
    Generate a CropTransform so that the cropping region contains
    the center of the given instance.

    Args:
        crop_size (tuple): h, w in pixels
        image_size (tuple): h, w
        instance (dict): an annotation dict of one instance, in Detectron2's
            dataset format.
    """
    crop_size = np.asarray(crop_size, dtype=np.int32)
    bbox = BoxMode.convert(instance["bbox"], instance["bbox_mode"], BoxMode.XYXY_ABS)
    center_yx = (bbox[1] + bbox[3]) * 0.5, (bbox[0] + bbox[2]) * 0.5
    assert (
        image_size[0] >= center_yx[0] and image_size[1] >= center_yx[1]
    ), "The annotation bounding box is outside of the image!"
    assert (
        image_size[0] >= crop_size[0] and image_size[1] >= crop_size[1]
    ), "Crop size is larger than image size!"

    min_yx = np.maximum(np.floor(center_yx).astype(np.int32) - crop_size, 0)
    max_yx = np.maximum(np.asarray(image_size, dtype=np.int32) - crop_size, 0)
    max_yx = np.minimum(max_yx, np.ceil(center_yx).astype(np.int32))

    y0 = np.random.randint(min_yx[0], max_yx[0] + 1)
    x0 = np.random.randint(min_yx[1], max_yx[1] + 1)
    return T.CropTransform(x0, y0, crop_size[1], crop_size[0])


def check_metadata_consistency(key, dataset_names):
    """
    Check that the datasets have consistent metadata.

    Args:
        key (str): a metadata key
        dataset_names (list[str]): a list of dataset names

    Raises:
        AttributeError: if the key does not exist in the metadata
        ValueError: if the given datasets do not have the same metadata values defined by key
    """
    if len(dataset_names) == 0:
        return
    logger = logging.getLogger(__name__)
    entries_per_dataset = [getattr(MetadataCatalog.get(d), key) for d in dataset_names]
    for idx, entry in enumerate(entries_per_dataset):
        if entry != entries_per_dataset[0]:
            logger.error(
                "Metadata '{}' for dataset '{}' is '{}'".format(key, dataset_names[idx], str(entry))
            )
            logger.error(
                "Metadata '{}' for dataset '{}' is '{}'".format(
                    key, dataset_names[0], str(entries_per_dataset[0])
                )
            )
            raise ValueError("Datasets have different metadata '{}'!".format(key))


def build_transform_gen(cfg, is_train):
    """
    Create a list of :class:`TransformGen` from config.
    Now it includes resizing and flipping.

    Returns:
        list[TransformGen]
    """
    if is_train:
        min_size = cfg.INPUT.MIN_SIZE_TRAIN
        max_size = cfg.INPUT.MAX_SIZE_TRAIN
        sample_style = cfg.INPUT.MIN_SIZE_TRAIN_SAMPLING
    else:
        min_size = cfg.INPUT.MIN_SIZE_TEST
        max_size = cfg.INPUT.MAX_SIZE_TEST
        sample_style = "choice"
    if sample_style == "range":
        assert len(min_size) == 2, "more than 2 ({}) min_size(s) are provided for ranges".format(
            len(min_size)
        )

    logger = logging.getLogger(__name__)
    tfm_gens = []
    tfm_gens.append(T.ResizeShortestEdge(min_size, max_size, sample_style))
    if is_train:
        tfm_gens.append(T.RandomFlip())
        logger.info("TransformGens used in training: " + str(tfm_gens))
    return tfm_gens
