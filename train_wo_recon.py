import torch
import torch.nn as nn
import torch.utils.data
import torch.optim as optim
import torch.nn.functional as F
# from torchvision import transforms, utils
import numpy as np
from model import Reconstruction, TriangleNet
from dataloader import load_data, ModelNetDataLoader
from tqdm import tqdm
import argparse
from dataloader import *
from OFFDataLoader import *
from torchvision import transforms, utils
from pathlib import Path



parser = argparse.ArgumentParser('Triangle-Net')
parser.add_argument('--batch_size', type=int, default=8, help='batch size')
parser.add_argument('--datapath', type=str, default=r'./data/modelnet40_ply_hdf5_2048/', help='path of modelnet 40 dataset')
parser.add_argument('--offpath', type=str, default="mesh_data/ModelNet40", help='path of modelnet 40 dataset')

parser.add_argument('--episodes', type=int, default=1000)
parser.add_argument('--n_points', type=int, default=1024)
parser.add_argument('--descriptor_type', type=str, default='C', help='[A, B, C]')
parser.add_argument('--rot_type', type=str, default='SO3', help='[SO3, z]')
args = parser.parse_args()

datapath = args.datapath
batch_size = args.batch_size
train_episodes = args.episodes
descriptor_type = args.descriptor_type
n_points = args.n_points
rot_type = args.rot_type
OFF_Path = Path(args.offpath)

################################### OFF DataLoader #########################################################

train_OFF_transforms = transforms.Compose([
    PointSampler(1024),
    Normalize(),
    RandomNoise()
    # ToTensor()
])

test_OFF_transforms = transforms.Compose([
    PointSampler(1024),
    Normalize(),
    RandomNoise()
    # ToTensor()
])

train_OFF_dataset = PointCloudData(OFF_Path, transform=train_OFF_transforms)
test_OFF_dataset = PointCloudData(OFF_Path,valid=True, folder='test', transform=test_OFF_transforms)
# print(type(train_OFF_dataset[0]))
# print(len(train_OFF_dataset))
# print(train_OFF_dataset[0].shape)
pointcloud, label = train_OFF_dataset[0]
# print(pointcloud.shape)
# print(label)
# print(type(train_OFF_dataset[0]["pointcloud"]))
# print(train_OFF_dataset[1000]["pointcloud"])
# print(train_OFF_dataset[1000]["category"])

num_train = len(train_OFF_dataset)
num_test = len(test_OFF_dataset)

train_data_new = np.ndarray((num_train, 1024, 3))
train_label_new = np.ndarray((num_train, 1))
test_data_new = np.ndarray((num_test, 1024, 3))
test_label_new = np.ndarray((num_test, 1))

for i in range(1):
    print("Loading PointCloud Training Data.............................")
    print(str(i) +  '/ ' + str(num_train))
    train_data_new[i], train_label_new[i] = train_OFF_dataset[i]

for i in range(1):
    print("Loading PointCloud Test Data.............................")
    print(str(i) +  '/ ' + str(num_test))
    test_data_new[i], test_data_new[i] = train_OFF_dataset[i]


###########################################################################################################
# Original Data Loader
# train_data, train_label, test_data, test_label = load_data(datapath, classification=True)
# print(type(train_data))
# print(train_data.shape)
# print(train_label.shape)

# trainDataset = ModelNetDataLoader(train_data, train_label, use_voxel=True, point_num = n_points, rot_type=rot_type)
trainDataset = ModelNetDataLoader(train_data_new, train_label_new, use_voxel=False, point_num = n_points, rot_type=rot_type)
testDataset = ModelNetDataLoader(test_data_new, test_label_new, use_voxel=False, point_num = n_points, rot_type=rot_type)
trainDataLoader = torch.utils.data.DataLoader(trainDataset, batch_size=batch_size, shuffle=True) #, num_workers = 6
testDataLoader = torch.utils.data.DataLoader(testDataset, batch_size=batch_size, shuffle=True) #, num_workers = 6

inp_lookup={"A":4,"B":12,"C":24}
net = TriangleNet(k=40, inp=inp_lookup[descriptor_type], descriptor_type=descriptor_type, scale_invariant=True).cuda()

optimizer_tri = optim.Adam(net.parameters(), lr=0.001, betas=(0.5, 0.999),weight_decay = 1e-4)

bestacc=0

for ep in range(train_episodes):
    print("episode", ep)
    net = net.train()
    for i, (points, norms, target) in tqdm(enumerate(trainDataLoader), total=len(trainDataLoader)):
        optimizer_tri.zero_grad()

        target = target[:, 0]
        target = target.cuda()
        points = points.cuda()
        norms = norms.cuda()

        pred, z = net(points,norms)
        loss = F.nll_loss(pred, target.long())
        loss.backward()
        optimizer_tri.step()

    net = net.eval()
    total_cnt=0
    correct_cnt=0
    for i, (points, norms, target) in enumerate(testDataLoader):

        points = points.cuda()
        norms = norms.cuda()
        target = target[:, 0]
        target = target.cuda()
        with torch.no_grad():
            pred, z = net(points, norms)
        pred_choice = pred.data.max(1)[1]
        correct = pred_choice.eq(target.long().data).cpu().sum()
        correct_cnt +=correct.item()
        total_cnt+=points.shape[0]
    test_acc =  correct_cnt/total_cnt
    if test_acc > bestacc:
        bestacc = test_acc
        torch.save(net, f"/log/best_net_{test_acc}_{n_points}.pth")

    print("test acc: ",test_acc, "best test acc: ", bestacc)

