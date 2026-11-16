"""Independent exact certificates for rational small examples.

The expected distribution is supplied by the fixture. Exact KKT proves global
optimality. A separate full-coordinate elimination with active zero equations
then obtains all feasible vertex cumulative values. No production numerics are
called, and the expected distribution need not be uniquely identifiable.
"""
from fractions import Fraction as F
from itertools import combinations


def unique_solution(equations, rhs, width):
    rows = [[F(x) for x in row] + [F(value)]
            for row, value in zip(equations, rhs)]
    pivot_row = 0
    pivots = []
    for column in range(width):
        selected = next((i for i in range(pivot_row, len(rows)) if rows[i][column]), None)
        if selected is None:
            continue
        rows[pivot_row], rows[selected] = rows[selected], rows[pivot_row]
        divisor = rows[pivot_row][column]
        rows[pivot_row] = [x / divisor for x in rows[pivot_row]]
        for i in range(len(rows)):
            if i != pivot_row:
                factor = rows[i][column]
                rows[i] = [a - factor * b for a, b in zip(rows[i], rows[pivot_row])]
        pivots.append(column)
        pivot_row += 1
    if any(all(x == 0 for x in row[:width]) and row[-1] != 0 for row in rows):
        return None
    if len(pivots) != width:
        return None
    answer = [F(0)] * width
    for i, column in enumerate(pivots):
        answer[column] = rows[i][-1]
    return answer


def certified_ranges(support, rows, expected_mass):
    n = len(support)
    mass = tuple(map(F, expected_mass))
    assert len(mass) == n and min(mass) >= 0 and sum(mass) == 1
    matrix = []
    weights = []
    for lower, upper, weight in rows:
        matrix.append([int((lower is None or lower <= point)
                           and (upper is None or point <= upper)) for point in support])
        weights.append(weight)
    q = [sum((a * p for a, p in zip(row, mass)), F(0)) for row in matrix]
    assert min(q) > 0
    total = sum(weights)
    for j in range(n):
        gradient = sum((F(weight * row[j]) / prob
                        for weight, row, prob in zip(weights, matrix, q)), F(0))
        assert gradient <= total
        if mass[j]:
            assert gradient == total
    equations = [[1] * n] + matrix
    rhs = [F(1)] + q
    candidates = []
    for size in range(n + 1):
        for zeros in combinations(range(n), size):
            extra = [[int(i == j) for i in range(n)] for j in zeros]
            answer = unique_solution(equations + extra, rhs + [F(0)] * size, n)
            if answer is not None and min(answer) >= 0:
                candidates.append(answer)
    assert candidates
    return [(min(sum(p[:end]) for p in candidates), max(sum(p[:end]) for p in candidates))
            for end in range(1, n + 1)]
