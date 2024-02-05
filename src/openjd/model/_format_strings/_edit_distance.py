# Copyright Amazon.com, Inc. or its affiliates. All Rights Reserved.

from array import array


def closest(symbols: set[str], match: str) -> tuple[int, set[str]]:
    """Return the set of symbols that most closely match the given match symbol.

    Returns:
        tuple[int, set[str]]
            - [0]: Distance from 'match' to its closest match(es)
            - [1]: Empty-set - If there is no such symbol (i.e. this table is empty)
                   Other -- One or more symbols that match the closest
    """
    best_cost = len(match) + 1
    best_match = set()
    for sym in symbols:
        distance = _edit_distance(sym, match)
        if distance < best_cost:
            best_cost = distance
            best_match = set((sym,))
        elif distance == best_cost:
            best_match.add(sym)
    return best_cost, best_match


def _edit_distance(s1: str, s2: str) -> int:
    # Levenshtein distance for turning s1 into s2.
    # Dynamic programming implementation storing only two rows of the DP matrix.
    # Reference: https://www.codeproject.com/Articles/13525/Fast-memory-efficient-Levenshtein-algorithm-2

    if len(s1) == 0:
        return len(s2)
    if len(s2) == 0:
        return len(s1)

    # Previous row of distances. Initialized to:
    #   a0[i] = edit distance from "" to s2[0:i]
    a0 = array("L", (i for i in range(0, len(s2) + 1)))

    # Current row of distances -- initialized values are irrelevant; they'll be overwritten
    a1 = array("L", a0.tobytes())

    for s1_idx in range(1, len(s1) + 1):
        # Calculate a1 as the edit distance from s1[0:s1_idx] to s2

        # a1[0] = edit distance from s1[0:s1_idx] to ""
        #   i.e. delete s1_idx characters from s1
        a1[0] = s1_idx
        for s2_idx in range(1, len(s2) + 1):
            # Calculate a1[s2_idx] as the edit distance from s1[0:s1_idx] to s2[0:s2_idx]
            # given:
            #   a0[s2_idx-1] = edit distance from s1[0:s1_idx-1] to s2[0:s2_idx-1]
            #   a0[s2_idx] = edit distance from s1[0:s1_idx-1] to s2[0:s2_idx]
            #   a1[s2_idx-1] = edit distance from s1[0:s1_idx] to s2[0:s2_idx-1]

            # If we have s2[0:s2_idx] already then the step would be to delete the s1[s1_idx]
            delete_cost = a0[s2_idx] + 1

            # If we have s2[0:s2_idx-1] and are inserting s1[s1_idx]
            insert_cost = a1[s2_idx - 1] + 1

            # If we have s2[0:s2_idx-1] and are changing s1[s1_idx] in to s2[s2_idx-1]
            substitution_cost = a0[s2_idx - 1] + (0 if s1[s1_idx - 1] == s2[s2_idx - 1] else 1)

            # Cost of going from s2[0:s2_idx-1] to s2[0:s2_idx]
            a1[s2_idx] = min(delete_cost, insert_cost, substitution_cost)

        # Swap for the next iteration
        a0, a1 = a1, a0

    return a0[len(s2)]
