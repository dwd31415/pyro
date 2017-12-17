from __future__ import absolute_import, division, print_function

import numpy as np
import torch
from torch.autograd import Variable
from pyro.distributions.distribution import Distribution


class MultivariateNormal(Distribution):
    """
    Multivariate normal (Gaussian) distribution.

    A distribution over vectors in which all the elements have a joint
    Gaussian distribution. Currently does not support batching parameters.

    :param torch.autograd.Variable mu: Mean. Must be a vector (Variable containing a 1d Tensor).
    :param torch.autograd.Variable sigma: Covariance matrix. Must be
    symmetric and positive semidefinite.
    :param is_cholesky: Should be set to True if you want to directly pass a
    Cholesky decomposition of the covariance matrix as sigma.
    :param use_inverse_for_batch_log: If this is set to true, the torch.inverse
    function will be used to compute the log_pdf. This means that the results of log_pdf can be differentiated with
    reference to sigma. Since the gradient of torch.potri is currently not implemented differentiation of log_pdf wrt
    sigma is not possible when using the Cholesky decomposition, it is however much faster and therefore enabled by
    default.
    :raises: ValueError if the shape of mean or Sigma is not supported.
    """

    def __init__(self, mu, sigma, batch_size=None, is_cholesky=False, use_inverse_for_batch_log=False, *args, **kwargs):
        self.mu = mu
        self.output_shape = mu.shape
        self.use_inverse_for_batch_log = use_inverse_for_batch_log
        self.batch_size = batch_size if batch_size is not None else 1
        if not is_cholesky:
            self.sigma = sigma
            # potrf is the very sensible name for the Cholesky decomposition in PyTorch
            self.sigma_cholesky = torch.potrf(sigma)
        else:
            self.sigma = sigma.transpose(0, 1) @ sigma
            self.sigma_cholesky = sigma
        if mu.dim() > 1:
            raise ValueError("The mean must be a vector, but got mu.size() = {}".format(mu.size()))
        if not sigma.dim() == 2:
            raise ValueError("The covariance matrix must be a matrix, but got sigma.size() = {}".format(mu.size()))

        super(MultivariateNormal, self).__init__(*args, **kwargs)

    def batch_shape(self, x=None):
        """
        Ref: :py:meth:`pyro.distributions.distribution.Distribution.batch_shape`
        """
        mu = self.mu.expand(self.batch_size, *self.mu.size()).squeeze(0)
        if x is not None:
            if x.size()[-1] != mu.size()[-1]:
                raise ValueError("The event size for the data and distribution parameters must match.\n"
                                 "Expected x.size()[-1] == self.mu.size()[0], but got {} vs {}".format(
                                    x.size(-1), mu.size(-1)))
            try:
                mu = mu.expand_as(x)
            except RuntimeError as e:
                raise ValueError("Parameter `mu` with shape {} is not broadcastable to "
                                 "the data shape {}. \nError: {}".format(mu.size(), x.size(), str(e)))

        return mu.size()[:-1]#torch.Size((self.batch_size, )) #if self.batch_size > 1 else torch.Size()

    def event_shape(self):
        """
        Ref: :py:meth:`pyro.distributions.distribution.Distribution.event_shape`
        """
        return self.mu.size()[-1:]

    def sample(self, n=-1):
        """
        A classic multivariate normal sampler.

        :param n: The number of samples to be drawn. Samples are batched along the first axis. Defaults to the
        batch_size passed to the constructor.
        Ref: :py:meth:`pyro.distributions.distribution.Distribution.sample`
        """
        batch_size = self.batch_size if n == -1 else n
        uncorrelated_standard_sample = Variable(torch.randn(batch_size, *self.mu.size()).type_as(self.mu.data))
        transformed_sample = self.mu + uncorrelated_standard_sample @ self.sigma_cholesky
        return transformed_sample

    def batch_log_pdf(self, x, normalized=True):
        """
        Return the logarithm of the probability density function evaluated at x.
        :param x: The points for which the
        log_pdf should be evaluated batched along axis 0.
        :param normalized: If set to false the normalization
        constant is omitted is the results. This might be preferable, as computing the determinant of sigma might not
        always be numerically stable. Defaults to `True`.
        :return: A `torch.autograd.Variable` of size x.size()[0]
        Ref: :py:meth:`pyro.distributions.distribution.Distribution.batch_log_pdf`
        """
        mu = self.mu
        mu.expand(self.shape(x))
        batch_size = x.size()[0] if len(x.size()) > len(self.mu.size()) else 1
        batch_log_pdf_shape = self.batch_shape(x) + (1,)
        x = x.view(batch_size, *self.mu.size())
        normalization_factor = torch.log(self.sigma_cholesky.diag()).sum() + (self.mu.shape[0] / 2) * np.log(
            2*np.pi) if normalized else 0
        sigma_inverse = torch.inverse(self.sigma) if self.use_inverse_for_batch_log else torch.potri(
            self.sigma_cholesky)
        return -(normalization_factor + 0.5 * torch.sum((x - self.mu).unsqueeze(2) * torch.bmm(
            sigma_inverse.expand(batch_size, *self.sigma_cholesky.size()),
            (x - self.mu).view(*x.size(), 1)), 1)).view(batch_log_pdf_shape)

    def analytic_mean(self):
        """
        Ref: :py:meth:`pyro.distributions.distribution.Distribution.analytic_mean`
        """
        return self.mu

    def analytic_var(self):
        """
        Ref: :py:meth:`pyro.distributions.distribution.Distribution.analytic_var`
        """
        return torch.diag(self.sigma)
