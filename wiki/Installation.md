# Installation on Ubuntu 16.04/18.04/20.04 
The following instructions is for main branch in Ubuntu 20.04. The branchs for other Ubuntu versions are comming soon. 

## Prerequisites  
- ROS: Install ROS following the instructions at the [ROS installation page](http://wiki.ros.org/ROS/Installation). The full install (ros-kinetic-desktop-full, ros-melodic-desktop-full, ros-noetic-desktop-full) are recommended. Make sure to source your ROS setup.bash script by following the instructions on the ROS installation page.
- Python 3.8 (required for ROS-noetic support)
- gcc & g++ >= 5.4
- [CMake](https://cmake.org/install/) 3.8 or later

## Install mapping backends
Install some dependencies
```
sudo apt update
sudo apt install python3-dev python3-pip python3-wstool protobuf-compiler dh-autoreconf python3-catkin-tools python3-osrf-pycommon
pip install -r requirements
```


Get the codes:
```
git clone --recurse-submodules https://github.com/y9miao/volumetric-semantically-consistent-3D-panoptic-mapping.git
```
Initialize catkin workspace and get dependencies of catkin packages:
```
export ROS_VERSION=noetic
cd volumetric-semantically-consistent-3D-panoptic-mapping/mapping_ros_ws
catkin init
catkin config --extend /opt/ros/$ROS_VERSION --merge-devel
catkin config --cmake-args -DCMAKE_CXX_STANDARD=14 -DCMAKE_BUILD_TYPE=Release
wstool init src

cd src
wstool merge -t . consistent_panoptic_mapping/consistent_panoptic_mapping.rosinstall
wstool update
```
Compile the mapping backends:
```
cd volumetric-semantically-consistent-3D-panoptic-mapping/mapping_ros_ws/src
catkin build consistent_gsm depth_segmentation_py
```

## Install panoptic segmentation server 
Firstly, please create another conda env (e.g. mask2former) for the pano seg server and install [Mask2Former](https://github.com/facebookresearch/Mask2Former/blob/main/INSTALL.md) in the mask2former environment.   And please add the Mask2Former Path to the env variable (sorry for the ugly solution):
```
export MASK2FORMER_PATH=$path_to_the_Mask2Former_folder
```
Secondly, install the panoptic segmentation server and client which is taken from [Interactive-Scene-Reconstruction](https://github.com/hmz-15/Interactive-Scene-Reconstruction/tree/main/mapping/rp_server):
```
# conda environment for panoptic segmentation server
conda activate mask2former
pip install pip --upgrade

# other dependencies
cd volumetric-semantically-consistent-3D-panoptic-mapping/scripts/semantics/rp_server
pip install -r requirements.txt

# install detectron2 server
make dev
```

Note that you may need to adjust the version of [torch, torchvision](https://pytorch.org/), [detectron2](https://detectron2.readthedocs.io/en/latest/tutorials/install.html) and [opencv](https://pypi.org/project/opencv-python/) based on your environment.   
Thirdly, download the [mask2former model](https://drive.google.com/file/d/1vHszTmSo7HGZFHJHF7QAhazOI9NcuRdv/view) which is finetuned on Scannet Dataset in the NYU40 category space. And put this model in the dir "volumetric-semantically-consistent-3D-panoptic-mapping/scripts/semantics/rp_server/checkpoints"


