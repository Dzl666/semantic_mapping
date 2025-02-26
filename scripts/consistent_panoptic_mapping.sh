#!/bin/bash
# which scene to run
SceneNum=scene0008_00
# data source dir
DataFolder=/media/zilong/Documents/MasterProject/scannet_v2
# folder of mapping results
ResultFolder=~/Disk_sda6/semantic_mapping_result/${SceneNum}
# folder to save intermediate segments result
IntermediateSegsFolder=~/Disk_sda6/depth_seg_temp_log/${SceneNum}
# folder to save 2D panoptic segments
PanopticSegsFolder=~/Disk_sda6/pano_seg_temp/${SceneNum}
# folder to save 2D geometrics segments
GeometricSegsFolder=~/Disk_sda6/geo_seg_temp/${SceneNum}

ThreadNum=10
logTest=info

# use one frame for integration every n_step frames
step=10

export PYTHONPATH=${PYTHONPATH}:mapping_ros_ws/devel/lib

python scripts/panoptic_mapping_.py \
--dataset scannet_nyu \
--task Nyu40 \
--preload \
--scene_num ${SceneNum} \
--data_folder ${DataFolder} \
--result_folder ${ResultFolder} \
--start 0 \
--end 5000 \
--step ${step} \
--data_association 2 \
--inst_association 4 \
--seg_graph_confidence 3 \
--temporal_results \
--intermediate_seg_folder ${IntermediateSegsFolder} \
--num_threads ${ThreadNum} \
--log "${logTest}"