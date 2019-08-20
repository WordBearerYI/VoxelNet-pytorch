from __future__ import division
from __future__ import print_function
from __future__ import with_statement
from __future__ import absolute_import

import time
import os
import sys
import yaml
from tqdm import tqdm
import numpy as np
from glob import glob
import torch.nn.functional as F
import cv2
from utils.utils import *
from utils.coord_transform import *
from utils.nms import nms
from data.data import KITDataset 
from box_overlaps import bbox_overlaps
from data_aug import aug_data

from VoxelNet import VoxelNet,weights_init
from VoxelLoss import VoxelLoss

from torch.autograd import Variable
import torch
import torch.utils.data as data
import torch.backends.cudnn
import torch.optim as optim
import torch.nn.init as init
import warnings
warnings.filterwarnings("ignore")

yamlPath = "configure.yaml"
f = open(yamlPath, 'r', encoding='utf-8')
conf = f.read()
conf_dict = yaml.safe_load(conf) 

if_cuda = True if conf_dict["if_cuda"] == 1 else False
classes = conf_dict["classes"]
chk_pth = "/home/screentest/ys3237/VoxelNet-pytorch/checkpoints/chk_Car_Van_35.pth"

if if_cuda:
    os.environ["CUDA_VISIBLE_DEVICES"] = "0"

print("-"*20)
print("if_cuda:",if_cuda)

def detection_collate(batch):
    voxel_features = []
    voxel_coords = []
    pos_equal_one = []
    neg_equal_one = []
    targets = []
    images = []
    calibs = []
    ids = []
    
    for i, sample in enumerate(batch):
        voxel_features.append(sample[0])
        voxel_coords.append(
            np.pad(sample[1], ((0, 0), (1, 0)),
                mode='constant', constant_values=i))

        pos_equal_one.append(sample[2])
        neg_equal_one.append(sample[3])
        targets.append(sample[4])

        images.append(sample[5])
        calibs.append(sample[6])
        ids.append(sample[7])
    return np.concatenate(voxel_features), np.concatenate(voxel_coords), \
           np.array(pos_equal_one),np.array(neg_equal_one),\
           np.array(targets), images, calibs, ids


def inference(setting="val"):#test,val
    kit_dataset= KITDataset(conf_dict=conf_dict,setting="val")#test,val
    kit_data_loader = data.DataLoader(kit_dataset, batch_size=1, num_workers=4,collate_fn=detection_collate,pin_memory=True)

    print('Loading pre-trained weights...')
    #chk = glob(chk_pth+'/*')[-1]
    net = VoxelNet()
    if if_cuda:
        net.cuda()
    net.load_state_dict(torch.load(chk_pth))
    net.eval()
    for batch_index, contents in enumerate(tqdm(kit_data_loader)):
        voxel_features, voxel_coords, pos_equal_one, neg_equal_one, gt_box3d, images, calibs, ids = contents
         # wrapper to variable
        
        #print(np.shape(voxel_features),np.shape(voxel_coords))
        voxel_features = Variable(torch.FloatTensor(voxel_features))
        if if_cuda:
            voxel_features = voxel_features.cuda()
            #pos_equal_one = Variable(torch.cuda.FloatTensor(pos_equal_one))
            #neg_equal_one = Variable(torch.cuda.FloatTensor(neg_equal_one))
            #targets = Variable(torch.cuda.FloatTensor(targets))
            #pos_equal_one = Variable(torch.FloatTensor(pos_equal_one))
            #neg_equal_one = Variable(torch.FloatTensor(neg_equal_one))
            #targets = Variable(torch.FloatTensor(targets))

            # zero the parameter gradients
 
        psm, rm = net(voxel_features, voxel_coords)
        
        rm = rm.permute(0,2,3,1).contiguous()
        rm = rm.view(rm.size(0),rm.size(1),rm.size(2),-1,7)
          #([batch, 200, 176, 2, 7])  
        rm_pos = rm.view(-1,7).detach().cpu().numpy()
        print(rm_pos)
        p_pos = F.sigmoid(psm.permute(0,2,3,1))#([batch, 200, 176, 2])
        p_pos = p_pos.view(-1,1).detach().cpu().numpy()
        print(p_pos)
        p_index = p_pos.argsort(axis=0)[-200:][::-1]
        print(p_pos[p_index])
        p = p_pos[p_index].squeeze(-1)
        print(rm_pos[p_index].squeeze(1),np.shape(rm_pos[p_index].squeeze(1)))
        rm = anchors_center_to_corner(rm_pos[p_index].squeeze(1))
        print(rm,np.shape(rm))
        rm_bev = corner_to_standup_box2d_batch(rm)
        print(np.shape(rm_bev),np.shape(p))
        bboxes_bev = np.concatenate((rm_bev,p),axis=1)
        print(bboxes_bev[:10,:])
        print(np.shape(bboxes_bev))
        bboxes_final = bboxes_bev[nms(bboxes_bev,0.3)]
        print(np.shape(bboxes_final))
        print(bboxes_final)
        print(gt_box3d)
        
        file_name = ids[0].split('/')[-1].split('.')[0]
        log_file = open("/home/screentest/ys3237/VoxelNet-pytorch/predicts/"+setting+'_'+file_name+'.txt','w+')
        for i in bboxes_final:
            items = list(map(lambda x:str(x),list(i)))
            print(items)
            
            log_file.write(','.join(items)+'\n')
        log_file.close()
    
if __name__ == '__main__':
    
      inference()
    
    
    
