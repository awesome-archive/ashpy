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
Collection of Metrics.

.. currentmodule:: ashpy.metrics

.. rubric:: Metric

.. autosummary::
    :nosignatures:
    :toctree: metric

    metric.Metric

----

.. rubric:: Classifier

.. autosummary::
    :nosignatures:
    :toctree: classifier

    classifier.ClassifierLoss
    classifier.ClassifierMetric

----

.. rubric:: GAN

.. autosummary::
    :nosignatures:
    :toctree: gan

    gan.DiscriminatorLoss
    gan.GeneratorLoss
    gan.EncoderLoss
    gan.InceptionScore
    gan.EncodingAccuracy

----

.. rubric:: Modules

.. autosummary::
    :nosignatures:
    :toctree: metrics
    :template: autosummary/submodule.rst

    classifier
    gan
    metric

"""
from ashpy.metrics.metric import Metric
from ashpy.metrics.classifier import ClassifierLoss, ClassifierMetric
from ashpy.metrics.gan import DiscriminatorLoss, InceptionScore, EncodingAccuracy

__ALL__ = [
    "Metric",
    "ClassifierLoss",
    "ClassifierMetric",
    "DiscriminatorLoss",
    "InceptionScore",
    "EncodingAccuracy",
]
