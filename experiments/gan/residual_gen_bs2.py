from experiments.gan.standard_parameters import *

experiment_name = 'residual_identity_gen_bs2_std_disc_i2'

# Model settings
residual = True
batch_normalization = False

# model to use
def generator(z, training, scope_name='generator'):
    return model_zoo.only_conv_generator(z, training, residual=residual, batch_normalization=batch_normalization,
                                         scope_name=scope_name, hidden_layers=gen_hidden_layers, filters=gen_filters)

discriminator = model_zoo.pool_fc_discriminator_bs2