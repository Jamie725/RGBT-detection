# import some common detectron2 utilities
from detectron2.engine import DefaultPredictor, DefaultTrainer
from detectron2.config import get_cfg
from detectron2.utils.visualizer import Visualizer
from detectron2.data import DatasetCatalog, MetadataCatalog
from detectron2.data.datasets import register_coco_instances
from detectron2.evaluation import FLIREvaluator, inference_on_dataset
from detectron2.data import build_detection_test_loader
from tools.plain_train_net import do_test
from os import listdir
from os.path import isfile, join
import numpy as np
import cv2
import os
import pdb
import torch
import pdb
from detectron2.data import build_detection_train_loader
from detectron2.data import transforms as T
from detectron2.data import detection_utils as utils

def test(cfg, dataset_name):
    
    cfg.DATASETS.TEST = (dataset_name, )
    predictor = DefaultPredictor(cfg)
    evaluator_FLIR = FLIREvaluator(dataset_name, cfg, False, output_dir=out_folder, out_pr_name='pr_val.png')
    #DefaultTrainer.test(cfg, trainer.model, evaluators=evaluator_FLIR)
    val_loader = build_detection_test_loader(cfg, dataset_name)
    inference_on_dataset(predictor.model, val_loader, evaluator_FLIR)

#Set GPU
torch.cuda.set_device(0)

# get path
dataset = 'FLIR'
# Train path
train_path = '../../../Datasets/'+ dataset +'/train/'
train_folder = '../../../Datasets/FLIR/train/'
train_json_path = '../../../Datasets/'+dataset+'/train/thermal_annotations_4_channel_no_dogs_3_class.json'
# Validation path
val_path = '../../../Datasets/'+ dataset +'/val/'
val_folder = '../../../Datasets/FLIR/val/'
val_json_path = '../../../Datasets/'+dataset+'/val/thermal_annotations_4_channel_no_dogs_3_class.json'
print(train_json_path)

# Register dataset
dataset_train = 'FLIR_train'
register_coco_instances(dataset_train, {}, train_json_path, train_folder)
FLIR_metadata_train = MetadataCatalog.get(dataset_train)
dataset_dicts_train = DatasetCatalog.get(dataset_train)

# Test on validation set
dataset_test = 'FLIR_val'
register_coco_instances(dataset_test, {}, val_json_path, val_folder)
FLIR_metadata_test = MetadataCatalog.get(dataset_test)
dataset_dicts_test = DatasetCatalog.get(dataset_test)

model = 'faster_rcnn_R_101_FPN_3x'

#files_names = [f for f in listdir(train_path) if isfile(join(train_path, f))]

out_folder = 'output_mid_fusion_3_class_1'
out_model_path = os.path.join(out_folder, 'out_model_final.pth')
if not os.path.exists(out_folder):
    os.mkdir(out_folder)

# Create config
cfg = get_cfg()
cfg.OUTPUT_DIR = out_folder
cfg.merge_from_file("./configs/FLIR-Detection/faster_rcnn_R_101_FLIR.yaml")
cfg.MODEL.ROI_HEADS.SCORE_THRESH_TEST = 0.5  # set threshold for this model
# Open middle level fusion
# Train config
cfg.DATASETS.TRAIN = (dataset_train,)
cfg.DATASETS.TEST = (dataset_test, )
#cfg.TEST.EVAL_PERIOD = 50
cfg.MODEL.ROI_HEADS.BATCH_SIZE_PER_IMAGE = 512   # faster, and good enough for this toy dataset (default: 512)
cfg.MODEL.ROI_HEADS.NUM_CLASSES = 3
cfg.MODEL.ROI_HEADS.SCORE_THRESH_TEST = 0.5   # set the testing threshold for this model

###### Performance tuning ########
cfg.SOLVER.IMS_PER_BATCH = 2
cfg.SOLVER.BASE_LR = 0.001  # pick a good LR
cfg.SOLVER.MAX_ITER = 50000

#-------------------------------------------- Get pretrained RGB parameters -------------------------------------#
###### Parameter for RGB channel input ####
cfg.MODEL.WEIGHTS = "detectron2://COCO-Detection/faster_rcnn_R_101_FPN_3x/137851257/model_final_f6e8b1.pkl"
cfg.MODEL.BACKBONE.FREEZE_AT = 0
cfg.INPUT.FORMAT = 'BGR'
cfg.INPUT.NUM_IN_CHANNELS = 3
cfg.MODEL.PIXEL_MEAN = [103.530, 116.280, 123.675]
cfg.MODEL.PIXEL_STD = [1.0, 1.0, 1.0]
#cfg.MODEL.BLUR_RGB = True
cfg.MODEL.MAX_POOL_RGB = False
#########################################

os.makedirs(cfg.OUTPUT_DIR, exist_ok=True)

from detectron2.modeling import build_model
model_ther = build_model(cfg)
param_thr = list(model_ther.backbone.bottom_up.stem.parameters())
param_thr = param_thr[0]
param_backbone = list(model_ther.backbone.parameters())
param_roi = list(model_ther.roi_heads.parameters())
param_rpn_head = list(model_ther.proposal_generator.rpn_head.parameters())
del model_ther
########### Parameters for thermal ##############
# Get thermal weights
cfg.MODEL.WEIGHTS = 'good_model/3_class/thermal_only/out_model_iter_15000.pth'
model_ther = build_model(cfg)
param_backbone_2 = list(model_ther.backbone.parameters())
del model_ther
#-------------------------------------------------- End --------------------------------------------------#
# for 6 inputs
param_rgb = param_thr.clone()
param_rgb = param_rgb.data.fill_(0)
param_cat = torch.cat((param_rgb, param_thr), 1)

# Set for training 6 inputs
cfg.INPUT.FORMAT = 'BGRTTT'
cfg.INPUT.NUM_IN_CHANNELS = 6 #4
cfg.MODEL.PIXEL_MEAN = [103.530, 116.280, 123.675, 135.438, 135.438, 135.438]
cfg.MODEL.PIXEL_STD = [1.0, 1.0, 1.0, 1.0, 1.0, 1.0]
cfg.MODEL.WEIGHTS = "detectron2://COCO-Detection/faster_rcnn_R_101_FPN_3x/137851257/model_final_f6e8b1.pkl"

eval_every_iter = 1000
num_loops = cfg.SOLVER.MAX_ITER // eval_every_iter
cfg.SOLVER.MAX_ITER = eval_every_iter
cfg.DATALOADER.NUM_WORKERS = 2
trainer = DefaultTrainer(cfg)
trainer.resume_or_load(resume=False)
cnt = 0

with torch.no_grad():
    trainer.model.backbone.weight = param_backbone
    trainer.model.backbone_2.weight = param_backbone_2
    trainer.model.backbone.bottom_up.stem.weight = param_cat
    print("----Done loading parameters !!---")
del param_backbone, param_backbone_2, param_rpn_head, param_roi, param_rgb, param_thr, param_cat

for idx in range(num_loops):
    print('============== The ', idx, ' * ', eval_every_iter, ' iterations ============')    
    
    if idx > 0:
        cfg.MODEL.WEIGHTS = out_model_path
        trainer = DefaultTrainer(cfg)
        trainer.resume_or_load(resume=False)
        
        out_name = 'out_model_iter_'+ str(idx*eval_every_iter) +'.pth'
        out_model_path = os.path.join(out_folder, out_name)
    trainer.train()
    torch.save(trainer.model.state_dict(), out_model_path)
    cfg.MODEL.WEIGHTS = out_model_path
    # Evaluation on validation set
    test(cfg, dataset_train)
    test(cfg, dataset_test)
    del trainer
