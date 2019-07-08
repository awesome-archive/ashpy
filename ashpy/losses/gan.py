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

"""GAN losses."""
from enum import Enum
from typing import List, Union, Type

import tensorflow as tf
from ashpy.contexts import GANContext

from ashpy.losses.executor import Executor, SumExecutor


class AdversarialLossType(Enum):
    GAN = 0  # classical gan loss (minmax)
    LSGAN = 1  # Least Square GAN


class GANExecutor(Executor):
    """
    Executor for GANs. Implements the basic functions needed by the GAN losses
    """

    @staticmethod
    def get_discriminator_inputs(
        context: GANContext,
        fake_or_real: tf.Tensor,
        condition: tf.Tensor,
        training: bool,
    ) -> Union[tf.Tensor, List[tf.Tensor]]:
        r"""
        Returns the discriminator inputs. If needed it uses the encoder.
        The current implementation uses the number of inputs to determine
        whether the discriminator is conditioned or not.
        Args:
            context (:py:class:`ashpy.contexts.gan.GANContext`): context for GAN models
            fake_or_real (:py:class:`tf.Tensor`): discriminator input tensor, it can be fake (generated) or real
            condition (:py:class:`tf.Tensor`): discriminator condition (it can also be generator noise)
            training (bool): whether is training phase or not

        Returns:
            The discriminator inputs.

        """
        num_inputs = len(context.discriminator_model.inputs)

        # Handle encoder
        if hasattr(context, "encoder_model"):
            if num_inputs == 2:
                d_inputs = [
                    fake_or_real,
                    context.encoder_model(fake_or_real, training=training),
                ]
            elif num_inputs == 3:
                d_inputs = [
                    fake_or_real,
                    context.encoder_model(fake_or_real, training=training),
                    condition,
                ]
            else:
                raise ValueError(
                    f"Context has encoder_model, but generator has only {num_inputs} inputs"
                )
        else:
            if num_inputs == 2:
                d_inputs = [fake_or_real, condition]
            else:
                d_inputs = fake_or_real

        return d_inputs


class AdversarialLossG(GANExecutor):
    r"""
    Base class for the adversarial loss of the generator
    """

    def __init__(self, loss_fn=None):
        """
        Args:
            loss_fn: loss_fn to call passing (tf.ones_like(d_fake_i), d_fake_i)
        """
        super().__init__(loss_fn)

    @Executor.reduce_loss
    def call(self, context, *, fake, condition, training, **kwargs):
        r"""
        Call: setup the discriminator inputs and calls `loss_fn`
        Args:
            context: GAN Context
            fake: fake images
            condition: generator condition
            training: if training or evaluation
        Returns:
            The loss for each example
        """

        fake_inputs = self.get_discriminator_inputs(
            context=context, fake_or_real=fake, condition=condition, training=training
        )

        d_fake = context.discriminator_model(fake_inputs, training=training)

        # support for Multiscale discriminator
        # TODO: Improve
        if isinstance(d_fake, list):
            value = tf.add_n(
                [
                    tf.reduce_mean(
                        self._fn(tf.ones_like(d_fake_i), d_fake_i), axis=[1, 2]
                    )
                    for d_fake_i in d_fake
                ]
            )
            return value
        else:
            value = self._fn(tf.ones_like(d_fake), d_fake)
            value = tf.cond(
                tf.equal(tf.rank(d_fake), tf.constant(4)),
                lambda: value,
                lambda: tf.expand_dims(tf.expand_dims(value, axis=-1), axis=-1),
            )
            return tf.reduce_mean(value, axis=[1, 2])


class GeneratorBCE(AdversarialLossG):
    r"""
    The Binary CrossEntropy computed among the generator and the 1 label.

    .. math::
        L_{G} =  E [\log (D( G(z))]

    """

    def __init__(self, from_logits=True):
        self.name = "GeneratorBCE"
        super().__init__(tf.losses.BinaryCrossentropy(from_logits=from_logits))


class GeneratorLSGAN(AdversarialLossG):
    r"""
    Least Square GAN Loss for generator
    Reference: https://arxiv.org/abs/1611.04076
    Basically the Mean Squared Error between
    the discriminator output when evaluated in fake and 1

    .. math::
        L_{G} =  \frac{1}{2} E [(1 - D(G(z))^2]

    """

    def __init__(self):
        super().__init__(tf.keras.losses.MeanSquaredError())
        self.name = "GeneratorLSGAN"


class GeneratorL1(GANExecutor):
    r"""
    L1 loss between the generator output and the target.

    .. math::
        L_G = E ||x - G(z)||_1

    where x is the target and G(z) is generated image.

    """

    class L1Loss(tf.losses.Loss):
        def __init__(self):
            super().__init__()
            self._reduction = tf.losses.Reduction.SUM_OVER_BATCH_SIZE

        @property
        def reduction(self):
            return self._reduction

        @reduction.setter
        def reduction(self, value):
            self._reduction = value

        def call(self, x, y):
            """
            For each element the mean of the l1 between x and y
            """
            if self._reduction == tf.losses.Reduction.SUM_OVER_BATCH_SIZE:
                axis = None
            elif self._reduction == tf.losses.Reduction.NONE:
                axis = (1, 2, 3)
            else:
                raise ValueError("L1Loss: unhandled reduction type")

            return tf.reduce_mean(tf.abs(x - y), axis=axis)

    def __init__(self):
        super().__init__(GeneratorL1.L1Loss())

    @Executor.reduce_loss
    def call(self, context, *, fake, real, **kwargs):
        mae = self._fn(fake, real)
        return mae


class FeatureMatchingLoss(GeneratorL1):
    r"""
    Conditional GAN Feature matching loss.
    The loss is computed for each example and it's the L1 (MAE) of the feature difference.
    Implementation of pix2pix HD: https://github.com/NVIDIA/pix2pixHD

    .. math::
        \text{FM} = \sum_{i=0}^N \frac{1}{M_i} ||D_i(x, c) - D_i(G(c), c) ||_1

    Where:

    - D_i is the i-th layer of the discriminator
    - N is the total number of layer of the discriminator
    - M_i is the number of components for the i-th layer
    - x is the target image
    - c is the condition
    - G(c) is the generated image from the condition c
    - || ||_1 stands for norm 1.

    This is for a single example: basically for each layer of the discriminator we compute the absolute error between
    the layer evaluated in real examples and in fake examples.
    Then we average along the batch. In the case where D_i is a multidimensional tensor we simply calculate the mean
    over the axis 1,2,3.
    """

    @Executor.reduce_loss
    def call(self, context, *, fake, real, condition, training, **kwargs):
        fake_inputs = self.get_discriminator_inputs(
            context, fake_or_real=fake, condition=condition, training=training
        )

        real_inputs = self.get_discriminator_inputs(
            context, fake_or_real=real, condition=condition, training=training
        )

        _, features_fake = context.discriminator_model(
            fake_inputs, training=training, return_features=True
        )
        _, features_real = context.discriminator_model(
            real_inputs, training=training, return_features=True
        )

        # for each feature the L1 between the real and the fake
        # every call to fn should return [batch_size, 1] that is the mean L1
        feature_loss = [
            self._fn(feat_real_i, feat_fake_i)
            for feat_real_i, feat_fake_i in zip(features_real, features_fake)
        ]
        mae = tf.add_n(feature_loss)
        return mae


class CategoricalCrossEntropy(Executor):
    r"""
    Categorical Cross Entropy between generator output and target.
    Useful when the output of the generator is a distribution over classes
    The target must be represented in one hot notation
    """

    def __init__(self):
        self.name = "CrossEntropy"
        super().__init__(tf.keras.losses.CategoricalCrossentropy())

    @Executor.reduce_loss
    def call(self, context, *, fake, real, **kwargs):
        """
        Compute the categorical cross entropy loss
        Args:
            context: unused
            fake: fake images G(condition)
            real: Real images x(c)
            **kwargs:

        Returns:
            The categorical cross entropy loss for each example

        """
        loss_value = tf.reduce_mean(self._fn(real, fake), axis=[1, 2])
        return loss_value


class Pix2PixLoss(SumExecutor):
    r"""
    Weighted sum of :py:class:`ashpy.losses.gan.GeneratorL1`, :py:class:`ashpy.losses.gan.AdversarialLossG` and
    :py:class:`ashpy.losses.gan.FeatureMatchingLoss`.
    Used by Pix2Pix [1] and Pix2PixHD [2]

    .. [1] Image-to-Image Translation with Conditional Adversarial Networks
             https://arxiv.org/abs/1611.07004
    .. [2] High-Resolution Image Synthesis and Semantic Manipulation with Conditional GANs
             https://arxiv.org/abs/1711.11585

    """

    def __init__(
        self,
        l1_loss_weight=100.0,
        adversarial_loss_weight=1.0,
        feature_matching_weight=10.0,
        adversarial_loss_type: AdversarialLossType = AdversarialLossType.GAN,
        use_feature_matching_loss: bool = False,
    ):
        r"""
        Weighted sum of :py:class:`ashpy.losses.gan.GeneratorL1`, :py:class:`ashpy.losses.gan.AdversarialLossG` and
        :py:class:`ashpy.losses.gan.FeatureMatchingLoss`.

        Args:
            l1_loss_weight: weight of L1 loss (scalar, :py:class:`tf.Tensor`, callable)
            adversarial_loss_weight: weight of adversarial loss (scalar, :py:class:`tf.Tensor`, callable)
            feature_matching_weight: weight of the feature matching loss (scalar, :py:class:`tf.Tensor`, callable)
            adversarial_loss_type (:py:class:`ashpy.losses.gan.AdversarialLossType`): Adversarial loss type
                                                                     (:py:class:`ashpy.losses.gan.AdversarialLossType.GAN`
                                                                     or :py:class:`ashpy.losses.gan.AdversarialLossType.LSGAN`)
            use_feature_matching_loss (bool): if True use also :py:class:`ashpy.losses.gan.FeatureMatchingLoss`

        """
        executors = [
            GeneratorL1() * l1_loss_weight,
            get_adversarial_loss_generator(adversarial_loss_type)()
            * adversarial_loss_weight,
        ]

        if use_feature_matching_loss:
            executors.append(FeatureMatchingLoss() * feature_matching_weight)

        super().__init__(executors)


class Pix2PixLossSemantic(SumExecutor):
    """
    Weighted sum of :py:class:`ashpy.losses.gan.CategoricalCrossEntropy`, :py:class:`ashpy.losses.gan.AdversarialLossG` and
    :py:class:`ashpy.losses.gan.FeatureMatchingLoss`
    """

    def __init__(
        self,
        cross_entropy_weight=100.0,
        adversarial_loss_weight=1.0,
        feature_matching_weight=10.0,
        adversarial_loss_type: AdversarialLossType = AdversarialLossType.GAN,
        use_feature_matching_loss: bool = False,
    ):
        r"""
        Weighted sum of :py:class:`ashpy.losses.gan.CategoricalCrossEntropy`, :py:class:`ashpy.losses.gan.AdversarialLossG` and
        :py:class:`ashpy.losses.gan.FeatureMatchingLoss`
        Args:
            cross_entropy_weight: weight of the categorical cross entropy loss (scalar, :py:class:`tf.Tensor`, callable)
            adversarial_loss_weight: weight of the adversarial loss (scalar, :py:class:`tf.Tensor`, callable)
            feature_matching_weight: weight of the feature matching loss (scalar, :py:class:`tf.Tensor`, callable)
            adversarial_loss_type (:py:class:`ashpy.losses.gan.AdversarialLossType`): type of adversarial loss,
                                                                     see :py:class:`ashpy.losses.gan.AdversarialLossType`
            use_feature_matching_loss (bool): whether to use feature matching loss or not
        """
        executors = [
            CategoricalCrossEntropy() * cross_entropy_weight,
            get_adversarial_loss_generator(adversarial_loss_type)()
            * adversarial_loss_weight,
        ]

        if use_feature_matching_loss:
            executors.append(FeatureMatchingLoss() * feature_matching_weight)
        super().__init__(executors)


class EncoderBCE(Executor):
    """The Binary Cross Entropy computed among the encoder and the 0 label.
    TODO: Check if this supports condition
    """

    def __init__(self, from_logits=True):
        super().__init__(tf.losses.BinaryCrossentropy(from_logits=from_logits))

    @Executor.reduce_loss
    def call(self, context, *, real, training, **kwargs):
        encode = context.encoder_model(real, training=training)
        d_real = context.discriminator_model([real, encode], training=training)
        return self._fn(tf.zeros_like(d_real), d_real)


class AdversarialLossD(GANExecutor):
    r"""
    Base class for the adversarial loss of the discriminator
    """

    def __init__(self, loss_fn=None):
        r"""
        Args:
            loss_fn to call passing (d_real, d_fake)
        """
        super().__init__(loss_fn)

    @Executor.reduce_loss
    def call(self, context, *, fake, real, condition, training, **kwargs):
        r"""
        Call: setup the discriminator inputs and calls `loss_fn`

        Args:
            context: GAN Context
            fake: fake images corresponding to the condition G(c)
            real: real images corresponding to the condition x(c)
            condition: condition for the generator and discriminator
            training: if training or evaluation

        Returns:
            The loss for each example
        """

        fake_inputs = self.get_discriminator_inputs(
            context, fake_or_real=fake, condition=condition, training=training
        )

        real_inputs = self.get_discriminator_inputs(
            context, fake_or_real=real, condition=condition, training=training
        )

        d_fake = context.discriminator_model(fake_inputs, training=training)
        d_real = context.discriminator_model(real_inputs, training=training)

        if isinstance(d_fake, list):
            value = tf.add_n(
                [
                    tf.reduce_mean(self._fn(d_real_i, d_fake_i), axis=[1, 2])
                    for d_real_i, d_fake_i in zip(d_real, d_fake)
                ]
            )
            return value
        else:
            value = self._fn(d_real, d_fake)
            value = tf.cond(
                tf.equal(tf.rank(d_fake), tf.constant(4)),
                lambda: value,
                lambda: tf.expand_dims(tf.expand_dims(value, axis=-1), axis=-1),
            )
            return tf.reduce_mean(value, axis=[1, 2])


class DiscriminatorMinMax(AdversarialLossD):
    r"""
    The min-max game played by the discriminator.

    .. math::
        L_{D} =  - \frac{1}{2} E [\log(D(x)) + \log (1 - D(G(z))]

    """

    class GANLoss(tf.losses.Loss):
        def __init__(self, from_logits=True, label_smoothing=0.0):
            self._positive_bce = tf.losses.BinaryCrossentropy(
                from_logits=from_logits,
                label_smoothing=label_smoothing,
                reduction=tf.losses.Reduction.NONE,
            )

            self._negative_bce = tf.losses.BinaryCrossentropy(
                from_logits=from_logits,
                label_smoothing=0.0,
                reduction=tf.losses.Reduction.NONE,
            )
            super().__init__()

        @property
        def reduction(self):
            return self._positive_bce.reduction

        @reduction.setter
        def reduction(self, value):
            self._positive_bce.reduction = value
            self._negative_bce.reduction = value

        def call(self, d_real, d_fake):
            """Play the DiscriminatorMinMax game between the discriminator computed in real
            and the discriminator compute with fake inputs."""

            return 0.5 * (
                self._positive_bce(tf.ones_like(d_real), d_real)
                + self._negative_bce(tf.zeros_like(d_fake), d_fake)
            )

    def __init__(self, from_logits=True, label_smoothing=0.0):
        super().__init__(
            DiscriminatorMinMax.GANLoss(
                from_logits=from_logits, label_smoothing=label_smoothing
            )
        )


class DiscriminatorLSGAN(AdversarialLossD):
    r"""
    Least square Loss for discriminator.

    Reference: Least Squares Generative Adversarial Networks [1]_ .

    Basically the Mean Squared Error between
    the discriminator output when evaluated in fake and 0
    and the discriminator output when evaluated in real and 1:

    .. math::
        L_{D} = \frac{1}{2} E[(D(x) - 1)^2 + (0 - D(G(z))^2]

    .. [1] https://arxiv.org/abs/1611.04076

    """

    class LeastSquareLoss(tf.losses.Loss):
        def __init__(self):
            self._positive_mse = tf.keras.losses.MeanSquaredError(
                reduction=tf.losses.Reduction.NONE
            )
            self._negative_mse = tf.keras.losses.MeanSquaredError(
                reduction=tf.losses.Reduction.NONE
            )
            super().__init__()

        @property
        def reduction(self):
            return self._positive_mse.reduction

        @reduction.setter
        def reduction(self, value):
            self._positive_mse.reduction = value
            self._negative_mse.reduction = value

        def call(self, d_real, d_fake):
            return 0.5 * (
                self._positive_mse(tf.ones_like(d_real), d_real)
                + self._negative_mse(tf.zeros_like(d_fake), d_fake)
            )

    def __init__(self):
        super().__init__(DiscriminatorLSGAN.LeastSquareLoss())
        self.name = "DiscriminatorLSGAN"


###
# Utility functions in order to get the correct loss
###


def get_adversarial_loss_discriminator(
    adversarial_loss_type: Union[AdversarialLossType, int] = AdversarialLossType.GAN
) -> Type[Executor]:
    r"""
    Returns the correct loss fot the discriminator

    Args:
        adversarial_loss_type (:py:class:`ashpy.losses.gan.AdversarialLossType`): Type of loss (:py:class:`ashpy.losses.gan.AdversarialLossType.GAN` or :py:class:`ashpy.losses.gan.AdversarialLossType.LSGAN`)

    Returns:
        The correct (:py:class:`ashpy.losses.executor.Executor`) (to be instantiated)
    """
    if (
        adversarial_loss_type == AdversarialLossType.GAN
        or adversarial_loss_type == AdversarialLossType.GAN.value
    ):
        return DiscriminatorMinMax
    elif (
        adversarial_loss_type == AdversarialLossType.LSGAN
        or adversarial_loss_type == AdversarialLossType.LSGAN.value
    ):
        return DiscriminatorLSGAN
    else:
        raise ValueError(
            "Loss type not supported, the implemented losses are DiscriminatorMinMax or LSGAN"
        )


def get_adversarial_loss_generator(
    adversarial_loss_type: Union[AdversarialLossType, int] = AdversarialLossType.GAN
) -> Type[Executor]:
    r"""
    Returns the correct loss fot the generator

    Args:
        adversarial_loss_type (:py:class:`ashpy.losses.gan.AdversarialLossType`): Type of loss (:py:class:`ashpy.losses.gan.AdversarialLossType.GAN` or :py:class:`ashpy.losses.gan.AdversarialLossType.LSGAN`)

    Returns:
        The correct (:py:class:`ashpy.losses.executor.Executor`) (to be instantiated)
    """
    if (
        adversarial_loss_type == AdversarialLossType.GAN
        or adversarial_loss_type == AdversarialLossType.GAN.value
    ):
        return GeneratorBCE
    elif (
        adversarial_loss_type == AdversarialLossType.LSGAN
        or adversarial_loss_type == AdversarialLossType.LSGAN.value
    ):
        return GeneratorLSGAN
    else:
        raise ValueError(
            "Loss type not supported, the implemented losses are DiscriminatorMinMax or LSGAN"
        )