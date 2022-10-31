# -*- coding: utf-8 -*-
import numpy as np
from scipy.linalg import sqrtm

from qibo.config import PRECISION_TOL, raise_error


def purity(state):
    """Purity of a quantum state :math:`\\rho`, which is given by :math:`\\text{Tr}(\\rho^{2})`.

    Args:
        state: state vector or density matrix.

    Returns:
        Purity of quantum state :math:`\\rho`.

    """

    if (
        (len(state.shape) >= 3)
        or (len(state) == 0)
        or (len(state.shape) == 2 and state.shape[0] != state.shape[1])
    ):
        raise_error(
            TypeError,
            f"Object must have dims either (k,) or (k,k), but have dims {state.shape}.",
        )

    if len(state.shape) == 1:
        pur = np.abs(np.dot(np.conj(state), state)) ** 2
    else:
        pur = np.real(np.trace(np.dot(state, state)))

    return pur


def entropy(state, base: float = 2):
    """The von-Neumann entropy :math:`S(\\rho)` of a quantum state :math:`\\rho`, which
    is given by

    ..math::
        S(\\rho) \\coloneqq - \\text{Tr}\\left[\\rho \\, \\log(\\rho)\\right]

    Args:
        state: state vector or density matrix.
        base (float): the base of the log. Default: 2.

    Returns:
        The von-Neumann entropy :math:`S(\\rho)`.

    """

    if base <= 0.0:
        raise_error(ValueError, "log base must be non-negative.")

    if (
        (len(state.shape) >= 3)
        or (len(state) == 0)
        or (len(state.shape) == 2 and state.shape[0] != state.shape[1])
    ):
        raise_error(
            TypeError,
            f"Object must have dims either (k,) or (k,k), but have dims {state.shape}.",
        )

    if purity(state) == 1.0:
        ent = 0.0
    else:
        eigenvalues, _ = np.linalg.eig(state)
        if base == 2:
            log_prob = np.log2(
                eigenvalues, out=np.zeros_like(eigenvalues), where=(eigenvalues != 0)
            )
        elif base == 10:
            log_prob = np.log10(
                eigenvalues, out=np.zeros_like(eigenvalues), where=(eigenvalues != 0)
            )
        elif base == np.e:
            log_prob = np.log(
                eigenvalues, out=np.zeros_like(eigenvalues), where=(eigenvalues != 0)
            )
        else:
            log_prob = np.log(
                eigenvalues, out=np.zeros_like(eigenvalues), where=(eigenvalues != 0)
            ) / np.log(base)

        ent = -np.sum(eigenvalues * log_prob)
        # absolute value if entropy == 0.0 to avoid returning -0.0
        ent = np.abs(ent) if ent == 0.0 else ent

    return ent


def trace_distance(state, target):
    """Trace distance between two quantum states:

    ..math::
        T(\\rho, \\sigma) \\coloneqq \\frac{1}{2} \\, ||\\rho - \\sigma||_{1}

    where :math:`||\\cdot||_{1}` is the Schatten 1-norm.

    Args:
        state: state vector or density matrix.
        target: state vector or density matrix.

    Returns:
        Trace distance between state :math:`\\rho` and target :math:`\\sigma`.

    """

    if state.shape != target.shape:
        raise_error(
            TypeError,
            f"State has dims {state.shape} while target has dims {target.shape}.",
        )

    if (len(state.shape) >= 3) or (len(state) == 0):
        raise_error(
            TypeError,
            f"Both objects must have dims either (k,) or (k,l), but have dims {state.shape} and {target.shape}",
        )

    if len(state.shape) == 1:
        state = np.outer(np.conj(state), state)
        target = np.outer(np.conj(target), target)

    difference = state - target
    difference_sqrt = sqrtm(np.dot(np.conj(np.transpose(difference)), difference))
    return np.real(np.trace(difference_sqrt)) / 2


def hilbert_schmidt_distance(state, target):
    """Hilbert-Schmidt distance between two quantum states:

    ..math::
        <\\rho, \\sigma>_{\\text{HS}} = \\text{Tr}\\left[(\\rho - \\sigma)^{2}\\right]

    Args:
        state: state vector or density matrix.
        target: state vector or density matrix.

    Returns:
        Hilbert-Schmidt distance between state :math:`\\rho` and target :math:`\\sigma`.

    """

    if state.shape != target.shape:
        raise_error(
            TypeError,
            f"State has dims {state.shape} while target has dims {target.shape}.",
        )

    if (len(state.shape) >= 3) or (len(state) == 0):
        raise_error(
            TypeError,
            f"Both objects must have dims either (k,) or (k,l), but have dims {state.shape} and {target.shape}",
        )

    if len(state.shape) == 1:
        state = np.outer(np.conj(state), state)
        target = np.outer(np.conj(target), target)

    return np.real(np.trace((state - target) ** 2))


def fidelity(state, target, validate=False):
    """Fidelity between two quantum states (when at least one state is pure).

    ..math::
        F(\\rho, \\sigma) = \\Tr(\\rho \\, \\sigma)

    Args:
        state: state vector or density matrix.
        target: state vector or density matrix.
        validate (bool): if True, checks if one of the input states is pure. Default: False.

    Returns:
        Fidelity between state :math:`\\rho` and target :math:`\\sigma`.

    """

    if state.shape != target.shape:
        raise_error(
            TypeError,
            f"State has dims {state.shape} while target has dims {target.shape}.",
        )

    if len(state.shape) >= 3 or len(state.shape) == 0:
        raise_error(
            TypeError,
            f"Both objects must have dims either (k,) or (k,l), but have dims {state.shape} and {target.shape}",
        )

    if validate:
        purity_state = purity(state)
        purity_target = purity(target)
        if (
            (purity_state < 1.0 - PRECISION_TOL) or (purity_state > 1.0 + PRECISION_TOL)
        ) and (
            (purity_target < 1.0 - PRECISION_TOL)
            or (purity_target > 1.0 + PRECISION_TOL)
        ):
            raise_error(
                ValueError,
                f"Neither state is pure. Purity state: {purity_state} , Purity target: {purity_target}.",
            )

    if len(state.shape) == 1 and len(target.shape) == 1:
        fid = np.abs(np.dot(np.conj(state), target)) ** 2
    elif len(state.shape) == 2 and len(target.shape) == 2:
        fid = np.real(np.trace(np.dot(state, target)))

    return fid


def process_fidelity(channel, target=None, validate=False):
    """Process fidelity between two quantum channels (when at least one channel is` unitary),

    ..math::
        F_{pro}(\\mathcal{E}, \\mathcal{U}) = \\frac{1}{d^{2}} \\, \\Tr(\\mathcal{E}^{\\dagger}, \\mathcal{U})

    Args:
        channel: quantum channel.
        target: quantum channel. If None, target is the Identity channel.

    Returns:
        Process fidelity between channels :math:`\\mathcal{E}` and target :math:`\\mathcal{U}`.

    """

    if target is not None:
        if channel.shape != target.shape:
            raise_error(
                TypeError,
                f"Channels must have the same dims, but {channel.shape} != {target.shape}",
            )

    d = int(np.sqrt(channel.shape[0]))

    if validate:
        norm_channel = np.linalg.norm(
            np.dot(np.conj(np.transpose(channel)), channel) - np.eye(d**2)
        )
        if target is None and norm_channel > PRECISION_TOL:
            raise_error(TypeError, f"Channel is not unitary and Target is None.")
        if target is not None:
            norm_target = np.linalg.norm(
                np.dot(np.conj(np.transpose(target)), target) - np.eye(d**2)
            )
            if (norm_channel > PRECISION_TOL) and (norm_target > PRECISION_TOL):
                raise_error(TypeError, f"Neither channel is unitary.")

    if target is None:
        # With no target, return process fidelity with Identity channel
        return np.real(np.trace(channel)) / d**2
    else:
        return (
            np.real(np.trace(np.dot(np.conj(np.transpose(channel)), target))) / d**2
        )


def average_gate_fidelity(channel, target=None):
    """Average gate fidelity between two quantum channels (when at least one channel is unitary),

    ..math::
        F_{avg}(\\mathcal{E}, \\mathcal{U}) = \\frac{d * F_{pro}(\\mathcal{E}, \\mathcal{U}) + 1}{d + 1}

    where :math:`d` is the dimension of the channels and :math:`F_{pro}(\\mathcal{E}, \\mathcal{U})` is the
    :meth:`~qibo.metrics.process_fidelily` of channel :math:`\\mathcal{E}` with respect to the unitary
    channel :math:`\\mathcal{U}`.

    Args:
        channel: quantum channel.
        target: quantum channel. If None, target is the Identity channel.

    Returns:
        Process fidelity between channel :math:`\\mathcal{E}` and target unitary channel :math:`\\mathcal{U}`.

    """

    d = channel.shape[0]
    return (d * process_fidelity(channel, target) + 1) / (d + 1)
