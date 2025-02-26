# Introduction
**"Volumetric Semantically Consistent 3D Panoptic Mapping"** is a pipeline for incrementally building volumetric object-centric maps during online scanning with a localized RGB-D camera. The code framework is based on [**Voxblox++**](https://github.com/ethz-asl/voxblox-plusplus).
The main difference against **Voxblox++** is: 
<ol>
  <li> <a href="https://github.com/facebookresearch/detectron2">Panoptic segmentation</a> is applied in 2D RGB images instead of <a href="https://github.com/matterport/Mask_RCNN2">instance segmentation.</a></li>
  <li>A novel method to segment semantic-instance surface regions(super-points), as illustrated in Section III-B in the paper.</li>
  <li>A new graph optimization-based semantic labeling and instance refinement algorithm, as illustrated in Section III-C & Section III-D in the paper.</li>
  <li>The proposed framework achieves state-of-the-art 2D-to-3D instance segmentation accuracy, as illustrated in Section IV in the paper.</li>
</ol>

<p align="center">
  <img src="https://github.com/y9miao/volumetric-semantically-consistent-3D-panoptic-mapping/blob/main/images/pipeline.png" width=700>
</p>

# Installation
The instructions for installing the framework are [here](https://github.com/y9miao/volumetric-semantically-consistent-3D-panoptic-mapping/wiki/Installation).

# Usage
For basic usage and replicate of results in the paper, instructions are provided:
- [Datasets](https://github.com/y9miao/volumetric-semantically-consistent-3D-panoptic-mapping/wiki/Datasets)
- [Basic Usage](https://github.com/y9miao/volumetric-semantically-consistent-3D-panoptic-mapping/wiki/Basic-Usage)