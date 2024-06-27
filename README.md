# SpInNet
Real-world wireless sensor network for indoor detection and localization. See the paper [Goelz2024EUSIPCO] available at https://www.researchgate.net/publication/381761991_Spatial_Inference_Network_Indoor_Proximity_Detection_via_Multiple_Hypothesis_Testing.

The `SpInNet` package provides code for and data recorded with a real-world large-scale wireless sensor network that uses relative humidity (rH) measurements to detect the presence of anomalous events in an indoor environments. Such events can be, for instance, the presence of people or an open door/window. The methods for inference were developped in previous work and its implementation is available as well, see the repository https://github.com/mgoelz95/lfdr-sMoM/. In addition, these methods are implemented in the python package ´spatialmht´ (https://pypi.org/project/spatialmht/).

This repository contains 
  1) annotated data recorded with our real-world network that can be used for your own work if you reference [Goelz2024EUSIPCO]. We provide two data sets: 'eusipco', which was used in the paper and 'bonus', which was not used in the paper due to lack of space. The data is in /csv/ and provided as csv files.
  2) code to process the data and generate inference results. 
  3) code to build your own network. Directory /running_the_network/ provides the python and arduino code that can be used directly to run your build your own spatial inference network, if would like to record your own measurements. Again, make sure to cite [Goelz2024EUSIPCO] if you use this code. 


Installation
------------

To install the package:

```
pip install spatialmht
```

Make sure you have ´spatialmht v2.1.1' installed. Execute /processing_data/process_sensor_data_to_pvals.py to generate p-values from the csv datafiles. Then execute /processing_data/produce_results.py to obtain inference results. See the comments in the scripts to learn about all options and plotting capabilities provided.


References
----------

[Goelz2024EUSIPCO]: **Spatial Inference Network: Indoor Proximity Detection via Multiple Hypothesis Testing**. M. Gölz, L. Okubo Baudenbacher, A.M. Zoubir and V. Koivunen, European Signal Processing Conference (EUSIPCO) 2024, August  2024, [DOI:TBA].

[Goelz2022TISPN]: **Multiple Hypothesis Testing Framework for Spatial Signals**. M. Gölz, A.M. Zoubir and V. Koivunen, IEEE Transactions on Signal and Information Processing over networks, July 2022, [DOI:10.1109/TSIPN.2022.3190735](https://ieeexplore.ieee.org/abstract/document/9830080).

[Goelz2022CISS]: **Estimating Test Statistic Distributions for Multiple Hypothesis Testing in Sensor Networks** M. Gölz, A.M. Zoubir and V. Koivunen, 2022 56th Annual Conference on Information Sciences and Systems (CISS), Princeton, NJ, February 2022, [10.1109/CISS53076.2022.9751186](https://ieeexplore.ieee.org/abstract/document/9751186).

[Goelz2022ICASSP]: **Improving Inference for Spatial Signals by Contextual False Discovery Rates**. M. Gölz, A.M. Zoubir and V. Koivunen, 2022 IEEE International Conference on Acoustics, Speech and Signal Processing (ICASSP2022), Singapore, [DOI:10.1109/ICASSP43922.2022.9747596](https://ieeexplore.ieee.org/abstract/document/9747596).

