"""Module with functions that create random quantum and classical objects."""

import warnings
from functools import reduce
from typing import Union

import numpy as np

from qibo import gates
from qibo.backends import GlobalBackend, NumpyBackend
from qibo.config import MAX_ITERATIONS, PRECISION_TOL, raise_error
from qibo.models import Circuit
from qibo.quantum_info.basis import comp_basis_to_pauli
from qibo.quantum_info.superoperator_transformations import (
    choi_to_chi,
    choi_to_kraus,
    choi_to_liouville,
    choi_to_pauli,
    vectorization,
)
from qibo.quantum_info.utils import ONEQUBIT_CLIFFORD_PARAMS


def random_gaussian_matrix(
    dims: int,
    rank: int = None,
    mean: float = 0,
    stddev: float = 1,
    seed=None,
    backend=None,
):
    """Generates a random Gaussian Matrix.

    Gaussian matrices are matrices where each entry is
    sampled from a Gaussian probability distribution

    .. math::"haar",
        p(x) = \\frac{1}{\\sqrt{2 \\, \\pi} \\, \\sigma} \\, \\exp{\\left(-\\frac{(x - \\mu)^{2}}{2\\,\\sigma^{2}}\\right)}

    with mean :math:`\\mu` and standard deviation :math:`\\sigma`.

    Args:
        dims (int): dimension of the matrix.
        rank (int, optional): rank of the matrix. If ``None``, then
            ``rank == dims``. Default: ``None``.
        mean (float, optional): mean of the Gaussian distribution. Default is 0.
        stddev (float, optional): standard deviation of the Gaussian distribution.
            Default is ``1``.
        seed (int or ``numpy.random.Generator``, optional): Either a generator of random
            numbers or a fixed seed to initialize a generator. If ``None``, initializes
            a generator with a random seed. Default: ``None``.
        backend (``qibo.backends.abstract.Backend``, optional): backend to be used
            in the execution. If ``None``, it uses ``GlobalBackend()``.
            Defaults to ``None``.

    Returns:
        (ndarray): Random Gaussian matrix with dimensions ``(dims, rank)``.
    """

    if dims <= 0:
        raise_error(ValueError, "dims must be type int and positive.")

    if rank is None:
        rank = dims
    else:
        if rank > dims:
            raise_error(
                ValueError, f"rank ({rank}) cannot be greater than dims ({dims})."
            )
        elif rank <= 0:
            raise_error(ValueError, f"rank ({rank}) must be an int between 1 and dims.")

    if stddev is not None and stddev <= 0.0:
        raise_error(ValueError, "stddev must be a positive float.")

    if (
        seed is not None
        and not isinstance(seed, int)
        and not isinstance(seed, np.random.Generator)
    ):
        raise_error(
            TypeError, "seed must be either type int or numpy.random.Generator."
        )

    if backend is None:  # pragma: no cover
        backend = GlobalBackend()

    local_state = (
        np.random.default_rng(seed) if seed is None or isinstance(seed, int) else seed
    )

    dims = (dims, rank)

    matrix = 1.0j * local_state.normal(loc=mean, scale=stddev, size=dims)
    matrix += local_state.normal(loc=mean, scale=stddev, size=dims)
    matrix = backend.cast(matrix, dtype=matrix.dtype)

    return matrix


def random_hermitian(
    dims: int,
    semidefinite: bool = False,
    normalize: bool = False,
    seed=None,
    backend=None,
):
    """Generates a random Hermitian matrix :math:`H`, i.e.
    a random matrix such that :math:`H = H^{\\dagger}.`

    Args:
        dims (int): dimension of the matrix.
        semidefinite (bool, optional): if ``True``, returns a Hermitian matrix that
            is also positive semidefinite. Default is ``False``.
        normalize (bool, optional): if ``True`` and ``semidefinite=False``, returns
            a Hermitian matrix with eigenvalues in the interval
            :math:`[-1, \\, 1]`. If ``True`` and ``semidefinite=True``,
            interval is :math:`[0, \\, 1]`. Default is ``False``.
        seed (int or ``numpy.random.Generator``, optional): Either a generator of
            random numbers or a fixed seed to initialize a generator. If ``None``,
            initializes a generator with a random seed. Default is ``None``.
        backend (``qibo.backends.abstract.Backend``, optional): backend to be used
            in the execution. If ``None``, it uses ``GlobalBackend()``.
            Defaults to ``None``.

    Returns:
        (ndarray): Hermitian matrix :math:`H` with dimensions ``(dims, dims)``.
    """

    if dims <= 0:
        raise_error(ValueError, f"dims ({dims}) must be type int and positive.")

    if not isinstance(semidefinite, bool) or not isinstance(normalize, bool):
        raise_error(TypeError, "semidefinite and normalize must be type bool.")

    if backend is None:  # pragma: no cover
        backend = GlobalBackend()

    matrix = random_gaussian_matrix(dims, dims, seed=seed, backend=backend)

    if semidefinite:
        matrix = np.dot(np.transpose(np.conj(matrix)), matrix)
    else:
        matrix = (matrix + np.transpose(np.conj(matrix))) / 2

    if normalize:
        matrix = matrix / np.linalg.norm(matrix)

    return matrix


def random_unitary(dims: int, measure: str = None, seed=None, backend=None):
    """Returns a random Unitary operator :math:`U`,, i.e.
    a random operator such that :math:`U^{-1} = U^{\\dagger}`.

    Args:
        dims (int): dimension of the matrix.
        measure (str, optional): probability measure in which to sample the unitary
            from. If ``None``, functions returns :math:`\\exp{(-i \\, H)}`, where
            :math:`H` is a Hermitian operator. If ``"haar"``, returns an Unitary
            matrix sampled from the Haar measure. Defaults to ``None``.
        seed (int or ``numpy.random.Generator``, optional): Either a generator of
            random numbers or a fixed seed to initialize a generator. If ``None``,
            initializes a generator with a random seed. Defaults to ``None``.
        backend (``qibo.backends.abstract.Backend``, optional): backend to be used
            in the execution. If ``None``, it uses ``GlobalBackend()``.
            Defaults to ``None``.

    Returns:
        (ndarray): Unitary matrix :math:`U` with dimensions ``(dims, dims)``.
    """

    if dims <= 0:
        raise_error(ValueError, "dims must be type int and positive.")

    if measure is not None:
        if not isinstance(measure, str):
            raise_error(
                TypeError, f"measure must be type str but it is type {type(measure)}."
            )
        if measure != "haar":
            raise_error(ValueError, f"measure {measure} not implemented.")

    if backend is None:  # pragma: no cover
        backend = GlobalBackend()

    if measure == "haar":
        gaussian_matrix = random_gaussian_matrix(dims, dims, seed=seed, backend=backend)
        Q, R = np.linalg.qr(gaussian_matrix)
        D = np.diag(R)
        D = D / np.abs(D)
        R = np.diag(D)
        unitary = np.dot(Q, R)
    elif measure is None:
        from scipy.linalg import expm

        H = random_hermitian(dims, seed=seed, backend=NumpyBackend())
        unitary = expm(-1.0j * H / 2)

    unitary = backend.cast(unitary, dtype=unitary.dtype)

    return unitary


def random_quantum_channel(
    dims: int,
    representation: str = "liouville",
    measure: str = None,
    order: str = "row",
    normalize: bool = False,
    precision_tol: float = None,
    seed=None,
    backend=None,
):
    """Creates a random superoperator from an unitary operator in one of the
    supported superoperator representations.

    Args:
        dims (int): dimension of the unitary operator.
        representation (str, optional): If ``"chi"``, returns a random channel in the
            Chi representation. If ``"choi"``, returns channel in Choi representation.
            If ``"kraus"``, returns Kraus representation of channel. If ``"liouville"``,
            returns Liouville representation. If ``"pauli"``, returns Pauli-Liouville
            representation. Defaults to ``"liouville"``.
        measure (str, optional): probability measure in which to sample the unitary
            from. If ``None``, functions returns :math:`\\exp{(-i \\, H)}`, where
            :math:`H` is a Hermitian operator. If ``"haar"``, returns an Unitary
            matrix sampled from the Haar measure. Defaults to ``None``.
        order (str, optional): If ``"row"``, vectorization is performed row-wise.
            If ``"column"``, vectorization is performed column-wise. If ``"system"``,
            a block-vectorization is performed. Defaults to ``"row"``.
        normalize (bool, optional): used when ``representation="chi"`` or
            ``representation="pauli"``. If ``True`` assumes the normalized Pauli basis.
            If ``False``, it assumes unnormalized Pauli basis. Defaults to ``False``.
        precision_tol (float, optional): if ``representation="kraus"``, it is the
            precision tolerance for eigenvalues found in the spectral decomposition
            problem. Any eigenvalue :math:`\\lambda <` ``precision_tol`` is set
            to 0 (zero). If ``None``, ``precision_tol`` defaults to
            ``qibo.config.PRECISION_TOL=1e-8``. Defaults to ``None``.
        seed (int or ``numpy.random.Generator``, optional): Either a generator of
            random numbers or a fixed seed to initialize a generator. If ``None``,
            initializes a generator with a random seed. Defaults to ``None``.
        backend (``qibo.backends.abstract.Backend``, optional): backend to be used
            in the execution. If ``None``, it uses ``GlobalBackend()``.
            Defaults to ``None``.

    Returns:
        ndarray: Superoperator representation of a random unitary gate.
    """
    if not isinstance(representation, str):
        raise_error(
            TypeError,
            f"representation must be type str, but it is type {type(representation)}",
        )

    if representation not in ["chi", "choi", "kraus", "liouville", "pauli"]:
        raise_error(ValueError, f"representation {representation} not found.")

    super_op = random_unitary(dims, measure, seed, backend)
    super_op = vectorization(super_op, order=order, backend=backend)
    super_op = np.outer(super_op, np.conj(super_op))

    if representation == "chi":
        super_op = choi_to_chi(
            super_op, normalize=normalize, order=order, backend=backend
        )
    elif representation == "kraus":
        super_op = choi_to_kraus(
            super_op,
            precision_tol=precision_tol,
            order=order,
            validate_cp=False,
            backend=backend,
        )
    elif representation == "liouville":
        super_op = choi_to_liouville(super_op, order=order, backend=backend)
    elif representation == "pauli":
        super_op = choi_to_pauli(
            super_op, normalize=normalize, order=order, backend=backend
        )

    return super_op


def random_statevector(dims: int, haar: bool = False, seed=None, backend=None):
    """Creates a random statevector :math:`\\ket{\\psi}`.

    .. math::
        \\ket{\\psi} = \\sum_{k = 0}^{d - 1} \\, \\sqrt{p_{k}} \\, e^{i \\phi_{k}} \\, \\ket{k} \\, ,

    where :math:`d` is ``dims``, and :math:`p_{k}` and :math:`\\phi_{k}` are, respectively,
    the probability and phase corresponding to the computational basis state :math:`\\ket{k}`.

    Args:
        dims (int): dimension of the matrix.
        haar (bool, optional): if ``True``, statevector is created by sampling a
            Haar random unitary :math:`U_{\\text{haar}}` and acting with it on a
            random computational basis state :math:`\\ket{k}`, i.e.
            :math:`\\ket{\\psi} = U_{\\text{haar}} \\ket{k}`. Default is ``False``.
        seed (int or ``numpy.random.Generator``, optional): Either a generator of
            random numbers or a fixed seed to initialize a generator. If ``None``,
            initializes a generator with a random seed. Default is ``None``.
        backend (``qibo.backends.abstract.Backend``, optional): backend to be used
            in the execution. If ``None``, it uses ``GlobalBackend()``.
            Defaults to ``None``.

    Returns:
        (ndarray): Random statevector :math:`\\ket{\\psi}`.
    """

    if dims <= 0:
        raise_error(ValueError, "dim must be of type int and >= 1")

    if not isinstance(haar, bool):
        raise_error(TypeError, f"haar must be type bool, but it is type {type(haar)}.")

    if (
        seed is not None
        and not isinstance(seed, int)
        and not isinstance(seed, np.random.Generator)
    ):
        raise_error(
            TypeError, "seed must be either type int or numpy.random.Generator."
        )

    if backend is None:  # pragma: no cover
        backend = GlobalBackend()

    local_state = (
        np.random.default_rng(seed) if seed is None or isinstance(seed, int) else seed
    )

    if not haar:
        probabilities = local_state.random(dims)
        probabilities = probabilities / np.sum(probabilities)
        phases = 2 * np.pi * local_state.random(dims)
        state = np.sqrt(probabilities) * np.exp(1.0j * phases)
        state = backend.cast(state, dtype=state.dtype)
    else:
        # select a random column of a haar random unitary
        k = local_state.integers(low=0, high=dims)
        state = random_unitary(dims, measure="haar", seed=seed, backend=backend)[:, k]

    return state


def random_density_matrix(
    dims: int,
    rank: int = None,
    pure: bool = False,
    metric: str = "Hilbert-Schmidt",
    basis: str = None,
    normalize: bool = False,
    seed=None,
    backend=None,
):
    """Creates a random density matrix :math:`\\rho`.

    Args:
        dims (int): dimension of the matrix.
        rank (int, optional): rank of the matrix. If ``None``, then ``rank == dims``.
            Default is ``None``.
        pure (bool, optional): if ``True``, returns a pure state. Default is ``False``.
        metric (str, optional): metric to sample the density matrix from. Options:
            ``"Hilbert-Schmidt"`` and ``"Bures"``. Default is ``"Hilbert-Schmidt"``.
        basis (str, optional): if ``"pauli"``, return random density matrix in the
            Pauli basis. If ``None``, returns it in the computational basis.
            Default is ``None``.
        normalize(bool, optional): if ``True`` and ``basis="pauli"``, returns random
            density matrix in the normalized Pauli basis. If ``False`` and
            ``basis="pauli"``, returns state in the unnormalized Pauli basis.
            Defaults to ``False``.
        seed (int or ``numpy.random.Generator``, optional): Either a generator of
            random numbers or a fixed seed to initialize a generator. If ``None``,
            initializes a generator with a random seed. Default is ``None``.
        backend (``qibo.backends.abstract.Backend``, optional): backend to be used
            in the execution. If ``None``, it uses ``GlobalBackend()``.
            Defaults to ``None``.

    Returns:
        (ndarray): Random density matrix :math:`\\rho`.
    """

    if dims <= 0:
        raise_error(ValueError, "dims must be type int and positive.")

    if rank is not None and rank > dims:
        raise_error(ValueError, f"rank ({rank}) cannot be greater than dims ({dims}).")

    if rank is not None and rank <= 0:
        raise_error(ValueError, f"rank ({rank}) must be an int between 1 and dims.")

    if not isinstance(pure, bool):
        raise_error(TypeError, f"pure must be type bool, but it is type {type(pure)}.")

    if not isinstance(metric, str):
        raise_error(
            TypeError, f"metric must be type str, but it is type {type(metric)}."
        )

    if basis is not None and not isinstance(basis, str):
        raise_error(TypeError, f"basis must be type str, but it is type {type(basis)}.")
    elif basis is not None and basis not in ["pauli"]:
        raise_error(ValueError, f"basis {basis} nor recognized.")

    if not isinstance(normalize, bool):
        raise_error(
            TypeError, f"normalize must be type bool, but it is type {type(normalize)}."
        )
    elif normalize is True and basis is None:
        raise_error(ValueError, "normalize cannot be True when basis=None.")

    if backend is None:  # pragma: no cover
        backend = GlobalBackend()

    if pure:
        state = random_statevector(dims, seed=seed, backend=backend)
        state = np.outer(state, np.transpose(np.conj(state)))
    else:
        if metric == "Hilbert-Schmidt":
            state = random_gaussian_matrix(dims, rank, seed=seed, backend=backend)
            state = np.dot(state, np.transpose(np.conj(state)))
            state = state / np.trace(state)
        elif metric == "Bures":
            nqubits = int(np.log2(dims))
            state = backend.identity_density_matrix(nqubits, normalize=False)
            state += random_unitary(dims, seed=seed, backend=backend)
            state = np.dot(
                state, random_gaussian_matrix(dims, rank, seed=seed, backend=backend)
            )
            state = np.dot(state, np.transpose(np.conj(state)))
            state = state / np.trace(state)
        else:
            raise_error(ValueError, f"metric {metric} not found.")

    state = backend.cast(state, dtype=state.dtype)

    if basis == "pauli":
        unitary = comp_basis_to_pauli(
            int(np.log2(dims)), normalize=normalize, backend=backend
        )
        state = unitary @ vectorization(state, backend=backend)

    return state


def random_clifford(
    qubits, return_circuit: bool = False, fuse: bool = False, seed=None, backend=None
):
    """Generates random Clifford operator(s).

    Args:
        qubits (int or list or ndarray): if ``int``, the number of qubits for the Clifford.
            If ``list`` or ``ndarray``, indexes of the qubits for the Clifford to act on.
        return_circuit (bool, optional): if ``True``, returns a ``qibo.gates.Unitary``
            object. If ``False``, returns an ``ndarray`` object. Default is ``False``.
        fuse (bool, optional): if ``False``, returns an ``ndarray`` with one Clifford
            gate per qubit. If ``True``, returns the tensor product of the Clifford
            gates that were sampled. Default is ``False``.
        seed (int or ``numpy.random.Generator``, optional): Either a generator of
            random numbers or a fixed seed to initialize a generator. If ``None``,
            initializes a generator with a random seed. Default is ``None``.
        backend (``qibo.backends.abstract.Backend``, optional): backend to be used
            in the execution. If ``None``, it uses ``GlobalBackend()``.
            Defaults to ``None``.

    Returns:
        (ndarray or ``qibo.gates.Unitary``): Random Clifford operator(s).
    """

    if (
        not isinstance(qubits, int)
        and not isinstance(qubits, list)
        and not isinstance(qubits, np.ndarray)
    ):
        raise_error(
            TypeError,
            f"qubits must be either type int, list or ndarray, but it is type {type(qubits)}.",
        )

    if isinstance(qubits, int) and qubits <= 0:
        raise_error(ValueError, "qubits must be a positive integer.")

    if isinstance(qubits, (list, np.ndarray)) and any(q < 0 for q in qubits):
        raise_error(ValueError, "qubit indexes must be non-negative integers.")

    if not isinstance(return_circuit, bool):
        raise_error(
            TypeError,
            f"return_circuit must be type bool, but it is type {type(return_circuit)}.",
        )

    if not isinstance(fuse, bool):
        raise_error(TypeError, f"fuse must be type bool, but it is type {type(fuse)}.")

    if (
        seed is not None
        and not isinstance(seed, int)
        and not isinstance(seed, np.random.Generator)
    ):
        raise_error(
            TypeError, "seed must be either type int or numpy.random.Generator."
        )

    if backend is None:  # pragma: no cover
        backend = GlobalBackend()

    local_state = (
        np.random.default_rng(seed) if seed is None or isinstance(seed, int) else seed
    )

    if isinstance(qubits, int):
        qubits = range(qubits)

    parameters = local_state.integers(0, len(ONEQUBIT_CLIFFORD_PARAMS), len(qubits))

    unitaries = [_clifford_unitary(*ONEQUBIT_CLIFFORD_PARAMS[p]) for p in parameters]

    if return_circuit is True:
        # tensor product of all gates generated
        unitaries = reduce(np.kron, unitaries)
        unitaries = gates.Unitary(unitaries, *qubits)
    else:
        if len(unitaries) == 1:
            unitaries = unitaries[0]
        elif fuse:
            unitaries = reduce(np.kron, unitaries)
        elif not fuse:
            unitaries = np.array(unitaries)

        unitaries = backend.cast(unitaries, dtype=unitaries.dtype)

    return unitaries


def random_pauli(
    qubits,
    depth: int,
    max_qubits: int = None,
    subset: list = None,
    return_circuit: bool = True,
    seed=None,
    backend=None,
):
    """Creates random Pauli operator(s).

    Pauli operators are sampled from the single-qubit Pauli set :math:`\\{I, X, Y, Z\\}`.

    Args:
        qubits (int or list or ndarray): if ``int`` and ``max_qubits=None``, the
            number of qubits. If ``int`` and ``max_qubits != None``, qubit index
            in which the Pauli sequence will act. If ``list`` or ``ndarray``,
            indexes of the qubits for the Pauli sequence to act.
        depth (int): length of the sequence of Pauli gates.
        max_qubits (int, optional): total number of qubits in the circuit.
            If ``None``, ``max_qubits = max(qubits)``. Defaults to ``None``.
        subset (list, optional): list containing a subset of the 4 single-qubit
            Pauli operators. If ``None``, defaults to the complete set.
            Defaults to ``None``.
        return_circuit (bool, optional): if ``True``, returns a ``qibo.models.Circuit``
            object. If ``False``, returns an ``ndarray`` with shape (qubits, depth, 2, 2)
            that contains all Pauli matrices that were sampled. Defaults to ``True``.
        seed (int or ``numpy.random.Generator``, optional): Either a generator of
            random numbers or a fixed seed to initialize a generator. If ``None``,
            initializes a generator with a random seed. Defaults to ``None``.
        backend (``qibo.backends.abstract.Backend``, optional): backend to be used
            in the execution. If ``None``, it uses ``GlobalBackend()``.
            Defaults to ``None``.

    Returns:
        (ndarray or ``qibo.models.Circuit``): all sampled Pauli operators.

    """

    if (
        not isinstance(qubits, int)
        and not isinstance(qubits, list)
        and not isinstance(qubits, np.ndarray)
    ):
        raise_error(
            TypeError,
            f"qubits must be either type int, list or ndarray, but it is type {type(qubits)}.",
        )

    if isinstance(qubits, int) and qubits < 0:
        raise_error(ValueError, "qubits must be a non-negative integer.")

    if isinstance(qubits, int) is False and any(q < 0 for q in qubits):
        raise_error(ValueError, "qubit indexes must be non-negative integers.")

    if isinstance(depth, int) and depth <= 0:
        raise_error(ValueError, "depth must be a positive integer.")

    if isinstance(max_qubits, int) and max_qubits <= 0:
        raise_error(ValueError, "max_qubits must be a positive integer.")

    if max_qubits is not None:
        if isinstance(qubits, int) and qubits >= max_qubits:
            raise_error(
                ValueError,
                f"qubit index ({qubits}) must be < max_qubits ({max_qubits}).",
            )
        elif not isinstance(qubits, int) and any(q >= max_qubits for q in qubits):
            raise_error(ValueError, "all qubit indexes must be < max_qubits.")

    if not isinstance(return_circuit, bool):
        raise_error(
            TypeError,
            f"return_circuit must be type bool, but it is type {type(return_circuit)}.",
        )

    if subset is not None and not isinstance(subset, list):
        raise_error(
            TypeError, f"subset must be type list, but it is type {type(subset)}."
        )

    if subset is not None and any(isinstance(item, str) is False for item in subset):
        raise_error(
            TypeError,
            "subset argument must be a subset of strings in the set ['I', 'X', 'Y', 'Z'].",
        )

    if (
        seed is not None
        and not isinstance(seed, int)
        and not isinstance(seed, np.random.Generator)
    ):
        raise_error(
            TypeError, "seed must be either type int or numpy.random.Generator."
        )

    if backend is None:  # pragma: no cover
        backend = GlobalBackend()

    local_state = (
        np.random.default_rng(seed) if seed is None or isinstance(seed, int) else seed
    )

    complete_set = {"I": gates.I, "X": gates.X, "Y": gates.Y, "Z": gates.Z}

    if subset is None:
        subset = complete_set
    else:
        subset = {key: complete_set[key] for key in subset}

    keys = list(subset.keys())

    if max_qubits is None:
        if isinstance(qubits, int):
            max_qubits = qubits
            qubits = range(qubits)
        else:
            max_qubits = int(max(qubits)) + 1
    else:
        if isinstance(qubits, int):
            qubits = [qubits]

    indexes = local_state.integers(0, len(subset), size=(len(qubits), depth))
    indexes = [[keys[item] for item in row] for row in indexes]

    if return_circuit:
        gate_grid = Circuit(max_qubits)
        for qubit, row in zip(qubits, indexes):
            for column_item in row:
                gate_grid.add(subset[column_item](qubit))
    else:
        gate_grid = np.array(
            [
                [subset[column_item](qubit).matrix for column_item in row]
                for qubit, row in zip(qubits, indexes)
            ]
        )
        gate_grid = backend.cast(gate_grid, dtype=gate_grid.dtype)

    return gate_grid


def random_pauli_hamiltonian(
    nqubits: int,
    max_eigenvalue: Union[int, float] = None,
    normalize: bool = False,
    seed=None,
    backend=None,
):
    """Generates a random Hamiltonian in the Pauli basis.

    Args:
        nqubits (int): number of qubits.
        max_eigenvalue (int or float, optional): fixes the value of the
            largest eigenvalue. Defaults to ``None``.
        normalize (bool, optional): If ``True``, fixes the gap of the
            Hamiltonian as ``1.0``. Moreover, if ``True``, then ``max_eigenvalue``
            must be ``> 1.0``. Defaults to ``False``.
        seed (int or ``numpy.random.Generator``, optional): Either a generator of
            random numbers or a fixed seed to initialize a generator. If ``None``,
            initializes a generator with a random seed. Defaults to ``None``.
        backend (``qibo.backends.abstract.Backend``, optional): backend to be used
            in the execution. If ``None``, it uses ``GlobalBackend()``.
            Defaults to ``None``.

    Returns:
        (ndarray, ndarray): Hamiltonian in the Pauli basis and its corresponding eigenvalues.
    """
    if isinstance(nqubits, int) is False:
        raise_error(
            TypeError, f"nqubits must be type int, but it is type {type(nqubits)}."
        )
    elif nqubits <= 0:
        raise_error(ValueError, "nqubits must be a positive int.")

    if isinstance(max_eigenvalue, (int, float)) is False and normalize is True:
        raise_error(
            TypeError,
            f"when normalize=True, max_eigenvalue must be type float, "
            + f"but it is {type(max_eigenvalue)}.",
        )
    elif (
        isinstance(max_eigenvalue, (int, float)) is False and max_eigenvalue is not None
    ):
        raise_error(
            TypeError,
            f"max_eigenvalue must be type float, but it is {type(max_eigenvalue)}.",
        )

    if isinstance(normalize, bool) is False:
        raise_error(
            TypeError,
            f"normalize must be type bool, but it is type {type(normalize)}.",
        )
    elif normalize is True and max_eigenvalue <= 1.0:
        raise_error(
            ValueError,
            "when normalize=True, gap is = 1, thus max_eigenvalue must be > 1.",
        )

    if backend is None:  # pragma: no cover
        backend = GlobalBackend()

    d = 2**nqubits

    hamiltonian = random_hermitian(d, normalize=True, seed=seed, backend=backend)

    eigenvalues, eigenvectors = np.linalg.eigh(hamiltonian)

    if normalize is True:
        eigenvalues -= eigenvalues[0]

        eigenvalues /= eigenvalues[1]

        shift = 2
        eigenvectors[:, shift:] = (
            eigenvectors[:, shift:] * max_eigenvalue / eigenvalues[-1]
        )
        eigenvalues[shift:] = eigenvalues[shift:] * max_eigenvalue / eigenvalues[-1]

        hamiltonian = np.zeros((d, d), dtype=complex)
        hamiltonian = backend.cast(hamiltonian, dtype=hamiltonian.dtype)
        # excluding the first eigenvector because first eigenvalue is zero
        for eigenvalue, eigenvector in zip(
            eigenvalues[1:], np.transpose(eigenvectors)[1:]
        ):
            hamiltonian += eigenvalue * np.outer(eigenvector, np.conj(eigenvector))

    U = comp_basis_to_pauli(nqubits, normalize=True, backend=backend)

    hamiltonian = np.real(U @ vectorization(hamiltonian, backend=backend))

    return hamiltonian, eigenvalues


def random_stochastic_matrix(
    dims: int,
    bistochastic: bool = False,
    diagonally_dominant: bool = False,
    precision_tol: float = None,
    max_iterations: int = None,
    seed=None,
    backend=None,
):
    """Creates a random stochastic matrix.

    Args:
        dims (int): dimension of the matrix.
        bistochastic (bool, optional): if ``True``, matrix is row- and column-stochastic.
            If ``False``, matrix is row-stochastic. Default is ``False``.
        diagonally_dominant (bool, optional): if ``True``, matrix is strictly diagonally
            dominant. Default is ``False``.
        precision_tol (float, optional): tolerance level for how much each probability
            distribution can deviate from summing up to ``1.0``. If ``None``,
            it defaults to ``qibo.config.PRECISION_TOL``. Default is ``None``.
        max_iterations (int, optional): when ``bistochastic=True``, maximum number
            of iterations used to normalize all rows and columns simultaneously.
            If ``None``, defaults to ``qibo.config.MAX_ITERATIONS``.
            Default is ``None``.
        seed (int or ``numpy.random.Generator``, optional): Either a generator of
            random numbers or a fixed seed to initialize a generator. If ``None``,
            initializes a statevectorgenerator with a random seed. Default is ``None``.
        backend (``qibo.backends.abstract.Backend``, optional): backend to be used
            in the execution. If ``None``, it uses ``GlobalBackend()``.
            Defaults to ``None``.

    Returns:
        (ndarray): a random stochastic matrix.

    """
    if dims <= 0:
        raise_error(ValueError, "dims must be type int and positive.")

    if not isinstance(bistochastic, bool):
        raise_error(
            TypeError,
            f"bistochastic must be type bool, but it is type {type(bistochastic)}.",
        )

    if not isinstance(diagonally_dominant, bool):
        raise_error(
            TypeError,
            f"diagonally_dominant must be type bool, but it is type {type(diagonally_dominant)}.",
        )

    if precision_tol is not None:
        if not isinstance(precision_tol, float):
            raise_error(
                TypeError,
                f"precision_tol must be type float, but it is type {type(precision_tol)}.",
            )
        if precision_tol < 0.0:
            raise_error(ValueError, "precision_tol must be non-negative.")

    if max_iterations is not None:
        if not isinstance(max_iterations, int):
            raise_error(
                TypeError,
                f"max_iterations must be type int, but it is type {type(precision_tol)}.",
            )
        if max_iterations <= 0.0:
            raise_error(ValueError, "max_iterations must be a positive int.")

    if (
        seed is not None
        and not isinstance(seed, int)
        and not isinstance(seed, np.random.Generator)
    ):
        raise_error(
            TypeError, "seed must be either type int or numpy.random.Generator."
        )

    if backend is None:  # pragma: no cover
        backend = GlobalBackend()

    local_state = (
        np.random.default_rng(seed) if seed is None or isinstance(seed, int) else seed
    )

    if precision_tol is None:
        precision_tol = PRECISION_TOL
    if max_iterations is None:
        max_iterations = MAX_ITERATIONS

    matrix = local_state.random(size=(dims, dims))
    if diagonally_dominant:
        matrix /= dims**2
        for k, row in enumerate(matrix):
            row = np.delete(row, obj=k)
            matrix[k, k] = 1 - np.sum(row)
    row_sum = np.sum(matrix, axis=1)

    row_sum = matrix.sum(axis=1)

    if bistochastic:
        column_sum = matrix.sum(axis=0)
        count = 0
        while count <= max_iterations - 1 and (
            (
                np.any(row_sum >= 1 + precision_tol)
                or np.any(row_sum <= 1 - precision_tol)
            )
            or (
                np.any(column_sum >= 1 + precision_tol)
                or np.any(column_sum <= 1 - precision_tol)
            )
        ):
            matrix = matrix / matrix.sum(axis=0)
            matrix = matrix / matrix.sum(axis=1)[:, np.newaxis]
            row_sum = matrix.sum(axis=1)
            column_sum = matrix.sum(axis=0)
            count += 1
        if count == max_iterations:
            warnings.warn("Reached max iterations.", RuntimeWarning)
    else:
        matrix = matrix / np.outer(row_sum, [1] * dims)

    matrix = backend.cast(matrix, dtype=matrix.dtype)

    return matrix


def _clifford_unitary(phase, x, y, z):
    """Returns a parametrized single-qubit Clifford gate,
    where possible parameters are defined in
    ``qibo.quantum_info.utils.ONEQUBIT_CLIFFORD_PARAMS``.

    Args:
        phase (float) : An angle.
        x (float) : prefactor.
        y (float) : prefactor.
        z (float) : prefactor.

    Returns:
        (ndarray): Clifford unitary with dimensions (2, 2).

    """

    return np.array(
        [
            [
                np.cos(phase / 2) - 1.0j * z * np.sin(phase / 2),
                -y * np.sin(phase / 2) - 1.0j * x * np.sin(phase / 2),
            ],
            [
                y * np.sin(phase / 2) - 1.0j * x * np.sin(phase / 2),
                np.cos(phase / 2) + 1.0j * z * np.sin(phase / 2),
            ],
        ]
    )
