import os, sys, time, threading, h5py
import numpy as np
from scipy.spatial.transform import Slerp, Rotation
import cv2
from collections import Counter

import sys
sys.path.append("/usr/lib/python3/dist-packages")
import pcl

# self packages
from semantics.pano_scannet_colormap import *
from utils.common_utils import preprocess, isPoseValid, dictToHd5, hd5ToDict


class Segment:
    def __init__(self, points, is_thing, instance_label, class_label, \
            inst_confidence, overlap_ratio, pose, index, center = None):

        self.points = points.astype(np.float32).reshape(-1,3)
        self.is_thing = is_thing
        self.instance_label = np.float32(instance_label)
        self.class_label= class_label
        self.inst_confidence = np.float32(inst_confidence)
        self.overlap_ratio = np.float32(overlap_ratio)
        self.pose = pose.astype(np.float32)
        self.index = index
        self.geometry_confidence = None

        if center is None:  
            self.center = np.mean(self.points, axis=0).astype(np.float32).reshape(1,3)
        else:
            self.center = center.astype(np.float32).reshape(1,3)
        self.box_points = np.zeros((1,3))

    def calculateConfidenceDefault(self, weight=0.5):
        self.geometry_confidence = np.ones((1,self.points.shape[0])).reshape(1,-1).astype(np.float32)

    def calculateBBox(self, voxel_grid = 0.02, sampling_dist = 0.025):
        seg_pcl = pcl.PointCloud(self.points)
        # sparsify pcl
        pcl_sparse_filter = seg_pcl.make_voxel_grid_filter()
        pcl_sparse_filter.set_leaf_size(voxel_grid,voxel_grid,voxel_grid)
        seg_pcl_voxel = pcl_sparse_filter.filter()
        # remove outlier
        pcl_filter = seg_pcl_voxel.make_statistical_outlier_filter()
        pcl_filter.set_mean_k (10)
        pcl_filter.set_std_dev_mul_thresh (2.0)
        pcl_filtered =  pcl_filter.filter()
        # calculate boundiing box
        Bbox_extractor = pcl.MomentOfInertiaEstimation()
        Bbox_extractor.set_InputCloud(pcl_filtered)
        Bbox_extractor.compute()
        min_point_OBB, max_point_OBB, position_OBB, rotational_matrix_OBB = Bbox_extractor.get_OBB()

        len_wid_hei_half = np.array(max_point_OBB).reshape(-1)
        sampling_num_x = int( max( np.floor(len_wid_hei_half[0]*2/sampling_dist -1), 1) )
        sampling_num_y = int( max( np.floor(len_wid_hei_half[1]*2/sampling_dist -1), 1) )
        sampling_num_z = int( max( np.floor(len_wid_hei_half[2]*2/sampling_dist -1), 1) )

        Bbox_vertices_unit = [
            [0,0,0], # box center
            [1,1,1], # v1
            [-1,1,1], # v2
            [-1,1,-1], # v3
            [1,1,-1], # v4
            [1,-1,1], # v5
            [-1,-1,1], # v6
            [-1,-1,-1], # v7
            [1,-1,-1] # v8
        ]
        x_sample_range = np.interp(np.array(range(sampling_num_x)), [0,sampling_num_x], [-1,1])
        y_sample_range = np.interp(np.array(range(sampling_num_y)), [0,sampling_num_y], [-1,1])
        z_sample_range = np.interp(np.array(range(sampling_num_z)), [0,sampling_num_z], [-1,1])

        Bbox_vertices_unit.extend([[x_sample, 1, 1] for x_sample in x_sample_range]) # samples between v1-v2
        Bbox_vertices_unit.extend([[-1, 1, z_sample] for z_sample in z_sample_range]) # samples between v2-v3
        Bbox_vertices_unit.extend([[x_sample, 1, -1] for x_sample in x_sample_range]) # samples between v3-v4
        Bbox_vertices_unit.extend([[1, 1, z_sample] for z_sample in z_sample_range]) # samples between v4-v1
        Bbox_vertices_unit.extend([[1, y_sample, 1] for y_sample in y_sample_range]) # samples between v1-v5
        Bbox_vertices_unit.extend([[-1, y_sample, 1] for y_sample in y_sample_range]) # samples between v2-v6
        Bbox_vertices_unit.extend([[-1, y_sample, -1] for y_sample in y_sample_range]) # samples between v3-v7
        Bbox_vertices_unit.extend([[1, y_sample, -1] for y_sample in y_sample_range]) # samples between v4-v8
        Bbox_vertices_unit.extend([[x_sample, -1, 1] for x_sample in x_sample_range]) # samples between v5-v6
        Bbox_vertices_unit.extend([[-1, -1, z_sample] for z_sample in z_sample_range]) # samples between v6-v7
        Bbox_vertices_unit.extend([[x_sample, -1, -1] for x_sample in x_sample_range]) # samples between v7-v8
        Bbox_vertices_unit.extend([[1, -1, z_sample] for z_sample in z_sample_range]) # samples between v8-v5
        Bbox_vertices_unit = np.array(Bbox_vertices_unit).reshape(-1,3)

        Bbox_vertices_AA = Bbox_vertices_unit*np.repeat(np.abs(max_point_OBB), Bbox_vertices_unit.shape[0], axis=0) # (n, 3)
        Bbox_vertices_Orient =  (Bbox_vertices_AA@rotational_matrix_OBB.T) + position_OBB.reshape(1,3)
        self.box_points = (Bbox_vertices_Orient).reshape(-1,3).astype(np.float32) # (n, 3)

class SegmentsGenerator:
    def __init__(self, gsm_node, depth_segmentor, panoptic_segmentor, \
        save_resutls_img=False, img_folder = None, \
        save_segments = False, use_segments = False, segments_folder = None):
        
        self.gsm_node = gsm_node
        self.depth_segmentor = depth_segmentor
        self.panoptic_segmentor = panoptic_segmentor

        self.save_resutls_img = save_resutls_img
        self.img_folder = img_folder
        if self.save_resutls_img:
            self.semantic_folder = os.path.join(self.img_folder, 'panoptic_seg')
            # self.depth_seg_folder = os.path.join(self.img_folder, 'depth_seg')
            if not os.path.exists(self.semantic_folder):
                os.makedirs(self.semantic_folder)
            # depth_seg is the same as semantic_mapping, so no need to save again
            # if not os.path.exists(self.depth_seg_folder):
            #     os.makedirs(self.depth_seg_folder)

        self.save_segments = save_segments
        self.use_segments =use_segments
        self.segments_folder = segments_folder
        if(self.save_segments and self.segments_folder is not None):
            if not os.path.exists(self.segments_folder):
                os.makedirs(self.segments_folder)
        else:
            self.save_segments = False
        return None

    def Segmennt2D(self, depth_img, rgb_img, frame_i):
        result = None
        # panoptic segmentation
        panoptic_result = self.panoptic_segmentor.forward(rgb_img)
        if len(panoptic_result['info']) == 0:
            return result
        
        # depth segmentation
        depth_img_scaled = preprocess(depth_img)
        self.depth_segmentor.depthSegment(depth_img_scaled,rgb_img.astype(np.float32))
        depth_map = self.depth_segmentor.get_depthMap()
        # normal_map = self.depth_segmentor.get_normalMap()
        segment_masks =  self.depth_segmentor.get_segmentMasks()
        if len(segment_masks) == 0:
            return result

        # extract instance/stuff information 
        id2info_instance = {}
        id2info_stuff = {}
        seg_map = panoptic_result['seg_map']
        for id_info in panoptic_result['info']:
            id = id_info['id']
            is_thing = id_info['isthing']
            if is_thing:
                # instance
                id2info_instance[id] = id_info

                x1, y1, x2, y2 = panoptic_result['boxes'][id-1]
                x1, y1, x2, y2 = int(np.floor(x1)), int(np.floor(y1)), int(np.ceil(x2)) , int(np.ceil(y2))
                area = np.sum(seg_map == id)
                id2info_instance[id]['area'] = area
                id2info_instance[id]['box'] = (x1, y1, x2, y2)
            else:
                # stuff
                id2info_stuff[id] = id_info.copy()
                id2info_stuff[id]['category_id'] += 80

        if self.save_resutls_img:
            semantic_vis = self.panoptic_segmentor.visualize(panoptic_result)
            # label_map = self.depth_segmentor.get_labelMap()
            panoptic_img_f = os.path.join(self.semantic_folder,str(frame_i+1)+".png")
            # depth_seg_img_f = os.path.join(self.depth_seg_folder,str(frame_i+1)+".png")
            cv2.imwrite(panoptic_img_f,cv2.cvtColor(semantic_vis, cv2.COLOR_RGB2BGR))
            # cv2.imwrite(depth_seg_img_f,label_map)

        result = {'seg_map': seg_map, 'id2info_instance':id2info_instance, 'id2info_stuff':id2info_stuff, \
                    'segment_masks': segment_masks, 'depth_map': depth_map}
        return result

    def generateSegments(self, seg_result_2D, pose, frame_i):
        # TODEBUG
        segment_list = []
        segment_masks = seg_result_2D['segment_masks']
        seg_map = seg_result_2D['seg_map']
        id2info_instance = seg_result_2D['id2info_instance']
        id2info_stuff = seg_result_2D['id2info_stuff']

        # generate segments candidates
        sem_depth_segments = []
        extra_instances = []
        background_segments = []
        for mask_i in range(segment_masks.shape[0]):
            depth_seg_mask = segment_masks[mask_i,:,:].copy()
            depth_seg_mask = depth_seg_mask.astype(bool)
            # remove small segments
            if np.sum(depth_seg_mask) < 800:
                continue
            depth_seg_ids = seg_map[depth_seg_mask!=0].reshape(-1)
            depth_seg_area = depth_seg_ids.shape[0]
            candidate_pairs = Counter(depth_seg_ids)

            max_overlap_area = 0
            max_candidate_id = 0 
            for id in candidate_pairs:
                if(id == 0):
                    continue
                candidate_area = candidate_pairs[id]
                is_thing = (id in id2info_instance)
                is_stuff = (id in id2info_stuff)
                if is_thing:
                    if(candidate_area>0.9*id2info_instance[id]['area'] and candidate_area<0.5*depth_seg_area):
                    # if depth-undersegment, then further seg it 
                        # save segmented instance
                        # extracted_mask = np.zeros((y2-y1, x2-x1), dtype=bool)
                        extracted_mask = np.logical_and(depth_seg_mask, seg_map==id)
                        overlap_ratio = candidate_area * 1.0 / id2info_instance[id]['area']
                        extra_instances.append({'mask': extracted_mask, 'id': id, 'is_thing': True, \
                            'inst_score': id2info_instance[id]['score'], 'overlap_r':overlap_ratio })
                        # further determine remaining part
                        depth_seg_area -= candidate_area
                        depth_seg_mask[extracted_mask] = False
                    else:
                        if max_overlap_area<candidate_area:
                            max_overlap_area = candidate_area
                            max_candidate_id = id
                    continue
                elif is_stuff:
                    if max_overlap_area<candidate_area:
                        max_overlap_area = candidate_area
                        max_candidate_id = id
            # determine semantic label for depth_seg
            if(max_overlap_area>=0.2*depth_seg_area):
                overlap_ratio = max_overlap_area*1.0/depth_seg_area
                is_thing = (max_candidate_id in id2info_instance)
                inst_score = id2info_instance[max_candidate_id]['score'] if is_thing else 0.5
                sem_depth_segments.append({'mask': depth_seg_mask, 'id': max_candidate_id, 'is_thing': is_thing, \
                    'inst_score': inst_score, 'overlap_r': overlap_ratio})
            else:
                overlap_ratio = candidate_pairs[0] * 1.0 / depth_seg_area
                background_segments.append({'mask': depth_seg_mask, 'id': 0, 'is_thing': False, 'inst_score': 0.5 \
                    , 'overlap_r': overlap_ratio})
        # generate segments
        mask_segments_singleframe = np.zeros_like(seg_map, dtype=np.uint8)
        depth_map = seg_result_2D['depth_map']
        seg_index = 0
        for info_sem_depth_seg in sem_depth_segments:
            points = depth_map[info_sem_depth_seg['mask']].astype(np.float32).reshape(-1,3)
            is_thing = info_sem_depth_seg['is_thing']
            instance_label = info_sem_depth_seg['id']
            semantic_label = id2info_instance[instance_label]['category_id'] if is_thing else id2info_stuff[instance_label]['category_id']
            semantic_label = semantic_map(semantic_label)
            inst_score = info_sem_depth_seg['inst_score']
            overlap_ratio = info_sem_depth_seg['overlap_r']
            segment = Segment(points, is_thing, instance_label, semantic_label, inst_score, overlap_ratio, pose, seg_index)
            # segment.calculateConfidenceDefault()
            segment_list.append(segment)
            seg_index += 1
            mask_segments_singleframe[info_sem_depth_seg['mask']] = seg_index
        for extected_instance_seg in extra_instances:
            # x1, y1, x2, y2 = extected_instance_seg['box']
            points = depth_map[extected_instance_seg['mask']].astype(np.float32).reshape(-1,3)
            is_thing = True
            instance_label = extected_instance_seg['id']
            semantic_label = id2info_instance[instance_label]['category_id']
            semantic_label = semantic_map(semantic_label)
            inst_score = extected_instance_seg['inst_score']
            overlap_ratio = extected_instance_seg['overlap_r']
            segment = Segment(points, is_thing, instance_label, semantic_label, inst_score, overlap_ratio, pose, seg_index)
            # segment.calculateConfidenceDefault()
            segment_list.append(segment)
            seg_index += 1 
            mask_segments_singleframe[extected_instance_seg['mask']] = seg_index
        for background_seg in background_segments:
            points = depth_map[background_seg['mask']].astype(np.float32).reshape(-1,3)
            is_thing = background_seg['is_thing']
            instance_label = background_seg['id']
            semantic_label = 80 # background semantic label
            # semantic_label = semantic_id_map[semantic_label]
            inst_score = background_seg['inst_score']
            overlap_ratio = background_seg['overlap_r']
            segment = Segment(points, is_thing, instance_label, semantic_label, inst_score, overlap_ratio, pose, seg_index)
            # segment.calculateConfidenceDefault()
            segment_list.append(segment)
            seg_index += 1
            mask_segments_singleframe[background_seg['mask']] = seg_index
        if self.save_segments:
            mask_f = os.path.join(self.segments_folder, str(frame_i).zfill(5)+"_mask.png")
            cv2.imwrite(mask_f, mask_segments_singleframe)
        if(len(segment_list) == 0):
            breakpoint = None
        return segment_list

    def outlierRemove(self, segment_list, neighbor_dist_th = 0.05):
        # TODO
        # instance_to_seg_pair = {}   
        # # get instance-segment map
        # for seg in segment_list:
        #     if seg.is_thing:
        #         if seg.instance_label in instance_to_seg_pair:
        #             instance_to_seg_pair[seg.instance_label].append(seg.index)
        #         else:
        #             instance_to_seg_pair[seg.instance_label] = [seg.index]

        # for instance_label in instance_to_seg_pair:
        #     # get neighbor map
        #     instance_seg_list = instance_to_seg_pair[instance_label]
        #     neighber_map = { seg_index:[] for seg_index in instance_seg_list}
        #     for i, seg_i in enumerate(instance_seg_list):
        #         for j in range(seg_i+1, )
        return segment_list


    def frameToSegments(self, depth_img, rgb_img, pose, frame_i, camera_K = None):
        # TODEBUG
        t0 = time.time()
        segment_list = []
        seg_result_2D = self.Segmennt2D(depth_img, rgb_img, frame_i)
        if seg_result_2D is None:
            return segment_list # return if nothing from 2D segmentation
        segment_list = self.generateSegments(seg_result_2D, pose, frame_i)

        # save segments information
        if self.save_segments:
            seg_info = {'is_thing':[], 'instance_label':[],'class_label':[], 'inst_confidence':[], \
                'overlap_ratio': [], 'pose':[], 'center':[], 'seg_num':0}
            for seg in segment_list:
                seg_info['is_thing'].append(seg.is_thing)
                seg_info['instance_label'].append(seg.instance_label)
                seg_info['class_label'].append(seg.class_label)
                seg_info['inst_confidence'].append(seg.inst_confidence)
                seg_info['overlap_ratio'].append(seg.overlap_ratio)
                seg_info['pose'].append(seg.pose)
                seg_info['center'].append(seg.center)
            seg_info['seg_num'] = len(segment_list)
            seg_info_f = os.path.join(self.segments_folder, str(frame_i).zfill(5)+"_seg_info.h5")
            dictToHd5(seg_info_f, seg_info)

        # self.gsm_node.outputLog("   Seg Generation in python cost %f s" %(time.time() - t0))
        return segment_list

    def loadSegments(self, depth_scaled, camera_K, frame_i):

        segments_list = []
        mask_f = os.path.join(self.segments_folder, str(frame_i).zfill(5)+"_mask.png")
        mask = cv2.imread(mask_f, cv2.IMREAD_UNCHANGED)
        seg_info_f = os.path.join(self.segments_folder, str(frame_i).zfill(5)+"_seg_info.h5")
        if( (not os.path.isfile(mask_f)) or (not os.path.isfile(seg_info_f)) ):
            return segments_list

        seg_info= hd5ToDict(seg_info_f)
        seg_indexes = np.unique(mask)
        for seg_i in range(seg_info['seg_num']):
            seg_mask = (mask==(seg_i+1))
            points = cv2.rgbd.depthTo3d(depth=depth_scaled,K=camera_K,mask=seg_mask.astype(np.uint8))
            is_thing = seg_info['is_thing'][seg_i]
            instance_label = seg_info['instance_label'][seg_i]
            class_label = seg_info['class_label'][seg_i]
            inst_confidence = seg_info['inst_confidence'][seg_i]
            overlap_ratio = seg_info['overlap_ratio'][seg_i]
            pose = seg_info['pose'][seg_i]
            center = seg_info['center'][seg_i]
            if(is_thing!=(class_label<80)): #TODO
                is_thing = (class_label<80)

            segment = Segment(points, is_thing, instance_label, class_label, 
                inst_confidence, overlap_ratio, pose, seg_i, center)
            if(segment.points.shape[0] < 1):
                continue
            # segment.calculateConfidenceDefault()
            segments_list.append(segment)
        return segments_list


class DataLoader:
    def __init__(self, dir, traj_filename, preload_img = False, preload_depth = False):
        # whether to preload data into memory
        self.preload_img = preload_img
        self.preload_depth = preload_depth

        # parse data location
        self.dir = dir
        self.depth_folder = os.path.join(self.dir, "depth")
        self.depth_files = os.listdir(self.depth_folder)
        self.depth_files.sort()
        self.depth_indexes = [int(depth_f.split('.')[0]) for depth_f in self.depth_files]
        self.depth_path_map = {index: os.path.join(self.depth_folder, str(index)+".png") \
                                for index in self.depth_indexes}

        self.rgb_folder = os.path.join(self.dir, "color")
        self.rgb_files = os.listdir(self.rgb_folder)
        self.rgb_files.sort()
        self.rgb_indexes = [int(color_f.split('.')[0]) for color_f in self.rgb_files]
        self.rgb_path_map = {index: os.path.join(self.rgb_folder, str(index)+".jpg") \
                                for index in self.rgb_indexes}

        # load poses first
        self.traj_f = os.path.join(self.dir, traj_filename)
        self.readTrajectory()
        self.traj_indexes = list(self.poses.keys())

        # get frame indexs
        self.indexes = set.intersection( set(self.depth_indexes), set(self.rgb_indexes),  set(self.traj_indexes))
        self.indexes = list(self.indexes)
        self.indexes.sort()
        self.index_min = min(self.indexes)
        self.index_max = max(self.indexes)  

        # get camera matrixs
        self.rgb_extrinsic_f = os.path.join(self.dir, "intrinsic", "extrinsic_color.txt")
        self.rgb_intrinsic_f = os.path.join(self.dir, "intrinsic", "intrinsic_color.txt")
        self.depth_extrinsic_f = os.path.join(self.dir, "intrinsic", "extrinsic_depth.txt")
        self.depth_intrinsic_f = os.path.join(self.dir, "intrinsic", "intrinsic_depth.txt")
        self.rgb_extrinsic = np.loadtxt(self.rgb_extrinsic_f)
        self.rgb_intrinsic = np.loadtxt(self.rgb_intrinsic_f)[:3, :3]
        self.depth_extrinsic = np.loadtxt(self.depth_extrinsic_f)
        self.depth_intrinsic = np.loadtxt(self.depth_intrinsic_f)[:3, :3]
        assert(np.isclose(np.eye(4), self.rgb_extrinsic).all())
        assert(np.isclose(np.eye(4), self.depth_extrinsic).all())
        self.homograph_color_to_depth = self.depth_intrinsic @ np.linalg.inv(self.rgb_intrinsic)

        # get depth image shape 
        depth_f = self.depth_path_map[self.indexes[0]]
        depth_img = cv2.imread(depth_f,cv2.IMREAD_UNCHANGED)
        self.depth_h = depth_img.shape[0]
        self.depth_w = depth_img.shape[1]

        # preload data in RAM
        if self.preload_img:
            self.images = {}
            for idx in self.indexes:
                image_f = self.rgb_path_map[idx]
                rgb_img = cv2.imread(image_f,cv2.IMREAD_UNCHANGED)
                rgb_img_aligned = cv2.warpPerspective(rgb_img, self.homograph_color_to_depth,
                    (self.depth_w, self.depth_h) )
                self.images[idx] = rgb_img_aligned

        if self.preload_depth:
            self.depths = {}
            for idx in self.indexes:
                depth_f = self.depth_path_map[idx]
                depth_img = cv2.imread(depth_f,cv2.IMREAD_UNCHANGED)
                self.depths[idx] = depth_img

    def readTrajectory(self):
        self.poses = {}
        f = open(self.traj_f,'r')
        T_WC = []
        current_id = None
        for line in f.readlines():
            data = line.split(' ')
            if(len(data) == 3):
                if T_WC:
                    T_WC = np.array(T_WC)
                    r = Rotation.from_matrix(T_WC[:3,:3])
                    T_WC[:3,:3] = r.as_matrix()
                    self.poses[current_id] = np.array(T_WC).reshape(4,4)
                current_id = int(data[0])
                T_WC = []

            elif(len(data) == 4):
                T_WC.append([float(data[0]),float(data[1]),float(data[2]),float(data[3])])
        f.close()

    def getPoseFromIndex(self, index):
        pose = self.poses[index]
        return pose

    def getDataFromIndex(self, index):
        # normally start from 0: 0.; 0-indexed
        if(index not in self.indexes):
            return None,None,None

        rgb_img_aligned = None
        depth_img = None
        pose = None

        if self.preload_img:
            rgb_img_aligned = self.images[index]
        else:
            image_f = self.rgb_path_map[index]
            rgb_img = cv2.imread(image_f,cv2.IMREAD_UNCHANGED)
            rgb_img_aligned = cv2.warpPerspective(rgb_img, self.homograph_color_to_depth,
                (self.depth_w, self.depth_h) )

        if self.preload_depth:
            depth_img = self.depths[index]
        else:
            depth_f = self.depth_path_map[index]
            depth_img = cv2.imread(depth_f,cv2.IMREAD_UNCHANGED)
        
        pose = self.poses[index]
        # check validity of pose
        is_pose_valid = isPoseValid(pose)
        if not is_pose_valid:
            return None,None,None

        return rgb_img_aligned, depth_img, pose.astype(np.float32)

    def getDepthScaledFromIndex(self, index):
        if(index not in self.indexes):
            return None

        depth_img = None
        if self.preload_depth:
            depth_img = self.depths[index]
        else:
            depth_f = self.depth_path_map[index]
            depth_img = cv2.imread(depth_f,cv2.IMREAD_UNCHANGED)

        depth_img_scaled = cv2.rgbd.rescaleDepth(depth_img, cv2.CV_32FC1)
        return depth_img_scaled

    def getCameraMatrix(self):
        # return depth camera matrix 
        return self.depth_intrinsic.astype(np.float32)
