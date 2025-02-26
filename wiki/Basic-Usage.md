<!-- 
Sample sequences can be downloaded [here](https://github.com/y9miao/volumetric-semantically-consistent-3D-panoptic-mapping/wiki/Datasets).
## SceneNN Sequence 206
<img src="https://github.com/y9miao/volumetric-semantically-consistent-3D-panoptic-mapping/blob/main/images/sequence206_semantics.png" width=300>  
-->
Due to the limitation of copyright, I am not allowed to distribute sample sequences here. The dataset can be downloaded from the official release: [ScanNet](https://kaldir.vc.in.tum.de/scannet_benchmark/) and [SceneNN](https://hkust-vgd.github.io/scenenn/).  
Note that some poses from ScanNet is not valid (e.g. NaN) so those frames with invalid poses are filtered out. Also the depth frames are transformed into png. Unfortunately the preprocess script is missing and I will update it soon. But the dataset is organized as this:
```
$path_to_ScanNet/
|----train/
    |----scene0000_00/
        |----poses/
            |----0.txt
            |----...
        |----color/
            |----0.jpg
            |----...
        |----depth/
            |----0.png
            |----...
|----val/...
|----test/... 
```
More details about the dataset organization and format can be found in /volumetric-semantically-consistent-3D-panoptic-mapping/scripts/utils/common_scannet_nyu.py

In order to run the pipeline, firstly download the [pretrained model](https://drive.google.com/file/d/1vHszTmSo7HGZFHJHF7QAhazOI9NcuRdv/view?usp=sharing) and put it into volumetric-semantically-consistent-3D-panoptic-mapping/scripts/semantics/rp_server/checkpoints launch the panoptic segmentation server:
```
conda activate mask2former
cd volumetric-semantically-consistent-3D-panoptic-mapping/scripts/semantics/rp_server
python launch_mask2former_server.py
```

Then launch the mapping script. Note that for each frame, the panoptic-geometric segmentation takes majority of runtime and the segmentation results can be saved in path-to-intermediate-results so that we don't need to run panoptic-geometric segmentation every experiment.
```
source volumetric-semantically-consistent-3D-panoptic-mapping/mapping_ros_ws/devel/setup.bash
cd volumetric-semantically-consistent-3D-panoptic-mapping
bash scripts/consistent_panoptic_mapping.sh  scene0000_00 parent-path-to-sequence_scene0000_00-folder path-to-initial-result-folder path-to-intermediate-results num-available-thread log-to-output 1
```
Note in path-to-initial-result-folder/, meshes with color encoded in instnace, semantic and super-point labels are generated; in path-to-initial-result-folder/log/, "gms_py_test.INFO" contains information of mapping process, "gms_py_test.ERROR" contains information of instnaces and super-points; "LabelInitialGuess.txt" contains initial guess regarding to supe-points' semantic and instanc labels; "ConfidenceMap.txt" contains information of edges in super-point graph.
<!--
Evaluation on result of initial guess.
```
bash scripts/evaluation/GeoSemEvalShellPano.sh 206 path-to-initial-result-folder path-to-sequence-206 1 CoCoPano 
```

Apply semantic regularization and instance segmentation refinement in a post-processing manner.
```
bash scripts/post_refinement.sh 206 path-to-refined-result-folder path-to-initial-result-folder
```
Evaluate the refined results.
```
bash scripts/evaluation/GeoSemEvalShellSegGraph.sh 206 path-to-refined-result-folder path-to-sequence-206 1 CoCoPano path-to-initial-result-folder
```
After evaluation code is run, the numbers of metrics(mAP, true positive instance, panoptic quality and chamfer distance) will be generated in path-to-initial-result-folder and path-to-refined-result-folder.
-->

