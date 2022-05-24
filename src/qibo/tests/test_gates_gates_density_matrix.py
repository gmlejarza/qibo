"""Test gates acting on density matrices."""
import pytest
import numpy as np
from qibo import gates
from qibo.config import raise_error
from qibo.tests.utils import random_density_matrix

_atol = 1e-8

def apply_gates(backend, gatelist, nqubits=None, initial_state=None):
    if initial_state is None:
        # TODO: Update this for density matrices
        state = backend.zero_state(nqubits)
    elif isinstance(initial_state, np.ndarray):
        state = np.copy(initial_state)
        if nqubits is None:
            nqubits = int(np.log2(len(state)))
        else: # pragma: no cover
            assert nqubits == int(np.log2(len(state)))
    else: # pragma: no cover
        raise_error(TypeError, "Invalid initial state type {}."
                               "".format(type(initial_state)))

    for gate in gatelist:
        state = backend.apply_gate_density_matrix(gate, state, nqubits)
    return state


def test_hgate_density_matrix(backend):
    initial_rho = random_density_matrix(2)
    gate = gates.H(1)
    final_rho = apply_gates(backend, [gate], 2, initial_rho)

    matrix = np.array([[1, 1], [1, -1]]) / np.sqrt(2)
    matrix = np.kron(np.eye(2), matrix)
    target_rho = matrix.dot(initial_rho).dot(matrix)
    backend.assert_allclose(final_rho, target_rho)


def test_rygate_density_matrix(backend):
    theta = 0.1234
    initial_rho = random_density_matrix(1)
    gate = gates.RY(0, theta=theta)
    final_rho = apply_gates(backend, [gate], 1, initial_rho)

    phase = np.exp(1j * theta / 2.0)
    matrix = phase * np.array([[phase.real, -phase.imag], [phase.imag, phase.real]])
    target_rho = matrix.dot(initial_rho).dot(matrix.T.conj())

    backend.assert_allclose(final_rho, target_rho, atol=_atol)


@pytest.mark.parametrize("gatename,gatekwargs",
                         [("H", {}), ("X", {}), ("Y", {}), ("Z", {}),
                          ("S", {}), ("SDG", {}), ("T", {}), ("TDG", {}),
                          ("I", {}), ("Align", {}),
                          ("RX", {"theta": 0.123}), ("RY", {"theta": 0.123}),
                          ("RZ", {"theta": 0.123}), ("U1", {"theta": 0.123}),
                          ("U2", {"phi": 0.123, "lam": 0.321}),
                          ("U3", {"theta": 0.123, "phi": 0.321, "lam": 0.123})])
def test_one_qubit_gates(backend, gatename, gatekwargs):
    """Check applying one qubit gates to one qubit density matrix."""
    initial_rho = random_density_matrix(1)
    gate = getattr(gates, gatename)(0, **gatekwargs)
    final_rho = apply_gates(backend, [gate], 1, initial_rho)

    matrix = backend.asmatrix(gate)
    target_rho = np.einsum("ab,bc,cd->ad", matrix, initial_rho, matrix.conj().T)
    backend.assert_allclose(final_rho, target_rho)


@pytest.mark.parametrize("gatename", ["H", "X", "Y", "Z", "S", "SDG", "T", "TDG"])
def test_controlled_by_one_qubit_gates(backend, gatename):
    initial_rho = random_density_matrix(2)
    gate = getattr(gates, gatename)(1).controlled_by(0)
    final_rho = apply_gates(backend, [gate], 2, initial_rho)

    matrix = backend.asmatrix(getattr(gates, gatename)(1))
    cmatrix = np.eye(4, dtype=matrix.dtype)
    cmatrix[2:, 2:] = matrix
    target_rho = np.einsum("ab,bc,cd->ad", cmatrix, initial_rho, cmatrix.conj().T)
    backend.assert_allclose(final_rho, target_rho)


@pytest.mark.parametrize("gatename,gatekwargs",
                         [("CNOT", {}), ("CZ", {}), ("SWAP", {}),
                          ("CRX", {"theta": 0.123}), ("CRY", {"theta": 0.123}),
                          ("CRZ", {"theta": 0.123}), ("CU1", {"theta": 0.123}),
                          ("CU2", {"phi": 0.123, "lam": 0.321}),
                          ("CU3", {"theta": 0.123, "phi": 0.321, "lam": 0.123}),
                          ("fSim", {"theta": 0.123, "phi": 0.543})])
def test_two_qubit_gates(backend, gatename, gatekwargs):
    """Check applying two qubit gates to two qubit density matrix."""
    initial_rho = random_density_matrix(2)
    gate = getattr(gates, gatename)(0, 1, **gatekwargs)
    final_rho = apply_gates(backend, [gate], 2, initial_rho)

    matrix = backend.asmatrix(gate)
    target_rho = np.einsum("ab,bc,cd->ad", matrix, initial_rho, matrix.conj().T)
    backend.assert_allclose(final_rho, target_rho, atol=_atol)


def test_toffoli_gate(backend):
    """Check applying Toffoli to three qubit density matrix."""
    initial_rho = random_density_matrix(3)
    gate = gates.TOFFOLI(0, 1, 2)
    final_rho = apply_gates(backend, [gate], 3, initial_rho)

    matrix = backend.asmatrix(gate)
    target_rho = np.einsum("ab,bc,cd->ad", matrix, initial_rho, matrix.conj().T)
    backend.assert_allclose(final_rho, target_rho)


@pytest.mark.parametrize("nqubits", [1, 2, 3])
def test_unitary_gate(backend, nqubits):
    """Check applying `gates.Unitary` to density matrix."""
    shape = 2 * (2 ** nqubits,)
    matrix = np.random.random(shape) + 1j * np.random.random(shape)
    initial_rho = random_density_matrix(nqubits)
    gate = gates.Unitary(matrix, *range(nqubits))
    final_rho = apply_gates(backend, [gate], nqubits, initial_rho)
    target_rho = np.einsum("ab,bc,cd->ad", matrix, initial_rho, matrix.conj().T)
    backend.assert_allclose(final_rho, target_rho)


def test_cu1gate_application_twoqubit(backend):
    """Check applying two qubit gate to three qubit density matrix."""
    theta = 0.1234
    nqubits = 3
    initial_rho = random_density_matrix(nqubits)
    gate = gates.CU1(0, 1, theta=theta)
    final_rho = apply_gates(backend, [gate], nqubits, initial_rho)

    matrix = np.eye(4, dtype=np.complex128)
    matrix[3, 3] = np.exp(1j * theta)
    matrix = np.kron(matrix, np.eye(2))
    target_rho = matrix.dot(initial_rho).dot(matrix.T.conj())
    backend.assert_allclose(final_rho, target_rho)


@pytest.mark.skip("Move this to special tests")
def test_flatten_density_matrix(backend):
    """Check ``Flatten`` gate works with density matrices."""
    target_rho = random_density_matrix(3)
    initial_rho = np.zeros(6 * (2,))
    gate = gates.Flatten(target_rho)
    gate.density_matrix = True
    final_rho = np.reshape(gate(initial_rho), (8, 8))
    K.assert_allclose(final_rho, target_rho)


def test_controlled_by_no_effect(backend):
    """Check controlled_by SWAP that should not be applied."""
    from qibo.models import Circuit
    initial_rho = np.zeros((16, 16))
    initial_rho[0, 0] = 1

    c = Circuit(4, density_matrix=True)
    c.add(gates.X(0))
    c.add(gates.SWAP(1, 3).controlled_by(0, 2))
    final_rho = c(np.copy(initial_rho))

    c = Circuit(4, density_matrix=True)
    c.add(gates.X(0))
    target_rho = c(np.copy(initial_rho))
    K.assert_allclose(final_rho, target_rho)


def test_controlled_with_effect(backend):
    """Check controlled_by SWAP that should be applied."""
    from qibo.models import Circuit
    initial_rho = np.zeros((16, 16))
    initial_rho[0, 0] = 1

    c = Circuit(4, density_matrix=True)
    c.add(gates.X(0))
    c.add(gates.X(2))
    c.add(gates.SWAP(1, 3).controlled_by(0, 2))
    final_rho = c(np.copy(initial_rho)).numpy()

    c = Circuit(4, density_matrix=True)
    c.add(gates.X(0))
    c.add(gates.X(2))
    c.add(gates.SWAP(1, 3))
    target_rho = c(np.copy(initial_rho)).numpy()
    K.assert_allclose(final_rho, target_rho)


@pytest.mark.parametrize("nqubits", [4, 5])
def test_controlled_by_random(backend, nqubits):
    """Check controlled_by method on gate."""
    from qibo.models import Circuit
    from qibo.tests.utils import random_state
    initial_psi = random_state(nqubits)
    initial_rho = np.outer(initial_psi, initial_psi.conj())
    c = Circuit(nqubits, density_matrix=True)
    c.add(gates.RX(1, theta=0.789).controlled_by(2))
    c.add(gates.fSim(0, 2, theta=0.123, phi=0.321).controlled_by(1, 3))
    final_rho = c(np.copy(initial_rho))

    c = Circuit(nqubits)
    c.add(gates.RX(1, theta=0.789).controlled_by(2))
    c.add(gates.fSim(0, 2, theta=0.123, phi=0.321).controlled_by(1, 3))
    target_psi = c(np.copy(initial_psi))
    target_rho = np.outer(target_psi, np.conj(target_psi))
    K.assert_allclose(final_rho, target_rho)


@pytest.mark.parametrize("qubit", [0, 1, 2])
def test_partial_trace_gate(backend, qubit):
    gate = gates.PartialTrace(qubit)
    gate.density_matrix = True
    initial_rho = random_density_matrix(3)
    final_state = gate(np.copy(initial_rho))

    zero_state = np.array([[1, 0], [0, 0]])
    target_state = np.reshape(initial_rho, 6 * (2,))
    if qubit == 0:
        target_state = np.einsum("aBCabc,Dd->DBCdbc", target_state, zero_state)
    elif qubit == 1:
        target_state = np.einsum("AbCabc,Dd->ADCadc", target_state, zero_state)
    elif qubit == 2:
        target_state = np.einsum("ABcabc,Dd->ABDabd", target_state, zero_state)
    target_state = np.reshape(target_state, (8, 8))
    K.assert_allclose(final_state, target_state)


@pytest.mark.skip("Move this to channel tests")
def test_partial_trace_gate_errors(backend):
    gate = gates.PartialTrace(0, 1)
    # attempt to create unitary matrix
    with pytest.raises(ValueError):
        gate._construct_unitary()
    # attempt to call on state vector
    state = np.random.random(16) + 1j * np.random.random(16)
    with pytest.raises(RuntimeError):
        gate(state)


@pytest.mark.skip("Move this to channel tests")
def test_channel_gate_setters(backend):
    a1 = np.sqrt(0.4) * np.array([[0, 1], [1, 0]])
    a2 = np.sqrt(0.6) * np.array([[1, 0, 0, 0], [0, 1, 0, 0],
                                  [0, 0, 0, 1], [0, 0, 1, 0]])
    channel = gates.KrausChannel([((1,), a1), ((0, 1), a2)])
    _ = channel.inverse_gates # create inverse gates
    channel.nqubits = 5
    channel.density_matrix = True
    for gate in channel.gates:
        assert gate.nqubits == 5
        assert gate.density_matrix
    for gate in channel.inverse_gates:
        if gate is not None:
            assert gate.nqubits == 5
            assert gate.density_matrix


@pytest.mark.skip("Move this to measurement tests")
def test_measurement_density_matrix(backend):
    from qibo.tests.test_measurement_gate import assert_result
    state = np.zeros(4)
    state[2] = 1
    rho = np.outer(state, state.conj())
    mgate = gates.M(0, 1)
    mgate.density_matrix = True
    result = mgate(K.cast(rho), nshots=100)

    target_binary_samples = np.zeros((100, 2))
    target_binary_samples[:, 0] = 1
    assert_result(result,
                  decimal_samples=2 * np.ones((100,)),
                  binary_samples=target_binary_samples,
                  decimal_frequencies={2: 100},
                  binary_frequencies={"10": 100})


@pytest.mark.parametrize("nqubits", [5, 6])
def test_variational_layer_density_matrix(backend, nqubits):
    from qibo.models import Circuit
    theta = 2 * np.pi * np.random.random(nqubits)
    c = Circuit(nqubits, density_matrix=True)
    c.add((gates.RY(i, t) for i, t in enumerate(theta)))
    c.add((gates.CZ(i, i + 1) for i in range(0, nqubits - 1, 2)))
    target_state = c()
    pairs = list((i, i + 1) for i in range(0, nqubits - 1, 2))
    c = Circuit(nqubits, density_matrix=True)
    c.add(gates.VariationalLayer(range(nqubits), pairs,
                                  gates.RY, gates.CZ, theta))
    final_state = c()
    K.assert_allclose(target_state, final_state)
    gate = gates.VariationalLayer(range(nqubits), pairs,
                                  gates.RY, gates.CZ, theta)
    gate.density_matrix = True
    final_state = gate(c.get_initial_state())
    K.assert_allclose(target_state, final_state)
