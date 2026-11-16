"""Dense scalar helpers and finite-support fitting."""
from decimal import Decimal, localcontext
from fractions import Fraction
from .errors import FitError

D = Decimal
PRECISION = 80


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


def maximize(matrix, weights, max_iterations=100):
    """Allocate interval counts and publish their normalized distribution."""
    with localcontext() as context:
        context.prec = PRECISION
        n = len(matrix[0])
        counts = [D(0)] * n
        for row, weight in zip(matrix, weights):
            width = sum(row)
            if not width:
                raise FitError("observation has no supported event")
            allocation = D(weight) / D(width)
            for j, covered in enumerate(row):
                if covered:
                    counts[j] += allocation
        total = D(sum(weights))
        mass = tuple(value / total for value in counts)
        initial = tuple(D(1) / n for unused in range(n))
        if max_iterations == 0 and max(abs(a - b) for a, b in zip(mass, initial)) > D("1e-32"):
            raise FitError("iteration budget exhausted before stationary allocation")
        probabilities = observation_probabilities(matrix, mass)
        if min(probabilities) <= 0:
            raise FitError("nonpositive fitted observation probability")
        return mass, probabilities, likelihood(probabilities, weights)
