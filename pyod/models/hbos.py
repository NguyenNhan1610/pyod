# -*- coding: utf-8 -*-
"""Histogram-based Outlier Detection (HBOS)
"""
# Author: Yue Zhao <yuezhao@cs.toronto.edu>
# License: BSD 2 clause

from __future__ import division
from __future__ import print_function

import numpy as np
from sklearn.utils import check_array
from sklearn.utils.validation import check_is_fitted

from ..utils.utility import check_parameter

from .base import BaseDetector


class HBOS(BaseDetector):
    """
    Histogram- based outlier detection (HBOS) is an efficient unsupervised
    method [1]. It assumes the feature independence and calculates the degree
    of outlyingness by building histograms. See :cite:`goldstein2012histogram`
    for details.

    :param n_bins: The number of bins
    :type n_bins: int, optional (default=10)

    :param alpha: The regularizer for preventing overflow
    :type alpha: float in (0, 1), optional (default=0.1)

    :param tol: The parameter to decide the flexibility while dealing
        the samples falling outside the bins.
    :type tol: float in (0, 1), optional (default=0.1)

    :param contamination: The amount of contamination of the data set, i.e.
        the proportion of outliers in the data set. When fitting this is used
        to define the threshold on the decision function.
    :type contamination: float in (0., 0.5), optional (default=0.1)

    :var bin_edges\_: The edges of the bins
    :vartype bin_edges\_: numpy array of shape (n_bins + 1, n_features )

    :var hist\_: The density of each histogram
    :vartype hist\_: numpy array of shape (n_bins, n_features)
    """

    def __init__(self, n_bins=10, alpha=0.1, tol=0.5, contamination=0.1):

        super(HBOS, self).__init__(contamination=contamination)
        self.n_bins = n_bins
        self.alpha = alpha
        self.tol = tol

        check_parameter(alpha, 0, 1, param_name='alpha')
        check_parameter(tol, 0, 1, param_name='tol')

    def fit(self, X, y=None):

        # Validate inputs X and y (optional)
        X = check_array(X)
        self._set_n_classes(y)

        n_samples, n_features = X.shape[0], X.shape[1]
        self.hist_ = np.zeros([self.n_bins, n_features])
        self.bin_edges_ = np.zeros([self.n_bins + 1, n_features])

        # build the histograms for all dimensions
        for i in range(n_features):
            self.hist_[:, i], self.bin_edges_[:, i] = \
                np.histogram(X[:, i], bins=self.n_bins, density=True)
            # the sum of (width * height) should equal to 1
            assert (np.isclose(1, np.sum(
                self.hist_[:, i] * np.diff(self.bin_edges_[:, i])), atol=0.1))

        outlier_scores = self._calculate_outlier_scores(X)

        # Invert decision_scores_. Outliers comes with higher outlier scores
        self.decision_scores_ = np.sum(outlier_scores, axis=1) * -1
        self._process_decision_scores()
        return self

    def decision_function(self, X):
        check_is_fitted(self, ['hist_', 'bin_edges_'])
        X = check_array(X)

        outlier_scores = self._calculate_outlier_scores(X)

        return np.sum(outlier_scores, axis=1).ravel() * -1

    def _calculate_outlier_scores(self, X):
        """
        The internal function to calculate the outlier scores based on
        the bins and histograms constructed with the training data

        :param X: The input samples
        :type X: numpy array of shape (n_samples, n_features)

        :return: outlier scores on all features (dimensions)
        :rtype: numpy array of shape (n_samples, n_features)
        """
        n_samples, n_features = X.shape[0], X.shape[1]
        outlier_scores = np.zeros([n_samples, n_features])
        for i in range(n_features):

            # Find the indices of the bins to which each value belongs.
            # See documentation for np.digitize since it is tricky
            # >>> x = np.array([0.2, 6.4, 3.0, 1.6, -1, 100, 10])
            # >>> bins = np.array([0.0, 1.0, 2.5, 4.0, 10.0])
            # >>> np.digitize(x, bins, right=True)
            # array([1, 4, 3, 2, 0, 5, 4], dtype=int64)

            bin_inds = np.digitize(X[:, i], self.bin_edges_[:, i],
                                   right=True)

            # Calculate the outlying scores on dimension i
            # Add a regularizer for preventing overflow
            out_score_i = np.log2(self.hist_[:, i] + self.alpha)

            for j in range(n_samples):

                # If the sample does not belong to any bins
                # bin_ind == 0 (fall outside since it is too small)
                if bin_inds[j] == 0:
                    dist = self.bin_edges_[0, i] - X[j, i]
                    bin_width = self.bin_edges_[1, i] - self.bin_edges_[0, i]

                    # If it is only slightly lower than the smallest bin edge
                    # assign it to bin 1
                    if dist <= bin_width * self.tol:
                        outlier_scores[j, i] = out_score_i[0]
                    else:
                        outlier_scores[j, i] = np.min(out_score_i)

                # If the sample does not belong to any bins
                # bin_ind == n_bins+1 (fall outside since it is too large)
                elif bin_inds[j] == self.n_bins + 1:
                    dist = X[j, i] - self.bin_edges_[-1, i]
                    bin_width = self.bin_edges_[-1, i] - self.bin_edges_[-2, i]

                    # If it is only slightly larger than the largest bin edge
                    # assign it to the last bin
                    if dist <= bin_width * self.tol:
                        outlier_scores[j, i] = out_score_i[self.n_bins - 1]
                    else:
                        outlier_scores[j, i] = np.min(out_score_i)
                else:
                    outlier_scores[j, i] = out_score_i[bin_inds[j] - 1]

        return outlier_scores
