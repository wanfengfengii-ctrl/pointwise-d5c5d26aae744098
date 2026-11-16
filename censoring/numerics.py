"""Dense scalar helpers and finite-support fitting."""
from decimal import Decimal, localcontext
from fractions import Fraction
from itertools import combinations
from .errors import FitError

D = Decimal
PRECISION = 80
STATIONARITY = D("1e-32")
GRADIENT_BOUND = D("1e-26")
FEASIBILITY = D("1e-22")
BOUNDARY = D("1e-12")


def solve(matrix, rhs):
    """Pivoted square solve, preserving the scalar type of the input."""
    n = len(rhs)
    rows = [list(row) + [value] for row, value in zip(matrix, rhs)]
    for column in range(n):
        pivot = max(range(column, n), key=lambda i: abs(rows[i][column]))
        if rows[pivot][column] == 0:
            return None
        rows[column], rows[pivot] = rows[pivot], rows[column]
        scale = rows[column][column]
        rows[column] = [x / scale for x in rows[column]]
        for i in range(n):
            if i != column:
                scale = rows[i][column]
                rows[i] = [a - scale * b for a, b in zip(rows[i], rows[column])]
    return [row[-1] for row in rows]


def independent_rows(matrix):
    """Exact rank and pivot row selection for integer coverage matrices."""
    basis = {}
    selected = []
    for index, original in enumerate(matrix):
        row = [Fraction(value) for value in original]
        for pivot in sorted(basis):
            factor = row[pivot]
            row = [a - factor * b for a, b in zip(row, basis[pivot])]
        pivot = next((i for i, value in enumerate(row) if value), None)
        if pivot is not None:
            scale = row[pivot]
            basis[pivot] = [value / scale for value in row]
            selected.append(index)
    return selected


def observation_probabilities(matrix, mass):
    return tuple(sum((D(a) * p for a, p in zip(row, mass)), D(0)) for row in matrix)


def likelihood(probabilities, weights):
    return sum((D(w) * q.ln() for q, w in zip(probabilities, weights)), D(0))


def gradient(matrix, weights, probabilities):
    """Mass gradient g_j = sum_i(w_i*A_ij/q_i) for every support index."""
    total = [D(0)] * len(matrix[0])
    for row, weight, probability in zip(matrix, weights, probabilities):
        share = D(weight) / probability
        for j, covered in enumerate(row):
            if covered:
                total[j] += share
    return total


def _face_stationary(matrix, weights, face, max_iterations):
    """Interior stationary point on one simplex face, or None.

    Runs a safeguarded Newton iteration on the stationarity system
    g_j = N (EM multiplicative fallback) from the uniform face point.
    Publishes only on reaching the interior tolerance N*STATIONARITY
    within the per-face budget; faces marching to a boundary optimum
    are left to their sub-faces.
    """
    k = len(face)
    rows = [[row[j] for j in face] for row in matrix]
    if any(not any(row) for row in rows):
        return None
    total = D(sum(weights))
    point = [D(1) / k] * k
    multiplier = total
    for iteration in range(max_iterations + 1):
        probabilities = [sum((D(a) * p for a, p in zip(row, point)), D(0)) for row in rows]
        if min(probabilities) <= 0:
            return None
        grad = gradient(matrix, weights, probabilities)
        residual = max(abs(grad[j] - total) for j in face)
        if residual <= total * STATIONARITY:
            return point, probabilities, grad
        if iteration == max_iterations:
            return None
        if min(point) < BOUNDARY and residual > total * D("1e-10"):
            return None
        hessian = [[D(0)] * k for _ in range(k)]
        for row, weight, probability in zip(rows, weights, probabilities):
            share = D(weight) / (probability * probability)
            for a in range(k):
                if row[a]:
                    for b in range(k):
                        if row[b]:
                            hessian[a][b] += share
        system = [[-hessian[a][b] for b in range(k)] + [D(-1)] for a in range(k)]
        system.append([D(1)] * k + [D(0)])
        rhs = [multiplier - grad[face[a]] for a in range(k)] + [D(1) - sum(point)]
        step = solve(system, rhs)
        moved = False
        if step is not None:
            alpha = D(1)
            score = None
            for _ in range(40):
                trial = [p + alpha * d for p, d in zip(point, step[:k])]
                if min(trial) > 0:
                    q = [sum((D(a) * p for a, p in zip(row, trial)), D(0)) for row in rows]
                    if min(q) > 0:
                        g_trial = gradient(matrix, weights, q)
                        acceptable = max(abs(g_trial[j] - total) for j in face) < residual
                        if not acceptable:
                            if score is None:
                                score = likelihood(probabilities, weights)
                            acceptable = likelihood(q, weights) > score
                        if acceptable:
                            point = trial
                            multiplier += alpha * step[k]
                            moved = True
                            break
                alpha /= 2
        if not moved:
            point = [p * grad[j] / total for p, j in zip(point, face)]
    return None


def _certify(matrix, weights, mass, total):
    """Publish only a mass meeting the numerical KKT certificate."""
    probabilities = observation_probabilities(matrix, mass)
    if min(probabilities) <= 0:
        raise FitError("nonpositive fitted observation probability")
    grad = gradient(matrix, weights, probabilities)
    for j, value in enumerate(grad):
        if value > total * (1 + GRADIENT_BOUND):
            raise FitError("fitted mass exceeds the gradient bound")
        if mass[j] > 0 and abs(value - total) > total * GRADIENT_BOUND:
            raise FitError("fitted mass fails the stationarity bound")
    return mass, probabilities, likelihood(probabilities, weights)


def maximize(matrix, weights, max_iterations=100):
    """Maximize sum(count * log(sum(covered mass))) over the simplex.

    Enumerates the simplex faces (at most 2**6-1); on each face whose
    coverage-plus-sum system has exact full column rank, a safeguarded
    Newton iteration solves the interior stationarity system within the
    per-face iteration budget. The first face whose point satisfies the
    global KKT gradient bounds publishes its mass; coordinates outside
    the face carry exactly zero mass. No certified face means FitError.
    """
    with localcontext() as context:
        context.prec = PRECISION
        n = len(matrix[0])
        if any(not any(row) for row in matrix):
            raise FitError("observation has no supported event")
        total = D(sum(weights))
        for size in range(1, n + 1):
            for face in combinations(range(n), size):
                equations = [[row[j] for j in face] for row in matrix]
                equations.append([1] * size)
                if len(independent_rows(equations)) < size:
                    continue
                solved = _face_stationary(matrix, weights, face, max_iterations)
                if solved is None:
                    continue
                point, probabilities, grad = solved
                if any(grad[j] > total * (1 + GRADIENT_BOUND)
                       for j in range(n) if j not in face):
                    continue
                mass = tuple(point[face.index(j)] if j in face else D(0)
                             for j in range(n))
                return _certify(matrix, weights, mass, total)
        raise FitError("iteration budget exhausted before stationary allocation")


def mass_vertices(matrix, probabilities):
    """Every vertex of {p >= 0, sum p = 1, A p = probabilities}.

    The maximizing distributions are exactly this polytope, so its
    vertices carry the cumulative extrema. Basic feasible solutions are
    enumerated: exact rank-many independent coverage columns, an exact
    independent square subsystem, and the absolute FEASIBILITY tolerance
    on the equations and nonnegativity.
    """
    n = len(matrix[0])
    equations = [list(row) for row in matrix] + [[1] * n]
    rhs = list(probabilities) + [D(1)]
    rank = len(independent_rows(equations))
    vertices = []
    for basis in combinations(range(n), rank):
        columns = [[row[j] for j in basis] for row in equations]
        rows = independent_rows(columns)
        if len(rows) < rank:
            continue
        square = [[D(equations[i][j]) for j in basis] for i in rows[:rank]]
        point = solve(square, [rhs[i] for i in rows[:rank]])
        if point is None or any(value < -FEASIBILITY for value in point):
            continue
        feasible = True
        for equation, target in zip(equations, rhs):
            value = sum((D(equation[j]) * point[t] for t, j in enumerate(basis)), D(0))
            if abs(value - target) > FEASIBILITY:
                feasible = False
                break
        if not feasible:
            continue
        vertex = [D(0)] * n
        for value, j in zip(point, basis):
            vertex[j] = value if value > 0 else D(0)
        vertices.append(tuple(vertex))
    if not vertices:
        raise FitError("fitted probabilities bound no feasible mass")
    return vertices
