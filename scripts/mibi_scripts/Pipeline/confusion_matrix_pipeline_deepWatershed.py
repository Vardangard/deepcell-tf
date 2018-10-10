# full flowthrough with DeepWatershed instance segmentation

import os
import errno
import argparse

import numpy as np
import skimage.io
import skimage.external.tifffile as tiff
import skimage.morphology
from tensorflow.python.keras.optimizers import SGD
from tensorflow.python.keras import backend as K
from scipy import stats

from deepcell import get_image_sizes
from deepcell import make_training_data
from deepcell import bn_feature_net_31x31
from deepcell import dilated_bn_feature_net_31x31
from deepcell import bn_feature_net_61x61           #model_zoo
from deepcell import dilated_bn_feature_net_61x61


from deepcell import train_model_watershed
from deepcell import train_model_watershed_sample
from deepcell import bn_dense_feature_net
from deepcell import rate_scheduler
from deepcell import train_model_disc, train_model_conv, train_model_sample
from deepcell import run_models_on_directory
from deepcell import export_model
from deepcell import get_data

import accuracy_metrics_will
from sklearn.metrics import confusion_matrix
from accuracy_metrics_will import *

# data options
DATA_OUTPUT_MODE = 'sample'
BORDER_MODE = 'valid' if DATA_OUTPUT_MODE == 'sample' else 'same'
RESIZE = True
RESHAPE_SIZE = 2048
N_EPOCHS = 40
BATCH_SIZE = 64
MAX_TRAIN = 1e8
BINS = 4

EDGE_THRESH = 0.25
INT_THRESH = 0.25
CELL_THRESH = 0.25
NUM_FINAL_EROSIONS = 1

INT_ONLY = True
REMAKE_CONV = False

# Check for channels_first or channels_last
IS_CHANNELS_FIRST = K.image_data_format() == 'channels_first'
ROW_AXIS = 2 if IS_CHANNELS_FIRST else 1
COL_AXIS = 3 if IS_CHANNELS_FIRST else 2
CHANNEL_AXIS = 1 if IS_CHANNELS_FIRST else -1



# filepath constants
DATA_DIR = '/data/data'
MODEL_DIR = '/data/models'
NPZ_DIR = '/data/npz_data'
RESULTS_DIR = '/data/results'
EXPORT_DIR = '/data/exports'

PREFIX_SEG = 'tissues/mibi/samir'
PREFIX_CLASS = 'tissues/mibi/mibi_full'
PREFIX_SAVE = 'tissues/mibi/pipeline'

FG_BG_DATA_FILE = 'mibi_pipe_wshedFB_{}_{}'.format(K.image_data_format(), DATA_OUTPUT_MODE)
CONV_DATA_FILE = 'mibi_watershedconv_{}_{}'.format(K.image_data_format(), 'conv')

CLASS_DATA_FILE = 'mibi_pipe_class_{}_{}'.format(K.image_data_format(), DATA_OUTPUT_MODE)

#'2018-07-13_mibi_watershedFB_channels_last_sample_fgbg_0.h5'

#MODEL_FGBG = '2018-08-02_mibi_watershedFB_channels_last_sample_fgbg_0.h5'
#MODEL_FGBG = '2018-07-13_mibi_31x31_channels_last_sample__0.h5'


# CURRENT BEST SEGMENTATION
MODEL_FGBG = '2018-08-20_mibi_31x31_8chanCFHHNPTd__channels_last_sample__0.h5'
CHANNELS_SEG = ['Ca.', 'Fe.', 'H3K27me3', 'H3K9ac', 'Na.', 'P.', 'Ta.', 'dsDNA.']



#STROMAL ONLY SEGMENTATION
#MODEL_FGBG = '2018-10-02_mibi_31x31_stromal__channels_last_sample__0.h5'
#CHANNELS_SEG = ['dsDNA', 'SMA', 'CD31', 'Vimentin'] 


#MODEL_FGBG = '2018-09-13_mibi_31x31_31chanlib8__channels_last_sample__0.h5'
## channel lib 8: Leeat classification + seg8 (best segmentation results so far) (31)
#CHANNELS_SEG = ['Ca.', 'Fe.', 'H3K27me3', 'H3K9ac', 'Na.', 'P.', 'Ta.', 'dsDNA.',
#                 'FoxP3.', 'CD4.', 'CD16.', 'EGFR.', 'CD68.', 'CD8.', 'CD3.',
#                 'Keratin17.', 'CD20.', 'p53.', 'catenin.', 'HLA-DR.', 'CD45.', 'Pan-Keratin.', 'MPO.',
#                 'Keratin6.', 'Vimentin.', 'SMA.', 'CD31.', 'CD56.', 'CD209.', 'CD11c.', 'CD11b.']




#single channel?
#MODEL_FGBG = '2018-07-06_mibi_31x31_channels_last_sample__0.h5'
#31x31 classification older
#MODEL_CLASS = '2018-08-09_mibi_balcompare_chan_flysampling_class_channels_last_sample__0.h5'
#61x61 newnoflip
#MODEL_CLASS = '2018-08-13_mibi_61x61_pixelremTWO_R2_class_channels_last_sample__0.h5'
#31x31 no aug
#MODEL_CLASS = '2018-08-11_mibi_31x31_dil2ero2_class_channels_last_sample__0.h5'
#31x31 std lib4 80% accurate
#MODEL_CLASS = '2018-08-21_mibi_31x31_r4_rot_med8_normStd_lib4_class_channels_last_sample__0.h5'
#31x31 lib8 
#MODEL_CLASS = '2018-09-02_mibi_31x31_r36_med8_normStd_lib8_re6_class_channels_last_sample__0.h5'
#61x61 std lib5
#MODEL_CLASS = '2018-08-16_mibi_61x61_pxR3_frot_lib5_class_channels_last_sample__0.h5'

#61x61 lib8
#MODEL_CLASS = '2018-08-29_mibi_61x61_r4_med8_normStd_lib8_re7_class_channels_last_sample__0.h5'

#61x61 megatrained and eroded 6x
MODEL_CLASS = '2018-09-13_mibi_31x31_r36_med8_normStd_lib8_re6_class_ITONE_channels_last_sample__0.h5'


#CORE100 class
#MODEL_CLASS = '2018-09-30_mibi_31x31_r36_med8_normStd_lib8_re6_class_CORE100_channels_last_sample__0.h5'

MODEL_CLASS = '2018-10-08_mibi_31x31_CORE100_test1_channels_last_sample__0.h5'

RUN_DIR = 'set1'

WINDOW_SIZE_SEG = (15,15)
WINDOW_SIZE_CLASS = (30,30)

TRAIN_DIR_SAMPLE = ['set1', 'set2']
TRAIN_DIR_CLASS_RANGE = range(1, 39+1)

NUM_FEATURES_IN_SEG = 2
NUM_FEATURES_OUT_SEG = 3
NUM_FEATURES_CLASS = 17

#CHANNELS_SEG = ['dsDNA', 'Ca', 'H3K27me3', 'H3K9ac', 'Ta']  #Add P?
#CHANNELS_SEG = ['dsDNA']

#CHANNELS_CLASS = ['dsDNA', 'Ca','H3K27me3', 'H3K9ac', 'Ta', 'FoxP3.', 'CD4.', 'CD16.', 'EGFR.', 'CD68.', 'CD8.', 'CD3.',
#                 'Keratin17.', 'CD20.', 'p53.', 'catenin.', 'HLA-DR.', 'CD45.', 'Pan-Keratin.', 'MPO.',
#                 'Keratin6.', 'Vimentin.', 'SMA.', 'CD31.', 'CD56.', 'CD209.', 'CD11c.', 'CD11b.']


## channel lib 4: Leeat classification + trimmed segmentation channels (26)
#CHANNELS_CLASS = ['dsDNA', 'Ca', 'Ta', 'FoxP3.', 'CD4.', 'CD16.', 'EGFR.', 'CD68.', 'CD8.', 'CD3.',
#                 'Keratin17.', 'CD20.', 'p53.', 'catenin.', 'HLA-DR.', 'CD45.', 'Pan-Keratin.', 'MPO.',
#                 'Keratin6.', 'Vimentin.', 'SMA.', 'CD31.', 'CD56.', 'CD209.', 'CD11c.', 'CD11b.']

## channel set 5: Leeat classification + trimmed segmentation channels (25)
#CHANNELS_CLASS = ['dsDNA','Ta', 'FoxP3.', 'CD4.', 'CD16.', 'EGFR.', 'CD68.', 'CD8.', 'CD3.',
#                 'Keratin17.', 'CD20.', 'p53.', 'catenin.', 'HLA-DR.', 'CD45.', 'Pan-Keratin.', 'MPO.',
#                 'Keratin6.', 'Vimentin.', 'SMA.', 'CD31.', 'CD56.', 'CD209.', 'CD11c.', 'CD11b.']

## channel lib 6: Leeat classification + trimmed segmentation channels + H3K27me3 (27)
#CHANNELS_CLASS = ['H3K27me3.', 'dsDNA', 'Ca', 'Ta', 'FoxP3.', 'CD4.', 'CD16.', 'EGFR.', 'CD68.', 'CD8.', 'CD3.',
#                 'Keratin17.', 'CD20.', 'p53.', 'catenin.', 'HLA-DR.', 'CD45.', 'Pan-Keratin.', 'MPO.',
#                 'Keratin6.', 'Vimentin.', 'SMA.', 'CD31.', 'CD56.', 'CD209.', 'CD11c.', 'CD11b.']


## channel lib 7: Leeat classification + dsDNA
#CHANNELS_CLASS = ['dsDNA', 'FoxP3.', 'CD4.', 'CD16.', 'EGFR.', 'CD68.', 'CD8.', 'CD3.',
#                 'Keratin17.', 'CD20.', 'p53.', 'catenin.', 'HLA-DR.', 'CD45.', 'Pan-Keratin.', 'MPO.',
#                 'Keratin6.', 'Vimentin.', 'SMA.', 'CD31.', 'CD56.', 'CD209.', 'CD11c.', 'CD11b.']

## channel lib 8: Leeat classification + seg8 (best segmentation results so far) (31)
CHANNELS_CLASS = ['Ca.', 'Fe.', 'H3K27me3', 'H3K9ac', 'Na.', 'P.', 'Ta.', 'dsDNA.',
                 'FoxP3.', 'CD4.', 'CD16.', 'EGFR.', 'CD68.', 'CD8.', 'CD3.',
                 'Keratin17.', 'CD20.', 'p53.', 'catenin.', 'HLA-DR.', 'CD45.', 'Pan-Keratin.', 'MPO.',
                 'Keratin6.', 'Vimentin.', 'SMA.', 'CD31.', 'CD56.', 'CD209.', 'CD11c.', 'CD11b.']


for d in (NPZ_DIR, MODEL_DIR, RESULTS_DIR):
    try:
        os.makedirs(os.path.join(d, PREFIX_SEG))
    except OSError as exc: # Guard against race condition
        if exc.errno != errno.EEXIST:
            raise
    try:
        os.makedirs(os.path.join(d, PREFIX_CLASS))
    except OSError as exc: # Guard against race condition
        if exc.errno != errno.EEXIST:
            raise
    try:
        os.makedirs(os.path.join(d, PREFIX_SAVE))
    except OSError as exc: # Guard against race condition
        if exc.errno != errno.EEXIST:
            raise

def dilate(array, mask, num_dilations):
    copy = np.copy(array)
    for x in range(0, num_dilations):
        dilated = skimage.morphology.dilation(copy)

        # if still within the mask range AND one cell not eating another, dilate
        #copy = np.where( ((mask!=0) & (dilated!=copy & copy==0)), dilated, copy)
        copy = np.where( (mask!=0) & (dilated!=copy) & (copy==0), dilated, copy)
    return copy

def dilate_nomask(array, num_dilations):
    copy = np.copy(array)
    for x in range(0, num_dilations):
        dilated = skimage.morphology.dilation(copy)

        # if one cell not eating another, dilate
        #copy = np.where( ((mask!=0) & (dilated!=copy & copy==0)), dilated, copy)
        copy = np.where( (dilated!=copy) & (copy==0), dilated, copy)
    return copy

def erode(array, num_erosions):
    original = np.copy(array)

    for x in range(0, num_erosions):
        eroded = skimage.morphology.erosion(np.copy(original))
        original[original != eroded] = 0

    return original

# runs the sample and watershed segmentation models
def run_model_segmentation():

    raw_dir = 'raw'
    data_location = os.path.join(DATA_DIR, PREFIX_CLASS, RUN_DIR, raw_dir)
    output_location = os.path.join(RESULTS_DIR, PREFIX_SEG)
    channel_names = CHANNELS_SEG
    image_size_x, image_size_y = get_image_sizes(data_location, channel_names)


    weights = os.path.join(MODEL_DIR, PREFIX_SEG, MODEL_FGBG)


    n_features = 3

    if DATA_OUTPUT_MODE == 'sample':
        if WINDOW_SIZE_SEG == (15,15):
            model_fn = dilated_bn_feature_net_31x31                               
        elif WINDOW_SIZE_SEG == (30,30):
            model_fn = dilated_bn_feature_net_61x61
    elif DATA_OUTPUT_MODE == 'conv':
        model_fn = bn_dense_feature_net
    else:
        raise ValueError('{} is not a valid training mode for 2D images (yet).'.format(
            DATA_OUTPUT_MODE))

    predictions = run_models_on_directory(
        data_location=data_location,
        channel_names=channel_names,
        output_location=output_location,
        n_features=n_features,
        model_fn=model_fn,
        list_of_weights=[weights],
        image_size_x=image_size_x,
        image_size_y=image_size_y,
        win_x=WINDOW_SIZE_SEG[0],
        win_y=WINDOW_SIZE_SEG[1],
        split=False)

    #0.25 0.25 works good
    edge_thresh = EDGE_THRESH
    interior_thresh = INT_THRESH
    cell_thresh = CELL_THRESH

    print('shape of predictions is:', predictions.shape)

    edge = np.copy(predictions[:,:,:,0])
    edge[edge < edge_thresh] = 0
    edge[edge > edge_thresh] = 1

    interior = np.copy(predictions[:, :, :, 1])
    interior[interior > interior_thresh] = 1
    interior[interior < interior_thresh] = 0

    cell_notcell = 1 - np.copy(predictions[:, :, :, 2])
    cell_notcell[cell_notcell > cell_thresh] = 1
    cell_notcell[cell_notcell < cell_thresh] = 0

    # define foreground as the interior bounded by edge
    fg_thresh = np.logical_and(interior==1, edge==0)

    # remove small objects from the foreground segmentation
    fg_thresh = skimage.morphology.remove_small_objects(fg_thresh, min_size=50, connectivity=1)

    #fg_thresh = skimage.morphology.binary_erosion(fg_thresh)
    #fg_thresh = skimage.morphology.binary_dilation(fg_thresh)

    fg_thresh = np.expand_dims(fg_thresh, axis=CHANNEL_AXIS)

    watershed_segmentation = skimage.measure.label(  np.squeeze(fg_thresh), connectivity=2)


    dilation = 'old'

    if dilation == 'new':
        # dilate gradually into the mask area
        watershed_segmentation = dilate(watershed_segmentation, interior, 2)
        watershed_segmentation = erode(watershed_segmentation, 1)
        watershed_segmentation = dilate(watershed_segmentation, interior, 2)
        watershed_segmentation = erode(watershed_segmentation, 1)
        watershed_segmentation = dilate(watershed_segmentation, interior, 2)
        watershed_segmentation = erode(watershed_segmentation, 1)
        watershed_segmentation = dilate(watershed_segmentation, interior, 2)
        watershed_segmentation = erode(watershed_segmentation, 1)
        watershed_segmentation = dilate(watershed_segmentation, interior, 2)
        watershed_segmentation = erode(watershed_segmentation, 1)
        watershed_segmentation = dilate(watershed_segmentation, interior, 2)
        watershed_segmentation = erode(watershed_segmentation, 1)
        watershed_segmentation = dilate(watershed_segmentation, interior, 2)
        watershed_segmentation = erode(watershed_segmentation, 1)
        watershed_segmentation = dilate(watershed_segmentation, interior, 2)
        watershed_segmentation = erode(watershed_segmentation, 1)
        watershed_segmentation = dilate(watershed_segmentation, interior, 2)

        # # dilate without regard to mask area
        #watershed_segmentation = dilate_nomask(watershed_segmentation, 2)
        #watershed_segmentation = erode(watershed_segmentation, 1)
        # watershed_segmentation = dilate_nomask(watershed_segmentation, 1)
        # watershed_segmentation = erode(watershed_segmentation, 1)
        # watershed_segmentation = dilate_nomask(watershed_segmentation, 1)

        # # erode to clean up and segment
        #watershed_segmentation = erode(watershed_segmentation, 1)
        watershed_segmentation = dilate_nomask(watershed_segmentation, 1)
        watershed_segmentation = erode(watershed_segmentation, 1)
        watershed_segmentation = dilate_nomask(watershed_segmentation, 1)
        watershed_segmentation = erode(watershed_segmentation, NUM_FINAL_EROSIONS)


    elif dilation == 'old':
        # dilate gradually into the mask area
        watershed_segmentation = dilate(watershed_segmentation, interior, 2)
        watershed_segmentation = erode(watershed_segmentation, 1)
        watershed_segmentation = dilate(watershed_segmentation, interior, 2)
        watershed_segmentation = erode(watershed_segmentation, 1)
        watershed_segmentation = dilate(watershed_segmentation, interior, 2)
        watershed_segmentation = erode(watershed_segmentation, 1)
        watershed_segmentation = dilate(watershed_segmentation, interior, 2)
        watershed_segmentation = erode(watershed_segmentation, 1)
        watershed_segmentation = dilate(watershed_segmentation, interior, 2)
        watershed_segmentation = erode(watershed_segmentation, 1)
        watershed_segmentation = dilate(watershed_segmentation, interior, 2)
        watershed_segmentation = erode(watershed_segmentation, 1)
        watershed_segmentation = dilate(watershed_segmentation, interior, 2)
        watershed_segmentation = erode(watershed_segmentation, 1)
        watershed_segmentation = dilate(watershed_segmentation, interior, 2)
        watershed_segmentation = erode(watershed_segmentation, 1)
        watershed_segmentation = dilate(watershed_segmentation, interior, 2)

        # # dilate without regard to mask area
        #watershed_segmentation = dilate_nomask(watershed_segmentation, 2)
        #watershed_segmentation = erode(watershed_segmentation, 1)
        # watershed_segmentation = dilate_nomask(watershed_segmentation, 1)
        # watershed_segmentation = erode(watershed_segmentation, 1)
        # watershed_segmentation = dilate_nomask(watershed_segmentation, 1)

        # # erode to clean up and segment
        #watershed_segmentation = erode(watershed_segmentation, 1)
        watershed_segmentation = dilate_nomask(watershed_segmentation, 1)
        watershed_segmentation = erode(watershed_segmentation, 2)
        watershed_segmentation = dilate_nomask(watershed_segmentation, 2)
        watershed_segmentation = erode(watershed_segmentation, NUM_FINAL_EROSIONS)
        

    index = 0

    output_location = os.path.join(RESULTS_DIR, PREFIX_SAVE)
    print('saving to: ', output_location)

    dsDNA = tiff.imread(os.path.join(data_location, 'dsDNA.tif'))
    dsDNA = dsDNA[15:-15, 15:-15]

    watershed_segmentation = watershed_segmentation.astype('uint16')

    tiff.imsave(os.path.join(output_location, 'raw_dsDNA.tif'), dsDNA)
    tiff.imsave(os.path.join(output_location, 'edge_prediction.tif'), predictions[index, :, :, 0])
    tiff.imsave(os.path.join(output_location, 'interior_bound.tif'), interior)
 #    tiff.imsave(os.path.join(output_location, 'cell_notcell.tif'), cell_notcell)
    tiff.imsave(os.path.join(output_location, 'shallowWatershed_instance_seg.tif'), watershed_segmentation)

    return watershed_segmentation

# runs the classification model
def run_model_classification():
    raw_dir = 'raw'
    data_location = os.path.join(DATA_DIR, PREFIX_CLASS, RUN_DIR, raw_dir)
    # test_images = os.path.join(DATA_DIR, 'tissues/mibi/mibi_full/TNBCShareData', 'set1', raw_dir)
    output_location = os.path.join(RESULTS_DIR, PREFIX_CLASS)
    image_size_x, image_size_y = get_image_sizes(data_location, CHANNELS_CLASS)

    print('image_size_x is:', image_size_x)
    print('image_size_y is:', image_size_y)

    weights = os.path.join(MODEL_DIR, PREFIX_CLASS, MODEL_CLASS)


    if DATA_OUTPUT_MODE == 'sample':
        if WINDOW_SIZE_CLASS == (15,15):
            model_fn = dilated_bn_feature_net_31x31
        elif WINDOW_SIZE_CLASS == (30,30):
            model_fn = dilated_bn_feature_net_61x61
    elif DATA_OUTPUT_MODE == 'conv':
        model_fn = bn_dense_feature_net
    else:
        raise ValueError('{} is not a valid training mode for 2D images (yet).'.format(
            DATA_OUTPUT_MODE))

    predictions = run_models_on_directory(
        data_location=data_location,
        channel_names=CHANNELS_CLASS,
        output_location=output_location,
        n_features=NUM_FEATURES_CLASS,
        model_fn=model_fn,
        list_of_weights=[weights],
        image_size_x=image_size_x,
        image_size_y=image_size_y,
        win_x=WINDOW_SIZE_CLASS[0],
        win_y=WINDOW_SIZE_CLASS[1],
        split=False)

    output_location = os.path.join(RESULTS_DIR, PREFIX_SAVE)

    for i in range(predictions.shape[0]):
        max_img = np.argmax(predictions[i], axis=-1)
        max_img = max_img.astype(np.int16)
        cnnout_name = 'pipe_class_argmax_frame_{}.tif'.format(str(i).zfill(3))
        out_file_path = os.path.join(output_location, cnnout_name)
        tiff.imsave(out_file_path, max_img)


    print('classification model output shape is:', max_img.shape)

    return max_img

def post_processing(instance, classification, ground_truth):



    print('Classifying cell types')

    # make an empty array of the same size as the instance input to store the output values
    rows = instance.shape[0]
    cols = instance.shape[1]
    instance_type_pred = np.zeros((cols, rows), dtype='uint16')
    instance_type_truth = np.zeros((cols, rows), dtype='uint16')

    cells_pred = np.array([])
    cells_truth = np.array([])

    # for each unique cell in the segmentation prediction, find the its celltype based off of the class prediction and class truth
    for label in range(1, (instance.max()+1)):

        label_classes = np.array([])
        label_truth_classes = np.array([])
        pixel_locations = np.argwhere(instance == label)

        # for each pixel the cell covers
        for x_y in pixel_locations:

            x = x_y[1]
            y = x_y[0]

            # store that pixels class unless it is background
            if classification[y,x] >= 0:
                label_classes = np.append(label_classes, classification[y,x])

            if ground_truth[y,x] >= 0:
                label_truth_classes = np.append(label_truth_classes, ground_truth[y,x])

        # If there are any cell classes for that cell, find the mode
        if len(label_classes) != 0:
            m = stats.mode(label_classes)
            cell_class_pred = np.asscalar(m[0])

        # if every pixel in the cell was classified as background, classify it as background. This should *not* happen
        elif len(label_classes) == 0:
            cell_class_pred = 0

        #classification for ground truth
        # If there are any cell classes for that cell, find the mode
        if len(label_truth_classes) != 0:
            m = stats.mode(label_truth_classes)
            cell_class_truth = np.asscalar(m[0])

        # if every pixel in the cell was classified as background, classify it as background. This should *not* happen
        elif len(label_truth_classes) == 0:
            cell_class_truth = 0

        cells_pred = np.append(cells_pred, cell_class_pred)
        cells_truth = np.append(cells_truth, cell_class_truth)


        for x_y in pixel_locations:

            x = x_y[1]
            y = x_y[0]

            instance_type_pred[y,x] = cell_class_pred
            instance_type_truth[y,x] = cell_class_truth

    print('Classification accuracy was:', np.count_nonzero(cells_pred == cells_truth)/len(cells_pred))
    print(confusion_matrix(cells_truth, cells_pred, labels=[0, 1, 2, 3, 4, 5, 6, 7, 8, 9, 10, 11, 12, 13, 14, 15, 16]))

    output_location = os.path.join(RESULTS_DIR, PREFIX_SAVE)
    cnnout_name_pred = 'Cellular_Instance_Classification_prediction.tif'
    cnnout_name_truth = 'Cellular_Instance_Classification_truth.tif'

    tiff.imsave( os.path.join(output_location, cnnout_name_pred), instance_type_pred)
    tiff.imsave( os.path.join(output_location, cnnout_name_truth), instance_type_truth)

# runs model on segmentation/watershed/classification, and postprocesses the results.
def run_pipeline_on_dir():
    instance_seg = np.squeeze(run_model_segmentation())
    cell_classes = run_model_classification()

    print(instance_seg.shape, cell_classes.shape)

    ground_truth_class = skimage.io.imread('/data/data/tissues/mibi/mibi_full/TNBCcellTypes/P1_labeledImage.tiff')
    
    # trim ground truth, cell classes, and instance seg to all be the same shape THIS IS BAD, HARDCODED CODE IM SORRY IM LAZY NEED TO FIX
    if (WINDOW_SIZE_CLASS == (15,15)) and (WINDOW_SIZE_SEG == (15,15)):
        ground_truth_class = ground_truth_class[15:-15, 15:-15]

    elif (WINDOW_SIZE_CLASS == (30, 30)) and (WINDOW_SIZE_SEG == (30,30)):
        ground_truth_class = ground_truth_class[30:-30, 30:-30]

    elif (WINDOW_SIZE_CLASS == (30, 30)) and (WINDOW_SIZE_SEG == (15,15)):
        ground_truth_class = ground_truth_class[30:-30, 30:-30]
        instance_seg = instance_seg[15:-15, 15:-15]

    elif (WINDOW_SIZE_CLASS == (15, 15)) and (WINDOW_SIZE_SEG == (30,30)):
        ground_truth_class = ground_truth_class[30:-30, 30:-30]
        cell_classes = cell_classes[15:-15, 15:-15]
 

    post_processing(instance_seg, cell_classes, ground_truth_class)


    return instance_seg


def run_stats(mask, instance, trim):

    print('shape of mask pre-prep is:', mask.shape)
    print('shape of instance pre-prep is:', instance.shape)


    truth, pred = im_prep(mask, instance, trim)

    print('shape of mask post-prep is:', pred.shape)
    print('shape of instance post-prep is:', truth.shape)
    

#    stats_pixelbased(truth, pred)
#    stats_objectbased(truth, pred)
    stats_pixelbased(truth, pred)
    stats_objectbased(truth, pred)


if __name__ == '__main__':
    import time

    start = time.time()
    print("hello")
    
    instance_seg = run_pipeline_on_dir()
    
    end = time.time()
    print(end - start)
    mask = skimage.io.imread( '/data/data/tissues/mibi/samir/set1/annotated/feature_1.tif') 

    # find the amount of edge that needs to be trimmed off
    trim = int((2048 - instance_seg.shape[0])/2)
    run_stats(mask, instance_seg, trim)
