import os, sys, time, h5py
import numpy as np
import cv2


def preprocess(depth_img):
    depth_img_rescaled = None
    if depth_img.dtype == np.uint16:
        # convert depth image from mili-meters to meters
        depth_img_rescaled = cv2.rgbd.rescaleDepth(depth_img, cv2.CV_32FC1)
    elif depth_img.dtype == np.float32:
        depth_img_rescaled = depth_img
    else:
        print("Unknown depth image encoding.")
        return None

    kZeroValue = 0.0
    nan_mask = (depth_img_rescaled != depth_img_rescaled)
    depth_img_rescaled[nan_mask] = kZeroValue # set nan pixels to 0

    return depth_img_rescaled


def checkSegmentFramesEqual(segs_framesA, segs_framesB):
    if(len(segs_framesA)!=len(segs_framesB)):
        print(" Not Equal, length of segment lists")
        return False
    for f_i, seg_A in enumerate(segs_framesA):
        seg_B = segs_framesB[f_i]
        # print("     check seg num %d "%(f_i))
        if(not np.isclose(seg_A.pose,seg_B.pose).all()):
            print("    Not Equal pose in %d frame "%(f_i))
            return False
        if(not np.isclose(seg_A.center,seg_B.center).all()):
            print("    Not Equal center in %d frame "%(f_i))
            return False
        if(not np.isclose(seg_A.points,seg_B.points, atol=1e-4).all()):
            print("    Not Equal points in %d frame "%(f_i))
            return False
        if(not np.isclose(seg_A.inst_confidence,seg_B.inst_confidence).all()):
            print("    Not Equal label_confidence in %d frame "%(f_i))
            return False
        if(not np.isclose(seg_A.overlap_ratio,seg_B.overlap_ratio).all()):
            print("    Not Equal label_confidence in %d frame "%(f_i))
            return False
        if((seg_A.instance_label!=seg_B.instance_label)):
            print("    Not Equal instance_label in %d frame "%(f_i))
            return False
        if((seg_A.class_label!=seg_B.class_label)):
            print("    Not Equal class_label in %d frame "%(f_i))
            return False
        if((seg_A.is_thing!=seg_B.is_thing)):
            print("    Not Equal class_label in %d frame "%(f_i))
            return False
    return True

def isPoseValid(pose):
    is_nan = np.isnan(pose).any() or np.isinf(pose).any()
    if is_nan:
        return False

    R_matrix = pose[:3, :3]
    I = np.identity(3)
    is_rotation_valid = ( np.isclose( np.matmul(R_matrix, R_matrix.T), I , atol=1e-3) ).all and np.isclose(np.linalg.det(R_matrix) , 1, atol=1e-3)
    if not is_rotation_valid:
        return False

    return True


def dictToHd5(file, dict):
	f = h5py.File(file,'w')
	for key in dict:
		f[key] = dict[key]
	f.close() 
	return None

def hd5ToDict(file):
	f = h5py.File(file,'r')
	dict = {}
	for key in f:
		dict[key] = np.array(f[key])
	f.close() 
	return dict


def getHostId(gpu_id):
    HOST = str(gpu_id) + ".0.0."+str(gpu_id)
    return HOST

def getGpuDevice(gpu_id, gpu_num):
    assert(gpu_id >= 0)
    assert(gpu_num > gpu_id)
    if(gpu_num == 1):
        return "cuda"
    return "cuda:"+str(gpu_id)