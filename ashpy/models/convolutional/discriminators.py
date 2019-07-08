# Copyright 2019 Zuru Tech HK Limited. All Rights Reserved.
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
# http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.

"""
Discriminators
"""
import typing
from typing import List, Tuple, Union

import tensorflow as tf
from tensorflow import keras

from ashpy.layers.layers import Attention, InstanceNormalization
from ashpy.models.convolutional.encoders import BaseEncoder
from ashpy.models.gans import Discriminator

__ALL__ = ["PatchDiscriminator", "MultiScaleDiscriminator"]


class PatchDiscriminator(Discriminator):
    """
    Pix2Pix discriminator:
    The last layer is an image in which each pixels is the probability of being fake or real.
    """

    def __init__(
        self,
        input_res: int,
        min_res: int,
        kernel_size: int,
        initial_filters: int,
        filters_cap: int,
        use_dropout: bool = True,
        dropout_prob: float = 0.3,
        non_linearity: typing.Type[keras.layers.Layer] = keras.layers.LeakyReLU,
        normalization_layer: typing.Type[keras.layers.Layer] = InstanceNormalization,
        use_attention: bool = False,
    ):
        """
        PatchDiscriminator used by pix2pix, when min_res=1 this is the same as a standard
        fully convolutional discriminator

        Args:
            input_res (int): Input Resolution
            min_res (int): Minimum Resolution reached by the discriminator
            kernel_size (int): Kernel Size used in Conv Layer
            initial_filters (int): number of filters in the first convolutional layer
            filters_cap (int): Maximum number of filters
            use_dropout (bool): whether to use dropout
            dropout_prob (float): probability of dropout
            non_linearity (:class:`tf.keras.layers.Layer`): non linearity used in the model
            normalization_layer (:class:`tf.keras.layers.Layer`): normalization layer used in the model
            use_attention (bool): whether to use attention
        """
        self.use_attention = use_attention
        self.layer_count = 0
        self.normalization_layer = normalization_layer
        super().__init__(
            layer_spec_input_res=input_res,
            layer_spec_target_res=min_res,
            kernel_size=kernel_size,
            initial_filters=initial_filters,
            filters_cap=filters_cap,
            output_shape=None,
            use_dropout=use_dropout,
            dropout_prob=dropout_prob,
            non_linearity=non_linearity,
        )
        # concatenate inputs on channel dimension
        self.concatenate = keras.layers.Concatenate(axis=-1)
        self.inputs = [1, 1]

    def _add_final_block(self, output_shape):
        initializer = tf.random_normal_initializer(0.0, 0.02)
        # last layer mapping to one channel with Linear activation
        # Notice: The activation is linear since we use the BCE from logits
        self.model_layers.append(tf.keras.layers.ZeroPadding2D())  # (bs, 34, 34, 256)
        self.model_layers.append(
            tf.keras.layers.Conv2D(
                512,
                self.kernel_size,
                strides=1,
                kernel_initializer=initializer,
                use_bias=False,
            )
        )  # (bs, 31, 31, 512)

        self.model_layers.append(self.normalization_layer())

        self.model_layers.append(self.non_linearity())

        self.model_layers.append(tf.keras.layers.ZeroPadding2D())  # (bs, 33, 33, 512)

        self.model_layers.append(
            tf.keras.layers.Conv2D(
                1, self.kernel_size, strides=1, kernel_initializer=initializer
            )
        )  # (bs, 30, 30, 1)

    def call(self, inputs, training=False, return_features=False):
        return super().call(
            inputs=self.concatenate(inputs),
            training=training,
            return_features=return_features,
        )

    def _add_building_block(self, filters, use_bn=False):
        """
        Construct the core of the :py:obj:`tf.keras.model`.

        The layers specified here get added to the :py:obj:`tf.keras.Model` multiple times
        consuming the hyper-parameters generated in the :func:`_get_layer_spec`.

        Args:
            filters (int): Number of filters to use for this iteration of the Building Block.

        """
        initializer = tf.random_normal_initializer(0.0, 0.02)
        self.model_layers.extend(
            [
                keras.layers.Conv2D(
                    filters,
                    self.kernel_size,
                    strides=(2, 2),
                    padding="same",
                    kernel_initializer=initializer,
                )
            ]
        )

        if len(self.model_layers) > 1:
            self.model_layers.append(self.normalization_layer())
        if self.use_dropout:
            self.model_layers.append(keras.layers.Dropout(self.dropout_prob))

        self.model_layers.append(self.non_linearity())

        if self.layer_count == 2 and self.use_attention:
            self.model_layers.append(Attention(filters))

        self.layer_count += 1


class MultiScaleDiscriminator(Discriminator):
    """
    Multiscale discriminator:
    The last layer is an image in which each pixels is the probability of being fake or real.
    """

    def __init__(
        self,
        input_res: int,
        min_res: int,
        kernel_size: int,
        initial_filters: int,
        filters_cap: int,
        use_dropout: bool = True,
        dropout_prob: float = 0.3,
        non_linearity: typing.Type[keras.layers.Layer] = keras.layers.LeakyReLU,
        normalization_layer: typing.Type[keras.layers.Layer] = InstanceNormalization,
        use_attention: bool = False,
        n_discriminators: int = 1,
    ):
        """
        Multi Scale Discriminator, used by Pix2PixHD [1]_.

        Args:
            input_res (int): input resolution
            min_res (int): minimum resolution reached by the discriminators
            kernel_size (int): kernel size of discriminators
            initial_filters (int): number of initial filters in the first layer of the discriminators
            filters_cap (int): maximum number of filters in the discriminators
            use_dropout (bool): whether to use dropout
            dropout_prob (float): probability of dropout
            non_linearity (:class:`tf.keras.layers.Layer`): non linearity used in discriminators
            normalization_layer (:class:`tf.keras.layers.Layer`): normalization used by the discriminators
            use_attention (bool): whether to use attention
            n_discriminators (int): Number of discriminators

        .. [1] High-Resolution Image Synthesis and Semantic Manipulation with Conditional GANs
             https://arxiv.org/abs/1711.11585
        """
        super(BaseEncoder, self).__init__()
        self.n_discriminators = n_discriminators
        self.input_res = input_res
        self.min_res = min_res
        self.kernel_size = kernel_size
        self.initial_filters = initial_filters
        self.filters_cap = filters_cap
        self.dropout_prob = dropout_prob
        self.non_linearity = non_linearity
        self.use_dropout = use_dropout
        self.use_attention = use_attention
        self.normalization_layer = normalization_layer
        self.discriminators = []
        # instantiate the discriminators
        for i in range(self.n_discriminators):
            self.discriminators.append(
                self.build_discriminator(int(input_res / (2 ** i)))
            )
        # subsampling operation
        self.subsampling = tf.keras.layers.AvgPool2D()
        # hack in order to accept two inputs
        self.inputs = [1, 1]

    def build_discriminator(self, input_res) -> Discriminator:
        d = PatchDiscriminator(
            input_res=input_res,
            min_res=self.min_res,
            kernel_size=self.kernel_size,
            initial_filters=self.initial_filters,
            filters_cap=self.filters_cap,
            use_dropout=self.use_dropout,
            dropout_prob=self.dropout_prob,
            non_linearity=self.non_linearity,
            use_attention=self.use_attention,
            normalization_layer=self.normalization_layer,
        )
        return d

    def call(
        self, inputs, training=True, return_features=False
    ) -> Union[List[tf.Tensor], Tuple[List[tf.Tensor], List[tf.Tensor]]]:
        """
        Args:
            inputs: input tensor
            training (bool): whether is training or not
            return_features (bool): whether to return features or not

        Returns:
            - A List of Tensors containing the value of D_i for each input.
            - A List of features for each discriminator if `return_features`

        """
        xs, condition = (
            inputs
        )  # inputs is a tuple containing the generated images and the conditions
        outs = []
        features = []

        x_i = xs
        condition_i = condition
        for i, d in enumerate(self.discriminators):
            # compute value of the i-th discriminator
            out, feat = d([x_i, condition_i], training=training, return_features=True)

            # append output and features
            outs.append(out)
            features.extend(feat)
            # reduce input size
            if i != len(self.discriminators) - 1:
                x_i = self.subsampling(x_i)
                condition_i = self.subsampling(condition_i)

        # handle output values
        if return_features:
            return outs, features
        return outs