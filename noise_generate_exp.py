

__author__ = 'jdietric'

import itertools
import logging
import numpy as np
import os
import tensorflow as tf
from sklearn.metrics import f1_score, recall_score, precision_score

import config.system as sys_config
import utils
import adni_data_loader_all



def get_latest_checkpoint_and_log(logdir, filename):
    init_checkpoint_path = utils.get_latest_model_checkpoint_path(logdir, filename)
    logging.info('Checkpoint path: %s' % init_checkpoint_path)
    last_step = int(init_checkpoint_path.split('/')[-1].split('-')[-1])
    logging.info('Latest step was: %d' % last_step)
    return init_checkpoint_path

def map_labels_to_list(labels, label_list):
    # label_list is a python list with the labels
    # map labels in range(len(label_list)) to the labels in label_list
    # E.g. [0,0,1,1] becomes [0,0,2,2] (if 1 doesnt exist in the data)
    # label gets mapped to label_list[label]
    label_lookup = tf.constant(np.array(label_list))
    return tf.gather(label_lookup, labels)


def build_gen_graph(img_tensor_shape, gan_config, noise_shape=None, use_noise=False):
    # noise_shape
    generator = gan_config.generator
    graph_generator = tf.Graph()
    with graph_generator.as_default():
        # source image (batch size = 1)
        xs_pl = tf.placeholder(tf.float32, img_tensor_shape, name='xs_pl')

        if use_noise:
            noise_pl = tf.placeholder(tf.float32, noise_shape, name='z_noise')
        else:
            noise_pl = None

        # generated fake image batch
        xf = generator(xs=xs_pl, z_noise=noise_pl, training=False)

        # Add the variable initializer Op.
        init = tf.global_variables_initializer()

        # Create a savers for writing training checkpoints.
        saver = tf.train.Saver()
        return graph_generator, xs_pl, noise_pl, xf, init, saver


def generate_with_noise(gan_experiment_path_list, noise_list,
                        image_saving_indices=set(), image_saving_path=None):
    """

    :param gan_experiment_path_list: list of GAN experiment paths to be evaluated. They must all have the same image settings and source/target field strengths as the classifier
    :param clf_experiment_path: AD classifier used
    :param image_saving_indices: set of indices of the images to be saved
    :param image_saving_path: where to save the images. They are saved in subfolders for each experiment
    :return:
    """

    batch_size = 1
    logging.info('batch size %d is used for everything' % batch_size)

    for gan_experiment_path in gan_experiment_path_list:
        gan_config, logdir_gan = utils.load_log_exp_config(gan_experiment_path)

        gan_experiment_name = gan_config.experiment_name

        # Load data
        data = adni_data_loader_all.load_and_maybe_process_data(
            input_folder=gan_config.data_root,
            preprocessing_folder=gan_config.preproc_folder,
            size=gan_config.image_size,
            target_resolution=gan_config.target_resolution,
            label_list=gan_config.label_list,
            offset=gan_config.offset,
            rescale_to_one=gan_config.rescale_to_one,
            force_overwrite=False
        )

        # extract images and indices of source/target images for the test set
        images_test = data['images_test']

        im_s = gan_config.image_size

        img_tensor_shape = [batch_size, im_s[0], im_s[1], im_s[2], 1]

        logging.info('\nGAN Experiment (%.1f T to %.1f T): %s' % (gan_config.source_field_strength,
                                                              gan_config.target_field_strength, gan_experiment_name))
        logging.info(gan_config)
        # open GAN save file from the selected experiment

        # prevents ResourceExhaustError when a lot of memory is used
        config = tf.ConfigProto()
        config.gpu_options.allow_growth = True  # Do not assign whole gpu memory, just use it on the go
        config.allow_soft_placement = True  # If a operation is not defined in the default device, let it execute in another.

        source_indices = []
        target_indices = []
        source_true_labels = []
        source_pred = []
        target_true_labels = []
        target_pred = []
        for i, field_strength in enumerate(data['field_strength_test']):
            if field_strength == gan_config.source_field_strength:
                source_indices.append(i)
            elif field_strength == gan_config.target_field_strength:
                target_indices.append(i)

        num_source_images = len(source_indices)
        num_target_images = len(target_indices)

        logging.info('Data summary:')
        logging.info(' - Images:')
        logging.info(images_test.shape)
        logging.info(images_test.dtype)
        logging.info(' - Domains:')
        logging.info('number of source images: ' + str(num_source_images))
        logging.info('number of target images: ' + str(num_target_images))

        # save real images
        source_image_path = os.path.join(image_saving_path, 'source')
        utils.makefolder(source_image_path)
        sorted_saving_indices = sorted(image_saving_indices)

        source_saving_indices = [source_indices[index] for index in sorted_saving_indices]
        for source_index in source_saving_indices:
            source_img_name = 'source_img_%.1fT_%d.nii.gz' % (gan_config.source_field_strength, source_index)
            utils.create_and_save_nii(images_test[source_index], os.path.join(source_image_path, source_img_name))
            logging.info(source_img_name + ' saved')

        logging.info('source images saved')

        logging.info('loading GAN')
        # open the latest GAN savepoint
        init_checkpoint_path_gan = get_latest_checkpoint_and_log(logdir_gan, 'model.ckpt')

        # TODO: put noise shape in and check that all noise has the required shape (gan_config)
        # build a separate graph for the generator
        graph_generator, generator_img_pl, z_noise_pl, x_fake_op, init_gan_op, saver_gan = build_gen_graph(img_tensor_shape, gan_config)

        # Create a session for running Ops on the Graph.
        sess_gan = tf.Session(config=config, graph=graph_generator)

        # Run the Op to initialize the variables.
        sess_gan.run(init_gan_op)
        saver_gan.restore(sess_gan, init_checkpoint_path_gan)

        # path where the generated images are saved
        experiment_generate_path = os.path.join(image_saving_path, gan_experiment_name + ('_%.1fT_source' % gan_config.source_field_strength))
        # make a folder for the generated images
        utils.makefolder(experiment_generate_path)

        logging.info('image generation begins')
        generated_pred = []
        batch_beginning_index = 0
        # loops through all images from the source domain
        for image_index, curr_img in zip(source_saving_indices, itertools.compress(images_test, source_saving_indices)):
            img_folder_name = 'image_test%d' % image_index
            curr_img_path = os.path.join(experiment_generate_path, img_folder_name)
            utils.makefolder(curr_img_path)
            # save source image
            source_img_name = 'source_img.nii.gz'
            utils.create_and_save_nii(np.squeeze(curr_img), os.path.join(curr_img_path, source_img_name))
            logging.info(source_img_name + ' saved')
            for noise_index, noise in noise_list:
                fake_img = sess_gan.run(x_fake_op, feed_dict={generator_img_pl: np.reshape(curr_img, img_tensor_shape),
                                                              z_noise_pl: noise})

                generated_img_name = 'generated_img_noise_%d.nii.gz' % (noise_index)
                utils.create_and_save_nii(np.squeeze(fake_img), os.path.join(curr_img_path, generated_img_name))
                logging.info(generated_img_name + ' saved')

                # save the difference g(xs)-xs
                difference_image_gs = np.squeeze(fake_img - curr_img)
                difference_img_name = 'difference_img_noise_%d.nii.gz' % (noise_index)
                utils.create_and_save_nii(difference_image_gs, os.path.join(curr_img_path, difference_img_name))
                logging.info(difference_img_name + ' saved')

        logging.info('generated all images for %s' % (gan_experiment_name))


def generate_noise_list():
    return [np.zeros(shape=(1, 10))]


if __name__ == '__main__':
    # settings
    gan_experiment_list = [
        'bousmalis_bn_dropout_keep0.9_10_noise_all_small_data_0l1_i1',
        'bousmalis_bn_dropout_keep0.9_10_noise_all_small_data_1e5l1_i1',
        'bousmalis_bn_dropout_keep0.9_no_noise_all_small_data_1e5l1_i1',
        'bousmalis_bn_dropout_keep0.9_no_noise_all_small_data_i1',
        'bousmalis_gen_n16b4_disc_n8_bn_dropout_keep0.9_no_noise_all_small_data_1e4l1_i1',
        'bousmalis_gen_n16b4_disc_n8_bn_dropout_keep0.9_no_noise_all_small_data_1e5l1_i1',
        'residual_identity_gen_bs2_std_disc_all_small_data_5e5l1_i1',
        'residual_identity_gen_bs2_std_disc_all_small_data_i1',
        'residual_identity_gen_bs20_std_disc_10_noise_all_small_data_1e4l1_bn_i1'
    ]
    gan_log_root = os.path.join(sys_config.log_root, 'gan/all_small_images')
    image_saving_path = os.path.join(sys_config.project_root,'data/generated_images/all_data_size_64_80_64_res_1.5_1.5_1.5_lbl_0_2_intrangeone_offset_0_0_-10')
    image_saving_indices = set(range(0, 120, 20))

    # put paths for experiments together
    gan_log_path_list = [os.path.join(gan_log_root, gan_name) for gan_name in gan_experiment_list]

    noise_list = generate_noise_list()

    generate_with_noise(gan_experiment_path_list=gan_log_path_list,
                                     noise_list=noise_list,
                                     image_saving_indices=image_saving_indices,
                                     image_saving_path=image_saving_path)






