from __future__ import absolute_import, division, print_function

from unittest import TestCase

import torch
from torch.autograd import Variable
from pyro.distributions import MultivariateNormal


class TestMultivariateNormal(TestCase):
    """
    Tests if the gradients of batch_log_pdf are the same regardless of normalization.
    """

    def setUp(self):
        N = 400
        self.L_tensor = torch.tril(1e-3 * torch.ones(N, N)).t()
        self.mu = Variable(torch.rand(N))
        self.L = Variable(self.L_tensor, requires_grad=True)
        self.sigma = Variable(torch.mm(self.L_tensor.t(), self.L_tensor), requires_grad=True)
        # Draw from an unrelated distribution as not to interfere with the gradients
        self.sample = Variable(torch.randn(N))

        self.cholesky_mv_normalized = MultivariateNormal(self.mu, scale_tril=self.L, normalized=True)
        self.cholesky_mv = MultivariateNormal(self.mu, scale_tril=self.L, normalized=False)

        self.full_mv_normalized = MultivariateNormal(self.mu, self.sigma, normalized=True)
        self.full_mv = MultivariateNormal(self.mu, self.sigma, normalized=False)

    def test_log_pdf_gradients_cholesky(self):
        self.cholesky_mv.log_pdf(self.sample).backward()
        grad1 = self.L.grad.data.clone()
        self.L.grad.data.zero_()

        self.cholesky_mv_normalized.log_pdf(self.sample).backward()
        grad2 = self.L.grad.data.clone()
        self.L.grad.data.zero_()

        assert torch.dist(grad1, grad2) < 1e-6

    def test_log_pdf_gradients(self):
        self.full_mv.log_pdf(self.sample).backward()
        grad1 = self.sigma.grad.data.clone()
        self.sigma.grad.data.zero_()

        self.full_mv_normalized.log_pdf(self.sample).backward()
        grad2 = self.sigma.grad.data.clone()
        self.sigma.grad.data.zero_()

        assert torch.dist(grad1, grad2) < 1e-6
